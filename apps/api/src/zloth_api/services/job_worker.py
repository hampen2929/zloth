"""Background job worker for architecture v2.

This module provides a generic job worker that processes jobs from any
QueueBackend implementation (SQLite, Redis, Azure Service Bus).

Design goals:
- Survive process restarts (queued jobs are not lost)
- Concurrency control via semaphore
- Best-effort cancellation for running jobs
- Backend-agnostic (works with any QueueBackend)

Architecture v2 Reference: docs/architecture-v2.md
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Mapping
from typing import TYPE_CHECKING

from zloth_api.config import settings
from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job

if TYPE_CHECKING:
    from zloth_api.queue.sqlite import SQLiteQueue

logger = logging.getLogger(__name__)

JobHandler = Callable[[Job], Awaitable[None]]


class JobWorker:
    """Background worker that polls a queue backend and executes handlers.

    This worker is designed to work with any QueueBackend implementation,
    enabling deployment flexibility:
    - Local development: SQLiteQueue (no external dependencies)
    - Small-scale production: RedisQueue (simple, low latency)
    - Enterprise production: AzureServiceBusQueue (managed, highly reliable)

    Example:
        ```python
        # Using SQLiteQueue
        from zloth_api.queue.sqlite import SQLiteQueue

        queue = SQLiteQueue(db)
        handlers = {
            JobKind.RUN_EXECUTE: run_service.execute_job,
            JobKind.REVIEW_EXECUTE: review_service.execute_job,
        }
        worker = JobWorker(queue=queue, handlers=handlers)
        await worker.recover_startup()
        worker.start()
        ```

    Attributes:
        worker_id: Unique identifier for this worker instance.
    """

    def __init__(
        self,
        *,
        queue: SQLiteQueue,
        handlers: Mapping[JobKind, JobHandler],
        max_concurrent: int | None = None,
        poll_interval_seconds: float | None = None,
        worker_id_prefix: str | None = None,
    ) -> None:
        """Initialize the job worker.

        Args:
            queue: Queue backend to pull jobs from.
            handlers: Mapping of job kinds to handler functions.
            max_concurrent: Maximum concurrent job executions.
                Defaults to settings.worker_concurrency.
            poll_interval_seconds: Interval between queue polls.
                Defaults to settings.worker_poll_interval_seconds.
            worker_id_prefix: Prefix for auto-generated worker ID.
                Defaults to settings.worker_id_prefix.
        """
        self._queue = queue
        self._handlers = dict(handlers)
        self._max_concurrent = max_concurrent or settings.worker_concurrency
        self._poll_interval_seconds = (
            poll_interval_seconds
            if poll_interval_seconds is not None
            else settings.worker_poll_interval_seconds
        )

        prefix = worker_id_prefix or settings.worker_id_prefix
        self._worker_id = f"{prefix}-{uuid.uuid4().hex[:12]}"

        self._semaphore = asyncio.Semaphore(self._max_concurrent)
        self._loop_task: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

        # Job ID -> running task
        self._running: dict[str, asyncio.Task[None]] = {}

    @property
    def worker_id(self) -> str:
        """Get the unique identifier for this worker."""
        return self._worker_id

    @property
    def queue(self) -> SQLiteQueue:
        """Get the queue backend."""
        return self._queue

    @property
    def running_count(self) -> int:
        """Get the number of currently running jobs."""
        return len([t for t in self._running.values() if not t.done()])

    @property
    def is_running(self) -> bool:
        """Check if the worker is currently running."""
        return self._loop_task is not None and not self._loop_task.done()

    def start(self) -> None:
        """Start the background polling loop.

        If the worker is already running, this is a no-op.
        """
        if self._loop_task and not self._loop_task.done():
            return
        self._stop_event.clear()
        self._loop_task = asyncio.create_task(self._run_loop())
        logger.info(
            "JobWorker started (id=%s, concurrency=%d, poll_interval=%.1fs)",
            self._worker_id,
            self._max_concurrent,
            self._poll_interval_seconds,
        )

    async def stop(self, *, timeout_seconds: float = 30.0) -> None:
        """Stop the worker and wait for running jobs to complete.

        Args:
            timeout_seconds: Maximum time to wait for running jobs.
        """
        self._stop_event.set()

        if self._loop_task and not self._loop_task.done():
            self._loop_task.cancel()
            try:
                await self._loop_task
            except asyncio.CancelledError:
                pass

        # Wait for running jobs to complete (with timeout)
        if self._running:
            running_tasks = list(self._running.values())
            try:
                await asyncio.wait_for(
                    asyncio.gather(*running_tasks, return_exceptions=True),
                    timeout=timeout_seconds,
                )
            except TimeoutError:
                logger.warning("Timeout waiting for %d running jobs, canceling", len(running_tasks))
                for task in running_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*running_tasks, return_exceptions=True)

        self._running.clear()
        logger.info("JobWorker stopped (%s)", self._worker_id)

    async def cancel_ref(self, *, kind: JobKind, ref_id: str) -> bool:
        """Cancel a queued job and attempt to cancel a running job.

        Args:
            kind: Type of job to cancel.
            ref_id: Reference ID to match.

        Returns:
            True if a job was canceled (queued or running).
        """
        # Cancel queued job
        cancelled = await self._queue.cancel_by_ref(kind=kind, ref_id=ref_id)

        # Try to cancel running job if owned by this worker
        running_job = await self._queue.get_by_ref(kind=kind, ref_id=ref_id)
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
        """Recover from previous process crashes.

        Marks all running jobs as failed since their state is unknown.
        Called once during application startup before starting the worker.
        """
        failed = await self._queue.fail_all_running(
            error="Server restarted while job was running (startup recovery)"
        )
        if failed:
            logger.warning("Startup recovery: marked %d running job(s) as failed", failed)

    async def cleanup_old_jobs(self) -> int:
        """Remove old completed jobs from the queue.

        Uses the configured cleanup threshold from settings.

        Returns:
            Number of jobs removed.
        """
        return await self._queue.cleanup_completed(
            older_than_hours=settings.queue_cleanup_older_than_hours
        )

    async def _run_loop(self) -> None:
        """Main polling loop that processes jobs."""
        while not self._stop_event.is_set():
            try:
                # Prune completed tasks
                for job_id, task in list(self._running.items()):
                    if task.done():
                        self._running.pop(job_id, None)

                # If we're at capacity, wait a bit
                if len(self._running) >= self._max_concurrent:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue

                # Try to claim a job
                job = await self._queue.dequeue(
                    locked_by=self._worker_id,
                    visibility_timeout_seconds=settings.job_timeout_seconds,
                )
                if not job:
                    await asyncio.sleep(self._poll_interval_seconds)
                    continue

                # Execute the job
                task = asyncio.create_task(self._execute_job(job))
                self._running[job.id] = task
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception(
                    "JobWorker loop error (worker_id=%s). Will retry after delay.",
                    self._worker_id,
                )
                await asyncio.sleep(self._poll_interval_seconds)

    async def _execute_job(self, job: Job) -> None:
        """Execute a single job with concurrency control."""
        async with self._semaphore:
            handler = self._handlers.get(job.kind)
            if not handler:
                await self._queue.fail(
                    job.id, error=f"No handler registered for job kind: {job.kind}"
                )
                return

            try:
                logger.debug(
                    "Executing job %s (kind=%s, ref=%s, attempt=%d/%d)",
                    job.id,
                    job.kind.value,
                    job.ref_id,
                    job.attempts,
                    job.max_attempts,
                )
                await handler(job)
                await self._queue.complete(job.id)
                logger.debug("Job %s completed successfully", job.id)
            except asyncio.CancelledError:
                await self._queue.cancel(job.id, reason="Job was cancelled")
                logger.info("Job %s was cancelled", job.id)
                raise
            except Exception as e:
                logger.exception("Job %s failed: %s", job.id, e)
                await self._queue.fail(job.id, error=str(e))
