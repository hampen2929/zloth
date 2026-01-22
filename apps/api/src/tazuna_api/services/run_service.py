"""Run execution service.

This service manages the execution of AI Agent runs following the
orchestrator management pattern where tazuna centrally manages git
operations while AI Agents only edit files.
"""

from __future__ import annotations

import asyncio
import builtins
import logging
import re
from collections.abc import Callable, Coroutine
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tazuna_api.agents.llm_router import LLMConfig, LLMRouter
from tazuna_api.agents.patch_agent import PatchAgent
from tazuna_api.config import settings
from tazuna_api.domain.enums import ExecutorType, RoleExecutionStatus, RunStatus
from tazuna_api.domain.models import (
    SUMMARY_FILE_PATH,
    AgentConstraints,
    AgentRequest,
    FileDiff,
    ImplementationResult,
    Run,
    RunCreate,
)
from tazuna_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from tazuna_api.executors.codex_executor import CodexExecutor, CodexOptions
from tazuna_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from tazuna_api.roles.base_service import BaseRoleService
from tazuna_api.roles.registry import RoleRegistry
from tazuna_api.services.commit_message import ensure_english_commit_message
from tazuna_api.services.git_service import GitService
from tazuna_api.services.model_service import ModelService
from tazuna_api.services.repo_service import RepoService
from tazuna_api.services.workspace_service import WorkspaceService
from tazuna_api.storage.dao import RunDAO, TaskDAO, UserPreferencesDAO

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from tazuna_api.services.github_service import GitHubService
    from tazuna_api.services.output_manager import OutputManager


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
        model_service: ModelService,
        repo_service: RepoService,
        git_service: GitService | None = None,
        user_preferences_dao: UserPreferencesDAO | None = None,
        github_service: GitHubService | None = None,
        output_manager: OutputManager | None = None,
        workspace_service: WorkspaceService | None = None,
    ):
        # Initialize base class with output manager and executors
        super().__init__(output_manager=output_manager)

        self.run_dao = run_dao
        self.task_dao = task_dao
        self.model_service = model_service
        self.repo_service = repo_service
        self.git_service = git_service or GitService()
        self.workspace_service = workspace_service or WorkspaceService()
        self.user_preferences_dao = user_preferences_dao
        self.github_service = github_service
        # Note: self.output_manager is set by base class
        self.queue = QueueAdapter()
        self.llm_router = LLMRouter()
        # Note: Executors are also available via self._executors from base class
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.codex_executor = CodexExecutor(CodexOptions(codex_cli_path=settings.codex_cli_path))
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
        )

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
            raise ValueError(f"Task not found: {task_id}")

        # Get repo for workspace
        repo = await self.repo_service.get(task.repo_id)
        if not repo:
            raise ValueError(f"Repo not found: {task.repo_id}")

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

                # Enqueue for execution
                def make_patch_agent_coro(
                    r: Run, rp: Any
                ) -> Callable[[], Coroutine[Any, Any, None]]:
                    return lambda: self._execute_patch_agent_run(r, rp)

                self.queue.enqueue(
                    run.id,
                    make_patch_agent_coro(run, repo),
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

        This method reuses an existing workspace/branch for the same task and
        executor type to enable conversation continuation in the same working
        directory. Only creates a new workspace if none exists.

        Supports two isolation modes:
        - Clone mode (default): Full git clone for better remote sync and conflict resolution
        - Worktree mode (legacy): Git worktree for faster creation and less disk space

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
        from tazuna_api.services.git_service import WorktreeInfo
        from tazuna_api.services.workspace_service import WorkspaceInfo

        # Get the latest session ID for this task and executor type
        # This enables conversation persistence across multiple runs
        previous_session_id = await self.run_dao.get_latest_session_id(
            task_id=task_id,
            executor_type=executor_type,
        )

        # Check for existing workspace to reuse
        existing_run = await self.run_dao.get_latest_worktree_run(
            task_id=task_id,
            executor_type=executor_type,
        )

        workspace_info: WorkspaceInfo | WorktreeInfo | None = None
        use_clone_mode = settings.use_clone_isolation

        if existing_run and existing_run.worktree_path:
            workspace_path = Path(existing_run.worktree_path)

            # Verify workspace is still valid
            if use_clone_mode:
                is_valid = await self.workspace_service.is_valid_workspace(workspace_path)
            else:
                is_valid = await self.git_service.is_valid_worktree(workspace_path)

            if is_valid:
                # If we're working from the repo's default branch, check freshness
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
                            "Existing workspace is behind latest default; creating a new one "
                            f"(workspace={workspace_path}, default={default_ref})"
                        )
                    else:
                        if use_clone_mode:
                            workspace_info = WorkspaceInfo(
                                path=workspace_path,
                                branch_name=existing_run.working_branch or "",
                                base_branch=existing_run.base_ref or base_ref,
                                created_at=existing_run.created_at,
                            )
                        else:
                            workspace_info = WorktreeInfo(
                                path=workspace_path,
                                branch_name=existing_run.working_branch or "",
                                base_branch=existing_run.base_ref or base_ref,
                                created_at=existing_run.created_at,
                            )
                        logger.info(f"Reusing existing workspace: {workspace_path}")
                else:
                    # Reuse existing workspace
                    if use_clone_mode:
                        workspace_info = WorkspaceInfo(
                            path=workspace_path,
                            branch_name=existing_run.working_branch or "",
                            base_branch=existing_run.base_ref or base_ref,
                            created_at=existing_run.created_at,
                        )
                    else:
                        workspace_info = WorktreeInfo(
                            path=workspace_path,
                            branch_name=existing_run.working_branch or "",
                            base_branch=existing_run.base_ref or base_ref,
                            created_at=existing_run.created_at,
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
                # Apply custom workspaces_dir from UserPreferences if set
                if prefs and prefs.worktrees_dir:
                    if use_clone_mode:
                        self.workspace_service.set_workspaces_dir(prefs.worktrees_dir)
                    else:
                        self.git_service.set_worktrees_dir(prefs.worktrees_dir)

            # Get auth_url for private repos
            auth_url: str | None = None
            if self.github_service and repo.repo_url:
                try:
                    owner, repo_name = self._parse_github_url(repo.repo_url)
                    auth_url = await self.github_service.get_auth_url(owner, repo_name)
                except Exception as e:
                    logger.warning(f"Could not get auth_url for workspace: {e}")

            # Create new workspace based on isolation mode
            if use_clone_mode:
                workspace_info = await self.workspace_service.create_workspace(
                    repo=repo,
                    base_branch=base_ref,
                    run_id=run.id,
                    branch_prefix=branch_prefix,
                    auth_url=auth_url,
                    shallow=True,  # Use shallow clone for speed
                )
                logger.info(f"Created clone-based workspace: {workspace_info.path}")
            else:
                workspace_info = await self.git_service.create_worktree(
                    repo=repo,
                    base_branch=base_ref,
                    run_id=run.id,
                    branch_prefix=branch_prefix,
                    auth_url=auth_url,
                )
                logger.info(f"Created worktree-based workspace: {workspace_info.path}")

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

        # Enqueue for execution based on executor type
        def make_coro(
            r: Run, ws: Any, et: ExecutorType, ps: str | None, rp: Any
        ) -> Callable[[], Coroutine[Any, Any, None]]:
            return lambda: self._execute_cli_run(r, ws, et, ps, rp)

        self.queue.enqueue(
            updated_run.id,
            make_coro(updated_run, workspace_info, executor_type, previous_session_id, repo),
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

    async def cancel(self, run_id: str) -> bool:
        """Cancel a run.

        Args:
            run_id: Run ID.

        Returns:
            True if cancelled.
        """
        run = await self.run_dao.get(run_id)
        cancelled = self.queue.cancel(run_id)

        if cancelled:
            await self.run_dao.update_status(run_id, RunStatus.CANCELED)

            # Cleanup worktree if it's a CLI executor run
            cli_executors = {
                ExecutorType.CLAUDE_CODE,
                ExecutorType.CODEX_CLI,
                ExecutorType.GEMINI_CLI,
            }
            if run and run.executor_type in cli_executors and run.worktree_path:
                await self.git_service.cleanup_worktree(
                    Path(run.worktree_path),
                    delete_branch=True,
                )

        return cancelled

    async def cleanup_worktree(self, run_id: str) -> bool:
        """Clean up the worktree for a run.

        Args:
            run_id: Run ID.

        Returns:
            True if cleanup was successful.
        """
        run = await self.run_dao.get(run_id)
        if not run or not run.worktree_path:
            return False

        await self.git_service.cleanup_worktree(
            Path(run.worktree_path),
            delete_branch=False,  # Keep branch for PR
        )
        return True

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
        workspace_info: Any,
        executor_type: ExecutorType,
        resume_session_id: str | None = None,
        repo: Any = None,
    ) -> None:
        """Execute a CLI-based run with automatic commit/push.

        Following the orchestrator management pattern:
        1. Sync with remote (pull or merge base branch if needed)
        2. Execute CLI (file editing only)
        3. Stage all changes
        4. Get patch
        5. Commit (automatic)
        6. Push (automatic)
        7. Save results

        Args:
            run: Run object.
            workspace_info: WorkspaceInfo or WorktreeInfo with path and branch info.
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
            use_clone_mode = settings.use_clone_isolation
            if self.github_service and repo:
                try:
                    await self._log_output(run.id, "Checking for remote updates...")
                    owner, repo_name = self._parse_github_url(repo.repo_url)
                    auth_url = await self.github_service.get_auth_url(owner, repo_name)

                    # Check if we're behind remote (works for both clone and worktree)
                    if use_clone_mode:
                        is_behind = await self.workspace_service.is_behind_remote(
                            workspace_info.path,
                            workspace_info.branch_name,
                            auth_url=auth_url,
                        )
                    else:
                        is_behind = await self.git_service.is_behind_remote(
                            workspace_info.path,
                            workspace_info.branch_name,
                            auth_url=auth_url,
                        )

                    if is_behind:
                        logger.info(
                            f"[{run.id[:8]}] Local branch is behind remote, "
                            "pulling latest changes..."
                        )
                        logs.append("Detected remote updates, pulling latest changes...")
                        await self._log_output(run.id, "Pulling latest changes from remote...")

                        if use_clone_mode:
                            # Use WorkspaceService for clone-based sync
                            sync_result = await self.workspace_service.sync_with_remote(
                                workspace_info.path,
                                branch=workspace_info.branch_name,
                                auth_url=auth_url,
                            )
                            if sync_result.success:
                                logs.append(
                                    f"Successfully pulled {sync_result.commits_pulled} "
                                    "commit(s) from remote"
                                )
                                logger.info(f"[{run.id[:8]}] Successfully pulled remote changes")
                            else:
                                logs.append(f"Sync warning: {sync_result.error}")
                                logger.warning(f"[{run.id[:8]}] Sync failed: {sync_result.error}")
                        else:
                            # Use GitService for worktree-based sync
                            pull_result = await self.git_service.pull(
                                workspace_info.path,
                                branch=workspace_info.branch_name,
                                auth_url=auth_url,
                            )

                            if pull_result.success:
                                logs.append("Successfully pulled latest changes from remote")
                                logger.info(f"[{run.id[:8]}] Successfully pulled remote changes")
                            elif pull_result.has_conflicts:
                                conflict_files_str = ", ".join(pull_result.conflict_files)
                                logs.append(
                                    f"Merge conflicts detected in: {conflict_files_str}. "
                                    "AI will be asked to resolve them."
                                )
                                logger.warning(
                                    f"[{run.id[:8]}] Merge conflicts detected: "
                                    f"{pull_result.conflict_files}"
                                )
                                conflict_instruction = self._build_conflict_resolution_instruction(
                                    pull_result.conflict_files
                                )
                            else:
                                logs.append(f"Pull failed: {pull_result.error}")
                                logger.warning(f"[{run.id[:8]}] Pull failed: {pull_result.error}")
                    else:
                        logger.info(f"[{run.id[:8]}] Branch is up to date with remote")

                    # Check if instruction contains conflict resolution request
                    # This handles the case where user explicitly asks to resolve conflicts
                    # with the base branch (main/master)
                    if use_clone_mode and self._is_conflict_resolution_request(run.instruction):
                        await self._log_output(
                            run.id, f"Merging base branch ({workspace_info.base_branch})..."
                        )
                        logs.append(f"Merging base branch: {workspace_info.base_branch}")

                        merge_result = await self.workspace_service.merge_base_branch(
                            workspace_info.path,
                            base_branch=workspace_info.base_branch,
                            auth_url=auth_url,
                        )

                        if merge_result.success:
                            logs.append("Successfully merged base branch (no conflicts)")
                            logger.info(f"[{run.id[:8]}] Merged base branch successfully")
                        elif (
                            merge_result.conflict_info
                            and merge_result.conflict_info.has_conflicts
                        ):
                            conflict_files = merge_result.conflict_info.conflict_files
                            conflict_files_str = ", ".join(conflict_files)
                            logs.append(
                                f"Merge conflicts with base branch in: {conflict_files_str}. "
                                "AI will resolve them."
                            )
                            logger.warning(
                                f"[{run.id[:8]}] Base branch conflicts: {conflict_files}"
                            )
                            await self._log_output(
                                run.id,
                                f"Conflict detected in {len(conflict_files)} file(s). "
                                "AI will resolve...",
                            )
                            conflict_instruction = self._build_base_conflict_resolution_instruction(
                                conflict_files,
                                workspace_info.base_branch,
                            )
                        else:
                            logs.append(f"Base merge failed: {merge_result.error}")
                            logger.warning(
                                f"[{run.id[:8]}] Base merge failed: {merge_result.error}"
                            )

                except Exception as sync_error:
                    # Log but don't fail - we can still proceed with the run
                    logs.append(f"Remote sync warning: {sync_error}")
                    logger.warning(f"[{run.id[:8]}] Remote sync failed: {sync_error}")

            # 1. Record pre-execution status
            pre_status = await self.git_service.get_status(workspace_info.path)
            logs.append(f"Pre-execution status: {pre_status.has_changes} changes")

            logs.append(f"Starting {executor_name} execution in {workspace_info.path}")
            logs.append(f"Working branch: {workspace_info.branch_name}")
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
                worktree_path=workspace_info.path,
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
                    worktree_path=workspace_info.path,
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
            summary_from_file = await self._read_and_remove_summary_file(workspace_info.path, logs)

            # 5. Stage all changes
            await self.git_service.stage_all(workspace_info.path)

            # 6. Get patch
            patch = await self.git_service.get_diff(workspace_info.path, staged=True)

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
            files_changed = self._parse_diff(patch)
            logs.append(f"Detected {len(files_changed)} changed file(s)")

            # Determine final summary (priority: file > CLI output > generated)
            final_summary = (
                summary_from_file or result.summary or self._generate_summary(files_changed)
            )

            # 7. Commit (automatic)
            commit_message = self._generate_commit_message(run.instruction, final_summary)
            commit_message = await ensure_english_commit_message(
                commit_message,
                llm_router=self.llm_router,
                hint=final_summary or "",
            )
            commit_sha = await self.git_service.commit(
                workspace_info.path,
                message=commit_message,
            )
            logs.append(f"Committed: {commit_sha[:8]}")

            # 8. Push (automatic) with retry on non-fast-forward
            if self.github_service and repo:
                owner, repo_name = self._parse_github_url(repo.repo_url)
                auth_url = await self.github_service.get_auth_url(owner, repo_name)
                push_result = await self.git_service.push_with_retry(
                    workspace_info.path,
                    branch=workspace_info.branch_name,
                    auth_url=auth_url,
                )

                if push_result.success:
                    if push_result.required_pull:
                        logs.append(
                            f"Pulled remote changes and pushed to branch: "
                            f"{workspace_info.branch_name}"
                        )
                    else:
                        logs.append(f"Pushed to branch: {workspace_info.branch_name}")
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

    def _parse_diff(self, diff: str) -> builtins.list[FileDiff]:
        """Parse unified diff to extract file change information.

        Args:
            diff: Unified diff string.

        Returns:
            List of FileDiff objects.
        """
        files: builtins.list[FileDiff] = []
        current_file: str | None = None
        current_patch_lines: builtins.list[str] = []
        added_lines = 0
        removed_lines = 0

        for line in diff.split("\n"):
            if line.startswith("--- a/"):
                # Save previous file if exists
                if current_file:
                    files.append(
                        FileDiff(
                            path=current_file,
                            added_lines=added_lines,
                            removed_lines=removed_lines,
                            patch="\n".join(current_patch_lines),
                        )
                    )
                # Reset for new file
                current_patch_lines = [line]
                added_lines = 0
                removed_lines = 0
            elif line.startswith("+++ b/"):
                current_file = line[6:]
                current_patch_lines.append(line)
            elif line.startswith("--- /dev/null"):
                # New file
                current_patch_lines = [line]
                added_lines = 0
                removed_lines = 0
            elif line.startswith("+++ b/") and current_file is None:
                # New file path
                current_file = line[6:]
                current_patch_lines.append(line)
            elif current_file:
                current_patch_lines.append(line)
                if line.startswith("+") and not line.startswith("+++"):
                    added_lines += 1
                elif line.startswith("-") and not line.startswith("---"):
                    removed_lines += 1

        # Save last file
        if current_file:
            files.append(
                FileDiff(
                    path=current_file,
                    added_lines=added_lines,
                    removed_lines=removed_lines,
                    patch="\n".join(current_patch_lines),
                )
            )

        return files

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

    def _build_base_conflict_resolution_instruction(
        self,
        conflict_files: builtins.list[str],
        base_branch: str,
    ) -> str:
        """Build instruction for AI to resolve conflicts with base branch.

        This is used when merging the base branch (e.g., main) into the feature
        branch to resolve conflicts before creating/updating a PR.

        Args:
            conflict_files: List of files with merge conflicts.
            base_branch: Name of the base branch (e.g., 'main').

        Returns:
            Instruction string for conflict resolution.
        """
        files_list = "\n".join(f"- {f}" for f in conflict_files)
        return f"""## CRITICAL: Base Branch Conflict Resolution Required

The base branch (`{base_branch}`) has been merged into this branch, but there are
conflicts that MUST be resolved before proceeding:

**Conflicted Files:**
{files_list}

### Resolution Instructions:
1. Open each conflicted file
2. Find conflict markers: `<<<<<<<`, `=======`, and `>>>>>>>`
3. The sections mean:
   - Between `<<<<<<< HEAD` and `=======`: Your current feature branch changes
   - Between `=======` and `>>>>>>> origin/{base_branch}`: Changes from the base branch
4. Resolve each conflict by:
   - Keeping your changes if they are correct
   - Keeping base branch changes if they are correct
   - Combining both if appropriate
5. Remove ALL conflict markers completely
6. Ensure the code is syntactically correct and functional

### After Resolution:
Once all conflicts are resolved, proceed with the original task. The resolved
changes will be committed and pushed automatically.

**Important:** Do NOT run `git add` or `git commit` - the system handles this automatically.
"""

    def _is_conflict_resolution_request(self, instruction: str) -> bool:
        """Check if the instruction is requesting conflict resolution with base branch.

        Args:
            instruction: The user's instruction.

        Returns:
            True if the instruction appears to be a conflict resolution request.
        """
        instruction_lower = instruction.lower()
        conflict_keywords = [
            "conflict",
            "コンフリクト",
            "衝突",
            "merge",
            "マージ",
            "rebase",
            "リベース",
            "main",
            "master",
            "base branch",
            "ベースブランチ",
            "update branch",
        ]
        resolution_keywords = [
            "resolve",
            "解決",
            "解消",
            "fix",
            "修正",
            "更新",
            "sync",
            "同期",
        ]

        has_conflict_keyword = any(kw in instruction_lower for kw in conflict_keywords)
        has_resolution_keyword = any(kw in instruction_lower for kw in resolution_keywords)

        return has_conflict_keyword and has_resolution_keyword

    def _parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Parse GitHub URL to extract owner and repo name.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            Tuple of (owner, repo_name).

        Raises:
            ValueError: If URL cannot be parsed.
        """
        # Handle various URL formats:
        # - https://github.com/owner/repo.git
        # - https://github.com/owner/repo
        # - git@github.com:owner/repo.git
        patterns = [
            r"github\.com[:/]([^/]+)/([^/.]+)(?:\.git)?$",
        ]
        for pattern in patterns:
            match = re.search(pattern, repo_url)
            if match:
                return match.group(1), match.group(2)
        raise ValueError(f"Could not parse GitHub URL: {repo_url}")

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
