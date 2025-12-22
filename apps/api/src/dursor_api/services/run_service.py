"""Run execution service."""

import asyncio
from collections.abc import Callable, Awaitable
from pathlib import Path
from typing import Any

from dursor_api.agents.llm_router import LLMClient, LLMConfig, LLMRouter
from dursor_api.agents.patch_agent import PatchAgent
from dursor_api.domain.enums import Provider, RunStatus
from dursor_api.domain.models import AgentConstraints, AgentRequest, Run, RunCreate
from dursor_api.services.model_service import ModelService
from dursor_api.services.repo_service import RepoService
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
    ):
        self.run_dao = run_dao
        self.task_dao = task_dao
        self.model_service = model_service
        self.repo_service = repo_service
        self.queue = QueueAdapter()
        self.llm_router = LLMRouter()

    async def create_runs(self, task_id: str, data: RunCreate) -> list[Run]:
        """Create runs for multiple models.

        Args:
            task_id: Task ID.
            data: Run creation data with model IDs.

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
        for model_id in data.model_ids:
            # Verify model exists and get model info
            model = await self.model_service.get(model_id)
            if not model:
                raise ValueError(f"Model not found: {model_id}")

            # Create run record with denormalized model info
            run = await self.run_dao.create(
                task_id=task_id,
                model_id=model_id,
                model_name=model.model_name,
                provider=model.provider,
                instruction=data.instruction,
                base_ref=data.base_ref or repo.default_branch,
            )
            runs.append(run)

            # Enqueue for execution
            self.queue.enqueue(
                run.id,
                lambda r=run, rp=repo: self._execute_run(r, rp),
            )

        return runs

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
        cancelled = self.queue.cancel(run_id)
        if cancelled:
            await self.run_dao.update_status(run_id, RunStatus.CANCELED)
        return cancelled

    async def _execute_run(self, run: Run, repo: Any) -> None:
        """Execute a single run.

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
