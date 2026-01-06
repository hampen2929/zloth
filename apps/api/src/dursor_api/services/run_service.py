"""Run execution service."""

import asyncio
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from dursor_api.agents.llm_router import LLMConfig, LLMRouter
from dursor_api.agents.patch_agent import PatchAgent
from dursor_api.domain.enums import ExecutorType, RunStatus
from dursor_api.domain.models import AgentConstraints, AgentRequest, Run, RunCreate
from dursor_api.executors.claude_code_executor import ClaudeCodeExecutor
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
        self.claude_executor = ClaudeCodeExecutor()

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

        if data.executor_type == ExecutorType.CLAUDE_CODE:
            # Create a single Claude Code run
            run = await self._create_claude_code_run(
                task_id=task_id,
                repo=repo,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
            )
            runs.append(run)
        else:
            # Create runs for each model (PatchAgent)
            if not data.model_ids:
                raise ValueError("model_ids required for patch_agent executor")

            for model_id in data.model_ids:
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

    async def _create_claude_code_run(
        self,
        task_id: str,
        repo: Any,
        instruction: str,
        base_ref: str,
    ) -> Run:
        """Create and start a Claude Code run.

        Args:
            task_id: Task ID.
            repo: Repository object.
            instruction: Natural language instruction.
            base_ref: Base branch to work from.

        Returns:
            Created Run object.
        """
        # Create the run record first (without worktree info)
        run = await self.run_dao.create(
            task_id=task_id,
            instruction=instruction,
            executor_type=ExecutorType.CLAUDE_CODE,
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

        # Enqueue for execution
        self.queue.enqueue(
            run.id,
            lambda r=run, wt=worktree_info: self._execute_claude_code_run(r, wt),
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

            # Cleanup worktree if it's a Claude Code run
            if run and run.executor_type == ExecutorType.CLAUDE_CODE and run.worktree_path:
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

    async def _execute_claude_code_run(self, run: Run, worktree_info: Any) -> None:
        """Execute a Claude Code run.

        Args:
            run: Run object.
            worktree_info: WorktreeInfo object with path and branch info.
        """
        logs: list[str] = []

        try:
            # Update status to running
            await self.run_dao.update_status(run.id, RunStatus.RUNNING)

            logs.append(f"Starting Claude Code execution in {worktree_info.path}")
            logs.append(f"Working branch: {worktree_info.branch_name}")

            # Execute Claude Code
            result = await self.claude_executor.execute(
                worktree_path=worktree_info.path,
                instruction=run.instruction,
                on_output=lambda line: self._log_output(run.id, line),
            )

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
