"""Background job worker using pluggable queue backend.

This module provides a lightweight queue worker that processes jobs using
a pluggable queue backend (SQLite, Redis, etc.).

Design goals:
- Survive process restarts (jobs are not lost)
- Concurrency control via semaphore
- Best-effort cancellation for running jobs
- Pluggable queue backend for different storage options
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping

from zloth_api.config import settings
from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job
from zloth_api.services.queue_backend import QueueBackend

logger = logging.getLogger(__name__)

JobHandler = Callable[[Job], Awaitable[None]]


class JobWorker:
    """Background worker that polls queue backend for jobs and executes handlers."""

    def __init__(
        self,
        *,
        queue_backend: QueueBackend,
        handlers: Mapping[JobKind, JobHandler],
        max_concurrent: int | None = None,
        poll_interval_seconds: float | None = None,
        visibility_timeout_seconds: float | None = None,
    ) -> None:
        """Initialize the job worker.

        Args:
            queue_backend: Queue backend for job storage/retrieval
            handlers: Mapping of job kinds to handler functions
            max_concurrent: Maximum concurrent job executions
            poll_interval_seconds: Interval between queue polling
            visibility_timeout_seconds: Visibility timeout for claimed jobs
        """
        self._queue = queue_backend
        self._handlers = dict(handlers)
        self._max_concurrent = max_concurrent or settings.queue_max_concurrent_tasks
        self._poll_interval_seconds = poll_interval_seconds or settings.queue_poll_interval_seconds
        self._visibility_timeout_seconds = (
            visibility_timeout_seconds or settings.queue_visibility_timeout_seconds
        )
        self._worker_id = f"worker-{uuid.uuid4().hex[:12]}"

        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Job ID -> running task
        self._running: dict[str, asyncio.Task[None]] = {}

    @property
    def worker_id(self) -> str:
        """Get the unique worker ID."""
        return self._worker_id

    @property
    def queue_backend(self) -> QueueBackend:
        """Get the queue backend."""
        return self._queue

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
        """Cancel a queued job, and best-effort cancel a running job.

        Args:
            kind: Type of job to cancel
            ref_id: Reference ID of the job

        Returns:
            True if a job was canceled.
        """
        cancelled = await self._queue.cancel_queued_by_ref(kind=kind, ref_id=ref_id)
        running_job = await self._queue.get_latest_by_ref(kind=kind, ref_id=ref_id)
        if (
            running_job
            and running_job.status == JobStatus.RUNNING
            and running_job.locked_by == self._worker_id
        ):
            task = self._running.get(running_job.id)
            if task and not task.done():
                await self._queue.cancel(running_job.id, reason="Canceled by user")
                task.cancel()
                return True
        return cancelled

    async def recover_startup(self) -> None:
        """Startup recovery for previous process crashes.

        For now we take a conservative approach:
        - Any job left in RUNNING is marked FAILED (unknown state).
        """
        failed = await self._queue.fail_all_running(
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

            job = await self._queue.dequeue(
                worker_id=self._worker_id,
                visibility_timeout_seconds=self._visibility_timeout_seconds,
            )
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
                await self._queue.fail(
                    job.id, error=f"No handler registered for job kind: {job.kind}", retry=False
                )
                return

            # Start heartbeat task to keep job alive during long executions
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(job.id))

            try:
                await handler(job)
                await self._queue.complete(job.id)
            except asyncio.CancelledError:
                await self._queue.cancel(job.id, reason="Job was cancelled")
                raise
            except Exception as e:
                logger.exception("Job %s failed: %s", job.id, e)
                await self._queue.fail(job.id, error=str(e))
            finally:
                heartbeat_task.cancel()
                try:
                    await heartbeat_task
                except asyncio.CancelledError:
                    pass

    async def _heartbeat_loop(self, job_id: str) -> None:
        """Send periodic heartbeats to keep a job alive."""
        # Send heartbeat every 30 seconds (visibility timeout is 5 min by default)
        interval = self._visibility_timeout_seconds / 10
        while True:
            await asyncio.sleep(interval)
            try:
                success = await self._queue.heartbeat(job_id)
                if not success:
                    logger.warning("Heartbeat failed for job %s", job_id)
                    break
            except Exception as e:
                logger.warning("Heartbeat error for job %s: %s", job_id, e)
                break
