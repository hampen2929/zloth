"""Run execution service.

This service manages the execution of AI Agent runs following the
orchestrator management pattern where zloth centrally manages git
operations while AI Agents only edit files.
"""

from __future__ import annotations

import asyncio
import builtins
import logging
from collections.abc import Callable, Coroutine
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from zloth_api.agents.llm_router import LLMConfig, LLMRouter
from zloth_api.agents.patch_agent import PatchAgent
from zloth_api.config import settings
from zloth_api.domain.enums import ExecutorType, JobKind, RoleExecutionStatus, RunStatus
from zloth_api.domain.models import (
    SUMMARY_FILE_PATH,
    AgentConstraints,
    AgentRequest,
    FileDiff,
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
from zloth_api.services.commit_message import ensure_english_commit_message
from zloth_api.services.job_worker import JobWorker
from zloth_api.services.diff_parser import parse_unified_diff
from zloth_api.services.git_service import GitService
from zloth_api.services.model_service import ModelService
from zloth_api.services.repo_service import RepoService
from zloth_api.services.workspace_adapters import (
    CloneWorkspaceAdapter,
    ExecutionWorkspaceInfo,
    WorkspaceAdapter,
    WorktreeWorkspaceAdapter,
)
from zloth_api.services.workspace_service import WorkspaceService
from zloth_api.storage.dao import JobDAO, RunDAO, TaskDAO, UserPreferencesDAO
from zloth_api.utils.github_url import parse_github_owner_repo

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from zloth_api.services.github_service import GitHubService
    from zloth_api.services.output_manager import OutputManager


# Note: QueueAdapter is kept for backward compatibility
# New code should use RoleQueueAdapter from roles.base_service
class QueueAdapter:
    """In-memory queue adapter with concurrency control and timeout.

    Features:
    - Concurrency limit via semaphore to prevent resource exhaustion
    - Execution timeout to prevent tasks from hanging indefinitely
    - Automatic cleanup of completed tasks to prevent memory leaks

    Can be replaced with Celery/RQ/Redis in v0.2+.
    """

    def __init__(
        self,
        max_concurrent: int | None = None,
        default_timeout: int | None = None,
    ) -> None:
        """Initialize the queue adapter.

        Args:
            max_concurrent: Maximum concurrent task executions.
                           Defaults to settings.queue_max_concurrent_tasks.
            default_timeout: Default timeout in seconds for task execution.
                            Defaults to settings.queue_task_timeout_seconds.
        """
        self._tasks: dict[str, asyncio.Task[None]] = {}
        self._max_concurrent = max_concurrent or settings.queue_max_concurrent_tasks
        self._default_timeout = default_timeout or settings.queue_task_timeout_seconds
        self._semaphore = asyncio.Semaphore(self._max_concurrent)

    def enqueue(
        self,
        run_id: str,
        coro: Callable[[], Coroutine[Any, Any, None]],
        timeout: int | None = None,
    ) -> None:
        """Enqueue a run for execution with concurrency control and timeout.

        Args:
            run_id: Run ID.
            coro: Coroutine to execute.
            timeout: Optional timeout override in seconds.
        """
        task_timeout = timeout or self._default_timeout

        async def wrapped_execution() -> None:
            """Execute with semaphore-based concurrency control and timeout."""
            async with self._semaphore:
                try:
                    await asyncio.wait_for(coro(), timeout=task_timeout)
                except TimeoutError:
                    logger.error(f"Task {run_id} timed out after {task_timeout}s")
                    raise
                except asyncio.CancelledError:
                    logger.info(f"Task {run_id} was cancelled")
                    raise
                except Exception as e:
                    logger.error(f"Task {run_id} failed with error: {e}")
                    raise
                finally:
                    # Cleanup completed task from memory if configured
                    if settings.queue_cleanup_completed_tasks:
                        self._cleanup_task(run_id)

        task: asyncio.Task[None] = asyncio.create_task(wrapped_execution())
        self._tasks[run_id] = task

    def _cleanup_task(self, run_id: str) -> None:
        """Remove completed task from internal tracking.

        Args:
            run_id: Run ID to clean up.
        """
        if run_id in self._tasks:
            del self._tasks[run_id]
            logger.debug(f"Cleaned up task {run_id} from queue")

    def cancel(self, run_id: str) -> bool:
        """Cancel a queued run.

        Args:
            run_id: Run ID.

        Returns:
            True if cancelled, False if not found or already completed.
        """
        task = self._tasks.get(run_id)
        if task and not task.done():
            task.cancel()
            return True
        return False

    def is_running(self, run_id: str) -> bool:
        """Check if a run is currently running.

        Args:
            run_id: Run ID.

        Returns:
            True if running.
        """
        task = self._tasks.get(run_id)
        return task is not None and not task.done()

    def get_queue_stats(self) -> dict[str, int]:
        """Get queue statistics for monitoring.

        Returns:
            Dictionary with queue statistics.
        """
        running = sum(1 for t in self._tasks.values() if not t.done())
        pending = len(self._tasks) - running
        return {
            "max_concurrent": self._max_concurrent,
            "running": running,
            "pending": pending,
            "total_tracked": len(self._tasks),
        }


@RoleRegistry.register("implementation")
class RunService(BaseRoleService[Run, RunCreate, ImplementationResult]):
    """Service for managing and executing runs (Implementation Role).

    Following the orchestrator management pattern, this service:
    - Creates worktrees for isolated execution
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
        # Determine isolation mode from settings
        self.use_clone_isolation = settings.use_clone_isolation
        self.workspace_adapter: WorkspaceAdapter
        if self.use_clone_isolation:
            self.workspace_adapter = CloneWorkspaceAdapter(self.workspace_service)
        else:
            self.workspace_adapter = WorktreeWorkspaceAdapter(self.git_service)

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

        This method supports two isolation modes:
        - Clone mode (use_clone_isolation=True): Uses git clone for workspace isolation.
          Better for remote sync and conflict resolution.
        - Worktree mode (use_clone_isolation=False): Uses git worktree for isolation.
          Faster but with more git operation constraints.

        In both modes, existing workspaces are reused for conversation continuation.

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

            # If clone isolation is enabled but the previous workspace is a worktree,
            # do not reuse it. We prefer clone-based isolation going forward.
            if self.use_clone_isolation:
                try:
                    worktrees_root = getattr(self.git_service, "worktrees_dir", None)
                except Exception:
                    worktrees_root = None

                if worktrees_root and str(workspace_path).startswith(str(worktrees_root)):
                    logger.info(
                        "Clone isolation enabled; skipping reuse of legacy worktree: %s",
                        workspace_path,
                    )
                    workspace_path = None  # Force fresh clone-based workspace

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
                    owner, repo_name = self._parse_github_url(repo.repo_url)
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
        """Execute a CLI-based run with automatic commit/push.

        Following the orchestrator management pattern:
        1. Execute CLI (file editing only)
        2. Stage all changes
        3. Get patch
        4. Commit (automatic)
        5. Push (automatic)
        6. Save results

        Args:
            run: Run object.
            worktree_info: WorktreeInfo object with path and branch info.
            executor_type: Type of CLI executor to use.
            resume_session_id: Optional session ID to resume a previous conversation.
            repo: Repository object for push operations.
        """
        logs: list[str] = []
        commit_sha: str | None = None

        # Map executor types to their executors and names
        executor_map: dict[
            ExecutorType, tuple[ClaudeCodeExecutor | CodexExecutor | GeminiExecutor, str]
        ] = {
            ExecutorType.CLAUDE_CODE: (self.claude_executor, "Claude Code"),
            ExecutorType.CODEX_CLI: (self.codex_executor, "Codex"),
            ExecutorType.GEMINI_CLI: (self.gemini_executor, "Gemini"),
        }

        executor, executor_name = executor_map[executor_type]

        # Track if we need to add conflict resolution instructions
        conflict_instruction: str | None = None

        try:
            # Update status to running
            await self.run_dao.update_status(run.id, RunStatus.RUNNING)
            logger.info(f"[{run.id[:8]}] Starting {executor_name} run")

            # Publish initial progress log so frontend can see activity
            await self._log_output(run.id, f"Starting {executor_name} execution...")

            # 0. Sync with remote (pull latest changes from remote branch)
            # This handles the case where the PR branch was updated on GitHub
            # (e.g., via "Update branch" button) and we need to incorporate those changes.
            if self.github_service and repo:
                try:
                    await self._log_output(run.id, "Checking for remote updates...")
                    owner, repo_name = self._parse_github_url(repo.repo_url)
                    auth_url = await self.github_service.get_auth_url(owner, repo_name)

                    is_behind = await self.workspace_adapter.is_behind_remote(
                        worktree_info.path,
                        branch=worktree_info.branch_name,
                        auth_url=auth_url,
                    )

                    if is_behind:
                        logger.info(
                            f"[{run.id[:8]}] Local branch is behind remote, "
                            "pulling latest changes..."
                        )
                        logs.append("Detected remote updates, pulling latest changes...")

                        sync_result = await self.workspace_adapter.sync_with_remote(
                            worktree_info.path,
                            branch=worktree_info.branch_name,
                            auth_url=auth_url,
                        )

                        if sync_result.success:
                            logs.append("Successfully pulled latest changes from remote")
                            logger.info(f"[{run.id[:8]}] Successfully pulled remote changes")
                        elif sync_result.has_conflicts:
                            # Conflicts detected - add resolution instructions for AI
                            conflict_files_str = ", ".join(sync_result.conflict_files)
                            logs.append(
                                f"Merge conflicts detected in: {conflict_files_str}. "
                                "AI will be asked to resolve them."
                            )
                            logger.warning(
                                f"[{run.id[:8]}] Merge conflicts detected: "
                                f"{sync_result.conflict_files}"
                            )
                            conflict_instruction = self._build_conflict_resolution_instruction(
                                sync_result.conflict_files
                            )
                        else:
                            logs.append(f"Pull failed: {sync_result.error}")
                            logger.warning(f"[{run.id[:8]}] Pull failed: {sync_result.error}")
                    else:
                        logger.info(f"[{run.id[:8]}] Branch is up to date with remote")

                except Exception as sync_error:
                    # Log but don't fail - we can still proceed with the run
                    logs.append(f"Remote sync warning: {sync_error}")
                    logger.warning(f"[{run.id[:8]}] Remote sync failed: {sync_error}")

            # 1. Record pre-execution status
            pre_status = await self.git_service.get_status(worktree_info.path)
            logs.append(f"Pre-execution status: {pre_status.has_changes} changes")

            logs.append(f"Starting {executor_name} execution in {worktree_info.path}")
            logs.append(f"Working branch: {worktree_info.branch_name}")
            # We proactively attempt to resume conversations via session_id when available.
            # If the CLI rejects the session (e.g., "already in use"), we retry once without it.

            # 2. Build instruction with constraints
            constraints = AgentConstraints()

            # Include conflict resolution instruction if conflicts were detected
            if conflict_instruction:
                instruction_with_constraints = (
                    f"{constraints.to_prompt()}\n\n"
                    f"{conflict_instruction}\n\n"
                    f"## Task\n{run.instruction}"
                )
            else:
                instruction_with_constraints = (
                    f"{constraints.to_prompt()}\n\n## Task\n{run.instruction}"
                )
            logger.info(
                f"[{run.id[:8]}] Instruction length: {len(instruction_with_constraints)} chars"
            )

            # 3. Execute the CLI (file editing only)
            logger.info(f"[{run.id[:8]}] Executing CLI...")
            await self._log_output(run.id, f"Launching {executor_name} CLI...")
            attempt_session_id = resume_session_id
            result = await executor.execute(
                worktree_path=worktree_info.path,
                instruction=instruction_with_constraints,
                on_output=lambda line: self._log_output(run.id, line),
                resume_session_id=attempt_session_id,
            )
            # Session error patterns that should trigger a retry without session continuation
            session_error_patterns = [
                "already in use",
                "in use",
                "no conversation found",
                "not found",
                "invalid session",
                "session expired",
            ]
            error_lower = result.error.lower() if result.error else ""
            if (
                not result.success
                and attempt_session_id
                and result.error
                and ("session" in error_lower)
                and any(pattern in error_lower for pattern in session_error_patterns)
            ):
                # Retry once without session continuation if the CLI rejects the session.
                logs.append(
                    f"Session continuation failed ({result.error}). Retrying without session_id."
                )
                result = await executor.execute(
                    worktree_path=worktree_info.path,
                    instruction=instruction_with_constraints,
                    on_output=lambda line: self._log_output(run.id, line),
                    resume_session_id=None,
                )
            logger.info(f"[{run.id[:8]}] CLI execution completed: success={result.success}")

            if not result.success:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error=result.error,
                    logs=logs + result.logs,
                    session_id=result.session_id or resume_session_id,
                )
                return

            # 4. Read and remove summary file (before staging)
            summary_from_file = await self._read_and_remove_summary_file(worktree_info.path, logs)

            # 5. Stage all changes
            await self.workspace_adapter.stage_all(worktree_info.path)

            # 6. Get patch
            patch = await self.workspace_adapter.get_diff(worktree_info.path, staged=True)

            # Skip commit/push if no changes
            if not patch.strip():
                logs.append("No changes detected, skipping commit/push")
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.SUCCEEDED,
                    summary="No changes made",
                    patch="",
                    files_changed=[],
                    logs=logs + result.logs,
                    session_id=result.session_id or resume_session_id,
                )
                return

            # Parse diff to get file changes
            files_changed = parse_unified_diff(patch)
            logs.append(f"Detected {len(files_changed)} changed file(s)")

            # Determine final summary (priority: file > CLI output > generated)
            final_summary = (
                summary_from_file or result.summary or self._generate_summary(files_changed)
            )

            # 7. Commit (automatic, use appropriate service)
            commit_message = self._generate_commit_message(run.instruction, final_summary)
            commit_message = await ensure_english_commit_message(
                commit_message,
                llm_router=self.llm_router,
                hint=final_summary or "",
            )
            commit_sha = await self.workspace_adapter.commit(
                worktree_info.path,
                message=commit_message,
            )
            logs.append(f"Committed: {commit_sha[:8]}")

            # 8. Push (automatic)
            if self.github_service and repo:
                owner, repo_name = self._parse_github_url(repo.repo_url)
                auth_url = await self.github_service.get_auth_url(owner, repo_name)

                push_result = await self.workspace_adapter.push(
                    worktree_info.path,
                    branch=worktree_info.branch_name,
                    auth_url=auth_url,
                )

                if push_result.success:
                    if push_result.required_pull:
                        logs.append(
                            f"Pulled remote changes and pushed to branch: "
                            f"{worktree_info.branch_name}"
                        )
                    else:
                        logs.append(f"Pushed to branch: {worktree_info.branch_name}")
                else:
                    logs.append(f"Push failed (will retry on PR creation): {push_result.error}")

            # 9. Save results
            await self.run_dao.update_status(
                run.id,
                RunStatus.SUCCEEDED,
                summary=final_summary,
                patch=patch,
                files_changed=files_changed,
                logs=logs + result.logs,
                warnings=result.warnings,
                session_id=result.session_id or resume_session_id,
                commit_sha=commit_sha,
            )

        except asyncio.CancelledError:
            # Task was cancelled (e.g., due to timeout or user cancellation)
            logger.warning(f"[{run.id[:8]}] CLI run was cancelled")
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error="Task was cancelled (timeout or user cancellation)",
                logs=logs + ["Execution cancelled"],
                commit_sha=commit_sha,
            )
            raise  # Re-raise to propagate cancellation

        except Exception as e:
            # Update status to failed
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error=str(e),
                logs=logs + [f"Execution failed: {str(e)}"],
                commit_sha=commit_sha,
            )

        finally:
            # Mark output stream as complete for SSE subscribers
            if self.output_manager:
                await self.output_manager.mark_complete(run.id)

    async def _read_and_remove_summary_file(
        self,
        worktree_path: Path,
        logs: builtins.list[str],
    ) -> str | None:
        """Read summary from the agent-generated summary file and remove it.

        The summary file is created by the agent at the end of execution.
        We read it before staging to use as the run summary, then delete it
        so it's not included in the commit.

        Args:
            worktree_path: Path to the worktree.
            logs: Log list to append to.

        Returns:
            Summary text if file exists, None otherwise.
        """
        summary_file = worktree_path / SUMMARY_FILE_PATH
        summary: str | None = None

        try:
            if summary_file.exists():
                summary = summary_file.read_text(encoding="utf-8").strip()
                logs.append(f"Read summary from {SUMMARY_FILE_PATH}")

                # Remove the file so it's not committed
                summary_file.unlink()
                logs.append(f"Removed {SUMMARY_FILE_PATH}")

                # Clean up empty summary
                if not summary:
                    summary = None
        except Exception as e:
            logs.append(f"Warning: Could not read summary file: {e}")

        return summary

    async def _log_output(self, run_id: str, line: str) -> None:
        """Log output from CLI execution.

        This logs output to console for debugging and publishes to
        OutputManager for SSE streaming to connected clients.

        Args:
            run_id: Run ID.
            line: Output line.
        """
        # Log to console for debugging
        logger.info(f"[{run_id[:8]}] {line}")

        # Publish to OutputManager for SSE streaming
        # Use await to ensure immediate delivery to subscribers
        if self.output_manager:
            await self.output_manager.publish_async(run_id, line)
        else:
            logger.warning(f"[{run_id[:8]}] OutputManager not available, cannot publish")

    def _generate_commit_message(self, instruction: str, summary: str | None) -> str:
        """Generate a commit message from instruction and summary.

        Args:
            instruction: Original user instruction.
            summary: Optional summary from executor.

        Returns:
            Commit message string.
        """
        # Use first line of instruction (truncate if too long)
        first_line = instruction.split("\n")[0][:72]
        if summary:
            return f"{first_line}\n\n{summary}"
        return first_line

    def _build_conflict_resolution_instruction(self, conflict_files: builtins.list[str]) -> str:
        """Build instruction for AI to resolve merge conflicts.

        Args:
            conflict_files: List of files with merge conflicts.

        Returns:
            Instruction string for conflict resolution.
        """
        files_list = "\n".join(f"- {f}" for f in conflict_files)
        return f"""## IMPORTANT: Merge Conflict Resolution Required

The following files have merge conflicts that MUST be resolved before proceeding with the task:

{files_list}

### Instructions for Conflict Resolution:
1. Open each conflicted file listed above
2. Look for conflict markers: `<<<<<<<`, `=======`, and `>>>>>>>`
3. Understand both versions of the conflicting code
4. Resolve each conflict by keeping the correct code (you may combine both versions if appropriate)
5. Remove ALL conflict markers completely
6. Ensure the resolved code is syntactically correct and functional

### Conflict Marker Format:
```
<<<<<<< HEAD
(your local changes)
=======
(incoming changes from remote)
>>>>>>> branch-name
```

After resolving ALL conflicts, proceed with the original task below.
"""

    def _parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Backward-compatible wrapper (use parse_github_owner_repo)."""
        return parse_github_owner_repo(repo_url)

    def _generate_summary(self, files_changed: builtins.list[FileDiff]) -> str:
        """Generate a human-readable summary of changes.

        Args:
            files_changed: List of changed files.

        Returns:
            Summary string.
        """
        if not files_changed:
            return "No files were modified."

        total_added = sum(f.added_lines for f in files_changed)
        total_removed = sum(f.removed_lines for f in files_changed)

        summary_parts = [
            f"Modified {len(files_changed)} file(s)",
            f"+{total_added} -{total_removed} lines",
        ]

        # List files
        file_list = ", ".join(f.path for f in files_changed[:5])
        if len(files_changed) > 5:
            file_list += f" and {len(files_changed) - 5} more"

        summary_parts.append(f"Files: {file_list}")

        return ". ".join(summary_parts) + "."

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

    async def list_by_task(self, task_id: str) -> builtins.list[Run]:
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
