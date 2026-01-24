"""Run execution service.

This service manages the execution of AI Agent runs following the
orchestrator management pattern where zloth centrally manages git
operations while AI Agents only edit files.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zloth_api.agents.llm_router import LLMConfig, LLMRouter
from zloth_api.agents.patch_agent import PatchAgent
from zloth_api.config import settings
from zloth_api.domain.enums import ExecutorType, JobKind, RoleExecutionStatus, RunStatus
from zloth_api.domain.models import (
    AgentConstraints,
    AgentRequest,
    ImplementationResult,
    Job,
    Run,
    RunCreate,
)
from zloth_api.errors import NotFoundError
from zloth_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from zloth_api.executors.codex_executor import CodexExecutor, CodexOptions
from zloth_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from zloth_api.roles.base_service import BaseRoleService
from zloth_api.roles.registry import RoleRegistry
from zloth_api.services.git_service import GitService
from zloth_api.services.job_worker import JobWorker
from zloth_api.services.model_service import ModelService
from zloth_api.services.repo_service import RepoService
from zloth_api.services.run_executor import ExecutorEntry, RunExecutor
from zloth_api.services.workspace_adapters import (
    CloneWorkspaceAdapter,
    ExecutionWorkspaceInfo,
    WorkspaceAdapter,
)
from zloth_api.services.workspace_service import WorkspaceService
from zloth_api.storage.dao import JobDAO, RunDAO, TaskDAO, UserPreferencesDAO
from zloth_api.utils.github_url import parse_github_owner_repo

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from zloth_api.services.github_service import GitHubService
    from zloth_api.services.output_manager import OutputManager


# Note: Removed legacy in-file QueueAdapter. Run execution is handled by
# JobWorker (durable queue) + RunExecutor (encapsulated execution logic).


@RoleRegistry.register("implementation")
class RunService(BaseRoleService[Run, RunCreate, ImplementationResult]):
    """Service for managing and executing runs (Implementation Role).

    Following the orchestrator management pattern, this service:
    - Creates isolated execution workspaces (clone-based)
    - Runs AI Agent CLIs (file editing only)
    - Automatically stages, commits, and pushes changes
    - Tracks commit SHAs for PR creation

    This service inherits from BaseRoleService for common role patterns
    while maintaining its specialized implementation logic.
    """

    def __init__(
        self,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        job_dao: JobDAO,
        model_service: ModelService,
        repo_service: RepoService,
        git_service: GitService | None = None,
        workspace_service: WorkspaceService | None = None,
        user_preferences_dao: UserPreferencesDAO | None = None,
        github_service: GitHubService | None = None,
        output_manager: OutputManager | None = None,
    ):
        # Initialize base class with output manager and executors
        super().__init__(output_manager=output_manager)

        self.run_dao = run_dao
        self.task_dao = task_dao
        self.job_dao = job_dao
        self.model_service = model_service
        self.repo_service = repo_service
        self.git_service = git_service or GitService()
        self.workspace_service = workspace_service or WorkspaceService()
        self.user_preferences_dao = user_preferences_dao
        self.github_service = github_service
        # Note: self.output_manager is set by base class
        self.job_worker: JobWorker | None = None
        self.llm_router = LLMRouter()
        # Note: Executors are also available via self._executors from base class
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.codex_executor = CodexExecutor(CodexOptions(codex_cli_path=settings.codex_cli_path))
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
        )
        # Workspace isolation mode:
        # Worktree-based isolation is deprecated. We always use clone-based workspaces.
        if not settings.use_clone_isolation:
            logger.warning(
                "use_clone_isolation=false is deprecated and will be ignored; "
                "zloth now uses clone-based workspaces only."
            )
        self.workspace_adapter: WorkspaceAdapter = CloneWorkspaceAdapter(self.workspace_service)

        # Encapsulated CLI executor to reduce RunService responsibilities
        self._run_executor = RunExecutor(
            run_dao=self.run_dao,
            git_service=self.git_service,
            workspace_adapter=self.workspace_adapter,
            executors={
                ExecutorType.CLAUDE_CODE: ExecutorEntry(self.claude_executor, "Claude Code"),
                ExecutorType.CODEX_CLI: ExecutorEntry(self.codex_executor, "Codex"),
                ExecutorType.GEMINI_CLI: ExecutorEntry(self.gemini_executor, "Gemini"),
            },
            llm_router=self.llm_router,
            output_manager=output_manager,
            github_service=self.github_service,
        )

    def set_job_worker(self, worker: JobWorker) -> None:
        """Attach the shared JobWorker instance (for best-effort cancellation)."""
        self.job_worker = worker

    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        """Create runs for multiple models or CLI executors.

        Supports parallel execution of multiple CLI executors (Claude Code, Codex, Gemini)
        by specifying executor_types list.

        Args:
            task_id: Task ID.
            data: Run creation data with model IDs or executor type(s).

        Returns:
            List of created Run objects.
        """
        # Verify task exists
        task = await self.task_dao.get(task_id)
        if not task:
            raise NotFoundError("Task not found", details={"task_id": task_id})

        # Get repo for workspace
        repo = await self.repo_service.get(task.repo_id)
        if not repo:
            raise NotFoundError("Repo not found", details={"repo_id": task.repo_id})

        runs: list[Run] = []
        existing_runs = await self.run_dao.list(task_id)

        # Determine executor types to use:
        # 1. If executor_types is specified, use it (new multi-CLI parallel execution)
        # 2. Otherwise, fall back to executor_type for backward compatibility
        executor_types: list[ExecutorType]
        if data.executor_types:
            executor_types = data.executor_types
        else:
            executor_types = [data.executor_type]

        # Note: Each executor type maintains its own worktree and session
        # so we allow multiple different CLI types in the same task

        # Separate CLI executors from PATCH_AGENT
        cli_executor_types = [
            et
            for et in executor_types
            if et in {ExecutorType.CLAUDE_CODE, ExecutorType.CODEX_CLI, ExecutorType.GEMINI_CLI}
        ]
        has_patch_agent = ExecutorType.PATCH_AGENT in executor_types

        # Create runs for each CLI executor type
        for executor_type in cli_executor_types:
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.selected_branch or repo.default_branch,
                executor_type=executor_type,
                message_id=data.message_id,
            )
            runs.append(run)

        # Handle PATCH_AGENT if included
        if has_patch_agent:
            # Create runs for each model (PatchAgent)
            model_ids = data.model_ids
            if not model_ids:
                # If the task is already locked to patch_agent, reuse the most recent
                # model set (grouped by latest patch_agent instruction).
                patch_runs = [
                    r for r in existing_runs if r.executor_type == ExecutorType.PATCH_AGENT
                ]
                if patch_runs:
                    latest_instruction = patch_runs[0].instruction  # newest-first
                    model_ids = []
                    seen: set[str] = set()
                    for r in patch_runs:
                        if r.instruction != latest_instruction:
                            continue
                        if r.model_id and r.model_id not in seen:
                            seen.add(r.model_id)
                            model_ids.append(r.model_id)
                if not model_ids:
                    raise ValueError("model_ids required for patch_agent executor")

            for model_id in model_ids:
                # Verify model exists and get model info
                model = await self.model_service.get(model_id)
                if not model:
                    raise ValueError(f"Model not found: {model_id}")

                # Create run record with denormalized model info
                run = await self.run_dao.create(
                    task_id=task_id,
                    instruction=data.instruction,
                    executor_type=ExecutorType.PATCH_AGENT,
                    message_id=data.message_id,
                    model_id=model_id,
                    model_name=model.model_name,
                    provider=model.provider,
                    base_ref=data.base_ref or repo.selected_branch or repo.default_branch,
                )
                runs.append(run)

                # Enqueue for execution (persistent job)
                await self.job_dao.create(
                    kind=JobKind.RUN_EXECUTE,
                    ref_id=run.id,
                    payload={},
                )

        return runs

    async def _create_cli_run(
        self,
        task_id: str,
        repo: Any,
        instruction: str,
        base_ref: str,
        executor_type: ExecutorType,
        message_id: str | None = None,
    ) -> Run:
        """Create and start a CLI-based run (Claude Code, Codex, or Gemini).

        This method uses clone-based workspaces only (worktree isolation is deprecated).
        Existing workspaces are reused for conversation continuation when valid.

        Args:
            task_id: Task ID.
            repo: Repository object.
            instruction: Natural language instruction.
            base_ref: Base branch to work from.
            executor_type: Type of CLI executor to use.
            message_id: ID of the triggering message.

        Returns:
            Created Run object.
        """
        # Get the latest session ID for this task and executor type
        # This enables conversation persistence across multiple runs
        previous_session_id = await self.run_dao.get_latest_session_id(
            task_id=task_id,
            executor_type=executor_type,
        )

        # Check for existing workspace/worktree to reuse
        existing_run = await self.run_dao.get_latest_worktree_run(
            task_id=task_id,
            executor_type=executor_type,
        )

        workspace_info: ExecutionWorkspaceInfo | None = None

        if existing_run and existing_run.worktree_path:
            workspace_path: Path | None = Path(existing_run.worktree_path)

            # Never reuse legacy worktrees (paths under worktrees_dir).
            # We store the workspace path in Run.worktree_path for backward compatibility.
            worktrees_root = getattr(self.git_service, "worktrees_dir", None)
            if worktrees_root and str(workspace_path).startswith(str(worktrees_root)):
                logger.info("Skipping reuse of legacy worktree path: %s", workspace_path)
                workspace_path = None

            if workspace_path is None:
                is_valid = False
            else:
                is_valid = await self.workspace_adapter.is_valid(workspace_path)

            if is_valid and workspace_path is not None:
                # If we're working from the repo's default branch, ensure the workspace
                # still contains the latest origin/<default>. Otherwise, create fresh.
                should_check_default = (base_ref == repo.default_branch) and bool(
                    repo.default_branch
                )
                if should_check_default:
                    default_ref = f"origin/{repo.default_branch}"
                    up_to_date = await self.git_service.is_ancestor(
                        repo_path=workspace_path,
                        ancestor=default_ref,
                        descendant="HEAD",
                    )
                    if not up_to_date:
                        logger.info(
                            "Existing workspace is behind latest default; creating new "
                            f"(workspace={workspace_path}, default={default_ref})"
                        )
                    else:
                        workspace_info = ExecutionWorkspaceInfo(
                            path=workspace_path,
                            branch_name=existing_run.working_branch or "",
                            base_branch=existing_run.base_ref or base_ref,
                            created_at=existing_run.created_at or datetime.utcnow(),
                        )
                        logger.info(f"Reusing existing workspace: {workspace_path}")
                else:
                    # Reuse existing workspace (no default-base freshness check)
                    workspace_info = ExecutionWorkspaceInfo(
                        path=workspace_path,
                        branch_name=existing_run.working_branch or "",
                        base_branch=existing_run.base_ref or base_ref,
                        created_at=existing_run.created_at or datetime.utcnow(),
                    )
                    logger.info(f"Reusing existing workspace: {workspace_path}")
            else:
                logger.warning(f"Workspace invalid or broken, will create new: {workspace_path}")

        # Create the run record
        run = await self.run_dao.create(
            task_id=task_id,
            instruction=instruction,
            executor_type=executor_type,
            message_id=message_id,
            base_ref=base_ref,
        )

        if not workspace_info:
            branch_prefix: str | None = None
            if self.user_preferences_dao:
                prefs = await self.user_preferences_dao.get()
                branch_prefix = prefs.default_branch_prefix if prefs else None

            # Get auth_url for private repos
            auth_url: str | None = None
            if self.github_service and repo.repo_url:
                try:
                    owner, repo_name = parse_github_owner_repo(repo.repo_url)
                    auth_url = await self.github_service.get_auth_url(owner, repo_name)
                except Exception as e:
                    logger.warning(f"Could not get auth_url for workspace creation: {e}")

            logger.info(f"Creating execution workspace for run {run.id[:8]}")
            workspace_info = await self.workspace_adapter.create(
                repo=repo,
                base_branch=base_ref,
                run_id=run.id,
                branch_prefix=branch_prefix,
                auth_url=auth_url,
            )

        # Update run with workspace info
        await self.run_dao.update_worktree(
            run.id,
            working_branch=workspace_info.branch_name,
            worktree_path=str(workspace_info.path),
        )

        # Update the run object with new info
        updated_run = await self.run_dao.get(run.id)
        if not updated_run:
            raise ValueError(f"Run not found after update: {run.id}")

        # Enqueue for execution (persistent job).
        # We store resume_session_id in payload because it is derived at enqueue-time.
        await self.job_dao.create(
            kind=JobKind.RUN_EXECUTE,
            ref_id=updated_run.id,
            payload={"resume_session_id": previous_session_id} if previous_session_id else {},
        )

        return updated_run

    async def get(self, run_id: str) -> Run | None:
        """Get a run by ID.

        Args:
            run_id: Run ID.

        Returns:
            Run object or None if not found.
        """
        return await self.run_dao.get(run_id)

    async def list(self, task_id: str) -> list[Run]:
        """List runs for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of Run objects.
        """
        return await self.run_dao.list(task_id)

    async def execute_job(self, job: Job) -> None:
        """Execute a durable queue job for a run.

        The worker calls this using only (run_id + payload). All runtime context
        must be reconstructed from the database.
        """
        if job.kind != JobKind.RUN_EXECUTE:
            raise ValueError(f"Unsupported job kind for RunService: {job.kind}")

        run = await self.run_dao.get(job.ref_id)
        if not run:
            raise ValueError(f"Run not found: {job.ref_id}")

        task = await self.task_dao.get(run.task_id)
        if not task:
            raise ValueError(f"Task not found for run: {run.task_id}")

        repo = await self.repo_service.get(task.repo_id)
        if not repo:
            raise ValueError(f"Repo not found for task: {task.repo_id}")

        if run.executor_type == ExecutorType.PATCH_AGENT:
            await self._execute_patch_agent_run(run, repo)
        else:
            if not run.worktree_path or not run.working_branch:
                raise ValueError(f"Run missing workspace info: {run.id}")

            workspace_info = ExecutionWorkspaceInfo(
                path=Path(run.worktree_path),
                branch_name=run.working_branch,
                base_branch=run.base_ref or repo.default_branch or "main",
                created_at=datetime.utcnow(),
            )

            resume_session_id = None
            if job.payload:
                resume_session_id = job.payload.get("resume_session_id")

            await self._execute_cli_run(
                run=run,
                worktree_info=workspace_info,
                executor_type=run.executor_type,
                resume_session_id=resume_session_id,
                repo=repo,
            )

        # Determine success based on persisted run status
        updated = await self.run_dao.get(run.id)
        if updated and updated.status == RunStatus.FAILED:
            raise RuntimeError(updated.error or "Run failed")

    async def cancel(self, run_id: str) -> bool:
        """Cancel a run.

        Args:
            run_id: Run ID.

        Returns:
            True if cancelled.
        """
        run = await self.run_dao.get(run_id)
        # Cancel queued job (durable queue) and best-effort cancel running job in this process.
        if self.job_worker:
            cancelled = await self.job_worker.cancel_ref(kind=JobKind.RUN_EXECUTE, ref_id=run_id)
        else:
            cancelled = await self.job_dao.cancel_queued_by_ref(
                kind=JobKind.RUN_EXECUTE, ref_id=run_id
            )

        if cancelled:
            await self.run_dao.update_status(run_id, RunStatus.CANCELED)

            # Cleanup workspace if it's a CLI executor run
            cli_executors = {
                ExecutorType.CLAUDE_CODE,
                ExecutorType.CODEX_CLI,
                ExecutorType.GEMINI_CLI,
            }
            if run and run.executor_type in cli_executors and run.worktree_path:
                workspace_path = Path(run.worktree_path)
                await self.workspace_adapter.cleanup(path=workspace_path, delete_branch=True)

        return cancelled

    async def cleanup_workspace(self, run_id: str) -> bool:
        """Clean up the workspace for a run.

        Args:
            run_id: Run ID.

        Returns:
            True if cleanup was successful.
        """
        run = await self.run_dao.get(run_id)
        if not run or not run.worktree_path:
            return False

        workspace_path = Path(run.worktree_path)
        await self.workspace_adapter.cleanup(path=workspace_path, delete_branch=False)
        return True

    # Keep old method name for backward compatibility
    async def cleanup_worktree(self, run_id: str) -> bool:
        """Clean up the worktree for a run (deprecated, use cleanup_workspace).

        Args:
            run_id: Run ID.

        Returns:
            True if cleanup was successful.
        """
        return await self.cleanup_workspace(run_id)

    async def _execute_patch_agent_run(self, run: Run, repo: Any) -> None:
        """Execute a PatchAgent run.

        Args:
            run: Run object.
            repo: Repository object.
        """
        # Validate required fields for PatchAgent runs
        if not run.model_id or not run.provider or not run.model_name:
            raise ValueError(
                f"PatchAgent run {run.id} missing required model info: "
                f"model_id={run.model_id}, provider={run.provider}, model_name={run.model_name}"
            )

        try:
            # Update status to running
            await self.run_dao.update_status(run.id, RunStatus.RUNNING)

            # Create working copy
            workspace_path = self.repo_service.create_working_copy(repo, run.id)

            try:
                # Get API key
                api_key = await self.model_service.get_decrypted_key(run.model_id)
                if not api_key:
                    raise ValueError("API key not found")

                # Create LLM client
                config = LLMConfig(
                    provider=run.provider,
                    model_name=run.model_name,
                    api_key=api_key,
                )
                llm_client = self.llm_router.get_client(config)

                # Create and run agent
                agent = PatchAgent(llm_client)
                request = AgentRequest(
                    workspace_path=str(workspace_path),
                    base_ref=run.base_ref or "HEAD",
                    instruction=run.instruction,
                    constraints=AgentConstraints(),
                )

                result = await agent.run(request)

                # Update run with results
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.SUCCEEDED,
                    summary=result.summary,
                    patch=result.patch,
                    files_changed=result.files_changed,
                    logs=result.logs,
                    warnings=result.warnings,
                )

            finally:
                # Cleanup working copy
                self.repo_service.cleanup_working_copy(run.id)

        except asyncio.CancelledError:
            # Task was cancelled (e.g., due to timeout or user cancellation)
            logger.warning(f"[{run.id[:8]}] PatchAgent run was cancelled")
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error="Task was cancelled (timeout or user cancellation)",
                logs=["Execution cancelled"],
            )
            raise  # Re-raise to propagate cancellation

        except Exception as e:
            # Update status to failed
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error=str(e),
                logs=[f"Execution failed: {str(e)}"],
            )

    async def _execute_cli_run(
        self,
        run: Run,
        worktree_info: ExecutionWorkspaceInfo,
        executor_type: ExecutorType,
        resume_session_id: str | None = None,
        repo: Any = None,
    ) -> None:
        """Delegate to RunExecutor for CLI execution."""
        await self._run_executor.execute_cli_run(
            run=run,
            worktree=worktree_info,
            executor_type=executor_type,
            repo=repo,
            resume_session_id=resume_session_id,
        )

    # Helper methods for CLI execution were moved to RunExecutor.

    # ==========================================
    # BaseRoleService Abstract Method Implementations
    # ==========================================

    async def create(self, task_id: str, data: RunCreate) -> Run:
        """Create a single run (BaseRoleService interface).

        Note: For multiple runs, use create_runs() instead.

        Args:
            task_id: Task ID.
            data: Run creation data.

        Returns:
            Created Run object.
        """
        runs = await self.create_runs(task_id, data)
        if not runs:
            raise ValueError("No runs created")
        return runs[0]

    # Note: get() method is inherited from the existing implementation above (line ~395)

    async def list_by_task(self, task_id: str) -> list[Run]:
        """List runs for a task (BaseRoleService interface).

        Args:
            task_id: Task ID.

        Returns:
            List of Run objects.
        """
        return await self.run_dao.list(task_id)

    async def _execute(self, record: Run) -> ImplementationResult:
        """Execute run-specific logic (BaseRoleService interface).

        Note: RunService uses its own execution flow via _execute_cli_run
        and _execute_patch_agent_run, so this method is not directly used.

        Args:
            record: Run record.

        Returns:
            ImplementationResult.
        """
        # RunService manages execution via create_runs which enqueues
        # _execute_cli_run or _execute_patch_agent_run directly.
        # This implementation is provided for interface compliance.
        return ImplementationResult(
            success=False,
            error="Direct execution not supported. Use create_runs() instead.",
        )

    async def _update_status(
        self,
        record_id: str,
        status: RoleExecutionStatus,
        result: ImplementationResult | None = None,
    ) -> None:
        """Update run status (BaseRoleService interface).

        Args:
            record_id: Run ID.
            status: New status.
            result: Optional result to save.
        """
        if result:
            await self.run_dao.update_status(
                record_id,
                status,
                summary=result.summary,
                patch=result.patch,
                files_changed=result.files_changed,
                logs=result.logs,
                warnings=result.warnings,
                error=result.error,
                session_id=result.session_id,
            )
        else:
            await self.run_dao.update_status(record_id, status)

    def _get_record_id(self, record: Run) -> str:
        """Extract ID from run (BaseRoleService interface).

        Args:
            record: Run record.

        Returns:
            Run ID.
        """
        return record.id

    def _create_error_result(self, error: str) -> ImplementationResult:
        """Create error result (BaseRoleService interface).

        Args:
            error: Error message.

        Returns:
            ImplementationResult with error.
        """
        return ImplementationResult(
            success=False,
            error=error,
            logs=[f"Error: {error}"],
        )
