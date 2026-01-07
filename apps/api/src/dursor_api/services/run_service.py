"""Run execution service."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from dursor_api.agents.llm_router import LLMConfig, LLMRouter
from dursor_api.agents.patch_agent import PatchAgent
from dursor_api.config import settings
from dursor_api.domain.enums import ExecutorType, RunStatus
from dursor_api.domain.models import AgentConstraints, AgentRequest, Run, RunCreate
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor, ClaudeCodeOptions
from dursor_api.executors.codex_executor import CodexExecutor, CodexOptions
from dursor_api.executors.gemini_executor import GeminiExecutor, GeminiOptions
from dursor_api.services.model_service import ModelService
from dursor_api.services.repo_service import RepoService
from dursor_api.services.worktree_service import WorktreeService
from dursor_api.storage.dao import RunDAO, TaskDAO


class QueueAdapter:
    """Simple in-memory queue adapter for v0.1.

    Can be replaced with Celery/RQ/Redis in v0.2+.
    """

    def __init__(self):
        self._tasks: dict[str, asyncio.Task] = {}

    def enqueue(
        self,
        run_id: str,
        coro: Callable[[], Awaitable[None]],
    ) -> None:
        """Enqueue a run for execution.

        Args:
            run_id: Run ID.
            coro: Coroutine to execute.
        """
        task = asyncio.create_task(coro())
        self._tasks[run_id] = task

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


class RunService:
    """Service for managing and executing runs."""

    def __init__(
        self,
        run_dao: RunDAO,
        task_dao: TaskDAO,
        model_service: ModelService,
        repo_service: RepoService,
        worktree_service: WorktreeService | None = None,
    ):
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.model_service = model_service
        self.repo_service = repo_service
        self.worktree_service = worktree_service or WorktreeService()
        self.queue = QueueAdapter()
        self.llm_router = LLMRouter()
        self.claude_executor = ClaudeCodeExecutor(
            ClaudeCodeOptions(claude_cli_path=settings.claude_cli_path)
        )
        self.codex_executor = CodexExecutor(
            CodexOptions(codex_cli_path=settings.codex_cli_path)
        )
        self.gemini_executor = GeminiExecutor(
            GeminiOptions(gemini_cli_path=settings.gemini_cli_path)
        )

    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        """Create runs for multiple models or Claude Code.

        Args:
            task_id: Task ID.
            data: Run creation data with model IDs or executor type.

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

        runs = []

        # Lock executor after the first run in the task.
        # Users expect "resume" style conversations to keep using the initially chosen executor.
        existing_runs = await self.run_dao.list(task_id)
        locked_executor: ExecutorType | None = None
        if existing_runs:
            # DAO returns newest-first; the earliest run is last.
            locked_executor = existing_runs[-1].executor_type
            if data.executor_type != locked_executor:
                data = data.model_copy(update={"executor_type": locked_executor})

        if data.executor_type == ExecutorType.CLAUDE_CODE:
            # Create a single Claude Code run
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=ExecutorType.CLAUDE_CODE,
            )
            runs.append(run)
        elif data.executor_type == ExecutorType.CODEX_CLI:
            # Create a single Codex CLI run
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=ExecutorType.CODEX_CLI,
            )
            runs.append(run)
        elif data.executor_type == ExecutorType.GEMINI_CLI:
            # Create a single Gemini CLI run
            run = await self._create_cli_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
                executor_type=ExecutorType.GEMINI_CLI,
            )
            runs.append(run)
        else:
            # Create runs for each model (PatchAgent)
            model_ids = data.model_ids
            if not model_ids:
                # If the task is already locked to patch_agent, reuse the most recent
                # model set (grouped by latest patch_agent instruction).
                patch_runs = [r for r in existing_runs if r.executor_type == ExecutorType.PATCH_AGENT]
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
                    model_id=model_id,
                    model_name=model.model_name,
                    provider=model.provider,
                    base_ref=data.base_ref or repo.default_branch,
                )
                runs.append(run)

                # Enqueue for execution
                self.queue.enqueue(
                    run.id,
                    lambda r=run, rp=repo: self._execute_patch_agent_run(r, rp),
                )

        return runs

    async def _create_cli_run(
        self,
        task_id: str,
        repo: Any,
        instruction: str,
        base_ref: str,
        executor_type: ExecutorType,
    ) -> Run:
        """Create and start a CLI-based run (Claude Code, Codex, or Gemini).

        Args:
            task_id: Task ID.
            repo: Repository object.
            instruction: Natural language instruction.
            base_ref: Base branch to work from.
            executor_type: Type of CLI executor to use.

        Returns:
            Created Run object.
        """
        # Get the latest session ID for this task and executor type
        # This enables conversation persistence across multiple runs
        previous_session_id = await self.run_dao.get_latest_session_id(
            task_id=task_id,
            executor_type=executor_type,
        )

        # Create the run record first (without worktree info)
        run = await self.run_dao.create(
            task_id=task_id,
            instruction=instruction,
            executor_type=executor_type,
            base_ref=base_ref,
        )

        # Create worktree for this run
        worktree_info = await self.worktree_service.create_worktree(
            repo=repo,
            base_branch=base_ref,
            run_id=run.id,
        )

        # Update run with worktree info
        await self.run_dao.update_worktree(
            run.id,
            working_branch=worktree_info.branch_name,
            worktree_path=str(worktree_info.path),
        )

        # Update the run object with new info
        run = await self.run_dao.get(run.id)

        # Enqueue for execution based on executor type
        self.queue.enqueue(
            run.id,
            lambda r=run, wt=worktree_info, et=executor_type, ps=previous_session_id: self._execute_cli_run(
                r, wt, et, ps
            ),
        )

        return run

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
                await self.worktree_service.cleanup_worktree(
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

        await self.worktree_service.cleanup_worktree(
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
        worktree_info: Any,
        executor_type: ExecutorType,
        resume_session_id: str | None = None,
    ) -> None:
        """Execute a CLI-based run (Claude Code, Codex, or Gemini).

        Args:
            run: Run object.
            worktree_info: WorktreeInfo object with path and branch info.
            executor_type: Type of CLI executor to use.
            resume_session_id: Optional session ID to resume a previous conversation.
        """
        logs: list[str] = []

        # Map executor types to their executors and names
        executor_map = {
            ExecutorType.CLAUDE_CODE: (self.claude_executor, "Claude Code"),
            ExecutorType.CODEX_CLI: (self.codex_executor, "Codex"),
            ExecutorType.GEMINI_CLI: (self.gemini_executor, "Gemini"),
        }

        executor, executor_name = executor_map[executor_type]

        try:
            # Update status to running
            await self.run_dao.update_status(run.id, RunStatus.RUNNING)

            logs.append(f"Starting {executor_name} execution in {worktree_info.path}")
            logs.append(f"Working branch: {worktree_info.branch_name}")
            if resume_session_id:
                logs.append(f"Resuming session: {resume_session_id}")

            # Execute the CLI with session persistence
            result = await executor.execute(
                worktree_path=worktree_info.path,
                instruction=run.instruction,
                on_output=lambda line: self._log_output(run.id, line),
                resume_session_id=resume_session_id,
            )

            # Save the session ID from the result for future runs
            if result.session_id:
                await self.run_dao.update_session_id(run.id, result.session_id)

            if result.success:
                # Update run with results
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.SUCCEEDED,
                    summary=result.summary,
                    patch=result.patch,
                    files_changed=result.files_changed,
                    logs=logs + result.logs,
                    warnings=result.warnings,
                )
            else:
                await self.run_dao.update_status(
                    run.id,
                    RunStatus.FAILED,
                    error=result.error,
                    logs=logs + result.logs,
                )

            # Note: We don't cleanup the worktree here
            # It stays for PR creation or manual cleanup

        except Exception as e:
            # Update status to failed
            await self.run_dao.update_status(
                run.id,
                RunStatus.FAILED,
                error=str(e),
                logs=logs + [f"Execution failed: {str(e)}"],
            )

    async def _log_output(self, run_id: str, line: str) -> None:
        """Log output from Claude Code execution.

        This is a placeholder for streaming support.
        In the future, this could emit SSE events.

        Args:
            run_id: Run ID.
            line: Output line.
        """
        # For now, just log to console
        # TODO: Implement SSE streaming for real-time output
        pass
