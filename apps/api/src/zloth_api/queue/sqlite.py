"""SQLite-backed queue implementation.

This module provides a QueueBackend implementation using SQLite,
suitable for local development and small-scale deployments.

Architecture v2 Reference: docs/architecture-v2.md
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job
from zloth_api.queue.models import EnqueueOptions, QueueStats
from zloth_api.storage.dao import JobDAO
from zloth_api.storage.db import Database

logger = logging.getLogger(__name__)


def _generate_id() -> str:
    """Generate a unique job ID."""
    import uuid

    return f"job_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    """Get current UTC time as ISO string."""
    return datetime.utcnow().isoformat()


class SQLiteQueue:
    """SQLite-backed queue implementation.

    This implementation uses the existing SQLite database and JobDAO
    for job persistence. It's suitable for:
    - Local development (no external dependencies)
    - Small-scale deployments (single worker)
    - Testing queue abstractions

    Limitations:
    - Single-process only (no distributed locking)
    - No built-in pub/sub for real-time notifications
    - Performance degrades with high job volumes

    For production deployments, consider RedisQueue or AzureServiceBusQueue.
    """

    def __init__(self, db: Database, job_dao: JobDAO | None = None) -> None:
        """Initialize SQLite queue.

        Args:
            db: Database connection.
            job_dao: Optional JobDAO instance. If not provided, creates one.
        """
        self._db = db
        self._job_dao = job_dao or JobDAO(db)

    @property
    def job_dao(self) -> JobDAO:
        """Get the underlying JobDAO for advanced operations."""
        return self._job_dao

    async def enqueue(
        self,
        *,
        kind: JobKind,
        ref_id: str,
        payload: dict[str, Any] | None = None,
        options: EnqueueOptions | None = None,
    ) -> str:
        """Add a new job to the queue.

        Args:
            kind: Type of job to create.
            ref_id: Reference to the domain entity (Run ID, Review ID).
            payload: Additional context for job execution.
            options: Enqueue options (delay, priority, max_attempts).

        Returns:
            The created job's ID.
        """
        opts = options or EnqueueOptions()

        # Calculate available_at based on delay
        available_at: datetime | None = None
        if opts.delay_seconds > 0:
            available_at = datetime.utcnow() + timedelta(seconds=opts.delay_seconds)

        job = await self._job_dao.create(
            kind=kind,
            ref_id=ref_id,
            payload=payload,
            max_attempts=opts.max_attempts,
            available_at=available_at,
        )

        logger.debug(
            "Enqueued job %s (kind=%s, ref=%s, priority=%s)",
            job.id,
            kind.value,
            ref_id,
            opts.priority.name,
        )
        return job.id

    async def dequeue(
        self,
        *,
        locked_by: str,
        visibility_timeout_seconds: int = 600,
    ) -> Job | None:
        """Atomically claim the next available job.

        Args:
            locked_by: Unique identifier for the claiming worker.
            visibility_timeout_seconds: How long the job remains invisible
                to other workers (not used in SQLite implementation).

        Returns:
            The claimed job, or None if no jobs are available.
        """
        # Note: visibility_timeout_seconds is not fully implemented in SQLite
        # because we don't have automatic job release after timeout.
        # This is a known limitation of the SQLite backend.
        job = await self._job_dao.claim_next(locked_by=locked_by)
        if job:
            logger.debug("Claimed job %s (kind=%s, worker=%s)", job.id, job.kind.value, locked_by)
        return job

    async def complete(self, job_id: str) -> None:
        """Mark a job as successfully completed.

        Args:
            job_id: ID of the job to complete.
        """
        await self._job_dao.complete(job_id)
        logger.debug("Completed job %s", job_id)

    async def fail(
        self,
        job_id: str,
        *,
        error: str,
        retry_delay_seconds: int = 10,
    ) -> None:
        """Record a job failure.

        If the job has remaining attempts, it is requeued with a delay.
        Otherwise, it is marked as FAILED.

        Args:
            job_id: ID of the job that failed.
            error: Error message describing the failure.
            retry_delay_seconds: Delay before retrying (default: 10 seconds).
        """
        await self._job_dao.fail(job_id, error=error, retry_delay_seconds=retry_delay_seconds)
        logger.debug("Failed job %s: %s", job_id, error)

    async def cancel(
        self,
        job_id: str,
        *,
        reason: str | None = None,
    ) -> bool:
        """Cancel a job by ID.

        Args:
            job_id: ID of the job to cancel.
            reason: Optional reason for cancellation.

        Returns:
            True if the job was canceled, False if not found or already completed.
        """
        job = await self._job_dao.get(job_id)
        if not job:
            return False
        if job.status in (JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELED):
            return False

        await self._job_dao.cancel(job_id=job_id, reason=reason)
        logger.debug("Canceled job %s: %s", job_id, reason or "no reason")
        return True

    async def cancel_by_ref(
        self,
        *,
        kind: JobKind,
        ref_id: str,
        reason: str | None = None,
    ) -> bool:
        """Cancel jobs by their reference ID.

        Args:
            kind: Type of job to cancel.
            ref_id: Reference ID to match.
            reason: Optional reason for cancellation.

        Returns:
            True if any jobs were canceled.
        """
        # Note: reason is not passed to cancel_queued_by_ref in current JobDAO
        return await self._job_dao.cancel_queued_by_ref(kind=kind, ref_id=ref_id)

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID.

        Args:
            job_id: ID of the job to retrieve.

        Returns:
            The job if found, None otherwise.
        """
        return await self._job_dao.get(job_id)

    async def get_by_ref(
        self,
        *,
        kind: JobKind,
        ref_id: str,
    ) -> Job | None:
        """Get the most recent job for a reference ID.

        Args:
            kind: Type of job to find.
            ref_id: Reference ID to match.

        Returns:
            The most recent job if found, None otherwise.
        """
        return await self._job_dao.get_latest_by_ref(kind=kind, ref_id=ref_id)

    async def get_stats(self) -> QueueStats:
        """Get current queue statistics.

        Returns:
            Statistics about the queue's current state.
        """
        conn = self._db.connection

        # Count jobs by status
        cursor = await conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
            """
        )
        rows = await cursor.fetchall()

        stats = QueueStats()
        for row in rows:
            status = row["status"]
            count = row["count"]
            if status == JobStatus.QUEUED.value:
                stats.queued = count
            elif status == JobStatus.RUNNING.value:
                stats.running = count
            elif status == JobStatus.SUCCEEDED.value:
                stats.succeeded = count
            elif status == JobStatus.FAILED.value:
                stats.failed = count
            elif status == JobStatus.CANCELED.value:
                stats.canceled = count

        # Get oldest queued job
        cursor = await conn.execute(
            """
            SELECT MIN(created_at) as oldest
            FROM jobs
            WHERE status = ?
            """,
            (JobStatus.QUEUED.value,),
        )
        oldest_row = await cursor.fetchone()
        if oldest_row and oldest_row["oldest"]:
            stats.oldest_queued_at = datetime.fromisoformat(oldest_row["oldest"])

        # Calculate average wait time for recently completed jobs
        cursor = await conn.execute(
            """
            SELECT AVG(
                CAST(
                    (julianday(locked_at) - julianday(created_at)) * 24 * 3600
                    AS REAL
                )
            ) as avg_wait
            FROM jobs
            WHERE status = ?
              AND locked_at IS NOT NULL
              AND updated_at >= datetime('now', '-1 hour')
            """,
            (JobStatus.SUCCEEDED.value,),
        )
        avg_row = await cursor.fetchone()
        if avg_row and avg_row["avg_wait"] is not None:
            stats.avg_wait_time_seconds = avg_row["avg_wait"]

        return stats

    async def fail_all_running(self, *, error: str) -> int:
        """Mark all running jobs as failed.

        Used for startup recovery after process crashes.

        Args:
            error: Error message to record.

        Returns:
            Number of jobs marked as failed.
        """
        count = await self._job_dao.fail_all_running(error=error)
        if count > 0:
            logger.warning("Startup recovery: marked %d running job(s) as failed", count)
        return count

    async def cleanup_completed(
        self,
        *,
        older_than_hours: int = 24,
    ) -> int:
        """Remove old completed jobs from the queue.

        Args:
            older_than_hours: Remove jobs completed more than this many hours ago.

        Returns:
            Number of jobs removed.
        """
        conn = self._db.connection
        cutoff = (datetime.utcnow() - timedelta(hours=older_than_hours)).isoformat()

        cursor = await conn.execute(
            """
            DELETE FROM jobs
            WHERE status IN (?, ?, ?)
              AND updated_at < ?
            """,
            (
                JobStatus.SUCCEEDED.value,
                JobStatus.FAILED.value,
                JobStatus.CANCELED.value,
                cutoff,
            ),
        )
        await conn.commit()

        count = cursor.rowcount
        if count > 0:
            logger.info("Cleaned up %d completed jobs older than %d hours", count, older_than_hours)
        return count
