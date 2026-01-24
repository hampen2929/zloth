"""SQLite-backed job worker.

This module provides a lightweight persistent queue implementation that stores
jobs in the existing SQLite database and processes them in the background.

Design goals:
- Survive process restarts (queued jobs are not lost)
- Concurrency control via semaphore
- Best-effort cancellation for running jobs
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable

from zloth_api.config import settings
from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job
from zloth_api.storage.dao import JobDAO

logger = logging.getLogger(__name__)

JobHandler = Callable[[Job], Awaitable[None]]


class JobWorker:
    """Background worker that polls SQLite for jobs and executes handlers."""

    def __init__(
        self,
        *,
        job_dao: JobDAO,
        handlers: dict[JobKind, JobHandler],
        max_concurrent: int | None = None,
        poll_interval_seconds: float = 1.0,
    ) -> None:
        self._job_dao = job_dao
        self._handlers = handlers
        self._max_concurrent = max_concurrent or settings.queue_max_concurrent_tasks
        self._poll_interval_seconds = poll_interval_seconds
        self._worker_id = f"worker-{uuid.uuid4().hex[:12]}"

        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Job ID -> running task
        self._running: dict[str, asyncio.Task[None]] = {}

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def start(self) -> None:
        """Start the background polling loop."""
        if self._loop_task and not self._loop_task.done():
            return
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info("JobWorker started (%s)", self._worker_id)

    async def stop(self) -> None:
        """Stop the worker and cancel running jobs."""
        self._stop_event.set()

        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        # Cancel running jobs best-effort
        for task in list(self._running.values()):
            if not task.done():
                task.cancel()
        if self._running:
            await asyncio.gather(*self._running.values(), return_exceptions=True)
        self._running.clear()
        logger.info("JobWorker stopped (%s)", self._worker_id)

    async def cancel_ref(self, *, kind: JobKind, ref_id: str) -> bool:
        """Cancel a queued job, and best-effort cancel a running job."""
        cancelled = await self._job_dao.cancel_queued_by_ref(kind=kind, ref_id=ref_id)
        running_job = await self._job_dao.get_latest_by_ref(kind=kind, ref_id=ref_id)
        if running_job and running_job.status == JobStatus.RUNNING and running_job.locked_by == self._worker_id:
            task = self._running.get(running_job.id)
            if task and not task.done():
                await self._job_dao.cancel(job_id=running_job.id, reason="Canceled by user")
                task.cancel()
                return True
        return cancelled

    async def recover_startup(self) -> None:
        """Startup recovery for previous process crashes.

        For now we take a conservative approach:
        - Any job left in RUNNING is marked FAILED (unknown state).
        """
        failed = await self._job_dao.fail_all_running(
            error="Server restarted while job was running (startup recovery)"
        )
        if failed:
            logger.warning("Startup recovery: marked %s running job(s) as failed", failed)

    async def _run_loop(self) -> None:
        """Poll for queued jobs and execute them."""
        while not self._stop_event.is_set():
            # Prune completed tasks
            for job_id, task in list(self._running.items()):
                if task.done():
                    self._running.pop(job_id, None)

            # If we're at capacity, wait a bit
            if len(self._running) >= self._max_concurrent:
                await asyncio.sleep(self._poll_interval_seconds)
                continue

            job = await self._job_dao.claim_next(locked_by=self._worker_id)
            if not job:
                await asyncio.sleep(self._poll_interval_seconds)
                continue

            task = asyncio.create_task(self._execute_job(job))
            self._running[job.id] = task

    async def _execute_job(self, job: Job) -> None:
        """Execute a single job with concurrency control."""
        async with self._semaphore:
            handler = self._handlers.get(job.kind)
            if not handler:
                await self._job_dao.fail(job.id, error=f"No handler registered for job kind: {job.kind}")
                return

            try:
                await handler(job)
                await self._job_dao.complete(job.id)
            except asyncio.CancelledError:
                await self._job_dao.cancel(job_id=job.id, reason="Job was cancelled")
                raise
            except Exception as e:
                logger.exception("Job %s failed: %s", job.id, e)
                await self._job_dao.fail(job.id, error=str(e))
