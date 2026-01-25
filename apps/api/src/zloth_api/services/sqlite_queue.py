"""SQLite-backed queue implementation.

This module provides a SQLite-based implementation of the QueueBackend
interface, wrapping the existing JobDAO for backward compatibility.

Design notes:
- Uses IMMEDIATE transactions for atomic job claiming
- Supports delayed jobs via available_at column
- Priority is stored but not yet fully utilized (future enhancement)
- Visibility timeout simulated via locked_at + timeout check
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job
from zloth_api.services.queue_backend import QueueBackend, QueueStats
from zloth_api.storage.db import Database

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    """Return current UTC timestamp in ISO format."""
    return datetime.utcnow().isoformat()


def _generate_id() -> str:
    """Generate a unique job ID."""
    import uuid

    return uuid.uuid4().hex[:16]


class SQLiteQueueBackend(QueueBackend):
    """SQLite-backed queue implementation.

    This implementation wraps direct database access for queue operations,
    providing the QueueBackend interface while maintaining compatibility
    with the existing jobs table schema.
    """

    def __init__(self, db: Database) -> None:
        """Initialize the SQLite queue backend.

        Args:
            db: Database connection wrapper
        """
        self._db = db

    async def enqueue(
        self,
        *,
        kind: JobKind,
        ref_id: str,
        payload: dict[str, Any] | None = None,
        max_attempts: int = 1,
        delay_seconds: float = 0,
        priority: int = 0,
    ) -> Job:
        """Add a job to the queue."""
        job_id = _generate_id()
        now = datetime.utcnow()
        now_iso = now.isoformat()
        payload_str = json.dumps(payload or {})

        # Calculate available_at for delayed jobs
        if delay_seconds > 0:
            available_at = (now + timedelta(seconds=delay_seconds)).isoformat()
        else:
            available_at = now_iso

        await self._db.connection.execute(
            """
            INSERT INTO jobs (
                id, kind, ref_id, status, payload,
                attempts, max_attempts, priority,
                available_at, locked_at, locked_by,
                last_error, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job_id,
                kind.value,
                ref_id,
                JobStatus.QUEUED.value,
                payload_str,
                0,
                max_attempts,
                priority,
                available_at,
                None,
                None,
                None,
                now_iso,
                now_iso,
            ),
        )
        await self._db.connection.commit()

        job = await self.get(job_id)
        if not job:
            raise RuntimeError(f"Job not found after create: {job_id}")
        return job

    async def dequeue(
        self,
        *,
        worker_id: str,
        visibility_timeout_seconds: float = 300,
    ) -> Job | None:
        """Atomically claim the next available job."""
        conn = self._db.connection
        now = datetime.utcnow()
        now_iso = now.isoformat()

        # Also check for jobs that have exceeded visibility timeout
        visibility_cutoff = (now - timedelta(seconds=visibility_timeout_seconds)).isoformat()

        await conn.execute("BEGIN IMMEDIATE")
        try:
            # Find next available job:
            # 1. Status is QUEUED and available_at <= now, OR
            # 2. Status is RUNNING but locked_at < visibility_cutoff (timed out)
            cursor = await conn.execute(
                """
                SELECT id FROM jobs
                WHERE (
                    (status = ? AND available_at <= ?)
                    OR (status = ? AND locked_at < ?)
                )
                ORDER BY priority DESC, created_at ASC
                LIMIT 1
                """,
                (
                    JobStatus.QUEUED.value,
                    now_iso,
                    JobStatus.RUNNING.value,
                    visibility_cutoff,
                ),
            )
            row = await cursor.fetchone()
            if not row:
                await conn.execute("COMMIT")
                return None

            job_id = row["id"]

            # Claim the job
            await conn.execute(
                """
                UPDATE jobs
                SET status = ?,
                    attempts = attempts + 1,
                    locked_at = ?,
                    locked_by = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    JobStatus.RUNNING.value,
                    now_iso,
                    worker_id,
                    now_iso,
                    job_id,
                ),
            )
            await conn.execute("COMMIT")
        except Exception:
            await conn.execute("ROLLBACK")
            raise

        return await self.get(job_id)

    async def complete(self, job_id: str) -> None:
        """Mark a job as succeeded."""
        now_iso = _now_iso()
        await self._db.connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                locked_at = NULL,
                locked_by = NULL,
                last_error = NULL,
                updated_at = ?
            WHERE id = ?
            """,
            (JobStatus.SUCCEEDED.value, now_iso, job_id),
        )
        await self._db.connection.commit()

    async def fail(
        self,
        job_id: str,
        *,
        error: str,
        retry: bool = True,
        retry_delay_seconds: int = 10,
    ) -> None:
        """Mark a job as failed, optionally requeuing for retry."""
        job = await self.get(job_id)
        if not job:
            return

        now = datetime.utcnow()
        now_iso = now.isoformat()

        if retry and job.attempts < job.max_attempts:
            # Requeue with delay
            available_at = (now + timedelta(seconds=retry_delay_seconds)).isoformat()
            await self._db.connection.execute(
                """
                UPDATE jobs
                SET status = ?,
                    available_at = ?,
                    locked_at = NULL,
                    locked_by = NULL,
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (JobStatus.QUEUED.value, available_at, error, now_iso, job_id),
            )
        else:
            # Permanent failure
            await self._db.connection.execute(
                """
                UPDATE jobs
                SET status = ?,
                    locked_at = NULL,
                    locked_by = NULL,
                    last_error = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (JobStatus.FAILED.value, error, now_iso, job_id),
            )
        await self._db.connection.commit()

    async def cancel(self, job_id: str, *, reason: str | None = None) -> None:
        """Cancel a job."""
        now_iso = _now_iso()
        await self._db.connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                locked_at = NULL,
                locked_by = NULL,
                last_error = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (JobStatus.CANCELED.value, reason, now_iso, job_id),
        )
        await self._db.connection.commit()

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        cursor = await self._db.connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    async def get_latest_by_ref(self, *, kind: JobKind, ref_id: str) -> Job | None:
        """Get the most recent job for a reference ID."""
        cursor = await self._db.connection.execute(
            """
            SELECT * FROM jobs
            WHERE kind = ? AND ref_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (kind.value, ref_id),
        )
        row = await cursor.fetchone()
        if not row:
            return None
        return self._row_to_job(row)

    async def cancel_queued_by_ref(self, *, kind: JobKind, ref_id: str) -> bool:
        """Cancel all queued jobs for a reference ID."""
        now_iso = _now_iso()
        cursor = await self._db.connection.execute(
            """
            UPDATE jobs
            SET status = ?, updated_at = ?
            WHERE kind = ?
              AND ref_id = ?
              AND status = ?
            """,
            (JobStatus.CANCELED.value, now_iso, kind.value, ref_id, JobStatus.QUEUED.value),
        )
        await self._db.connection.commit()
        return cursor.rowcount > 0

    async def fail_all_running(self, *, error: str) -> int:
        """Fail all running jobs (startup recovery)."""
        now_iso = _now_iso()
        cursor = await self._db.connection.execute(
            """
            UPDATE jobs
            SET status = ?,
                locked_at = NULL,
                locked_by = NULL,
                last_error = ?,
                updated_at = ?
            WHERE status = ?
            """,
            (JobStatus.FAILED.value, error, now_iso, JobStatus.RUNNING.value),
        )
        await self._db.connection.commit()
        return cursor.rowcount

    async def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        conn = self._db.connection

        # Count by status
        cursor = await conn.execute(
            """
            SELECT status, COUNT(*) as count
            FROM jobs
            GROUP BY status
            """
        )
        rows = await cursor.fetchall()
        status_counts: dict[str, int] = {row["status"]: row["count"] for row in rows}

        # Count by kind
        cursor = await conn.execute(
            """
            SELECT kind, COUNT(*) as count
            FROM jobs
            WHERE status IN (?, ?)
            GROUP BY kind
            """,
            (JobStatus.QUEUED.value, JobStatus.RUNNING.value),
        )
        rows = await cursor.fetchall()
        kind_counts: dict[str, int] = {row["kind"]: row["count"] for row in rows}

        return QueueStats(
            queued_count=status_counts.get(JobStatus.QUEUED.value, 0),
            running_count=status_counts.get(JobStatus.RUNNING.value, 0),
            succeeded_count=status_counts.get(JobStatus.SUCCEEDED.value, 0),
            failed_count=status_counts.get(JobStatus.FAILED.value, 0),
            canceled_count=status_counts.get(JobStatus.CANCELED.value, 0),
            counts_by_kind=kind_counts,
        )

    async def extend_visibility(
        self,
        job_id: str,
        *,
        additional_seconds: float,
    ) -> bool:
        """Extend the visibility timeout for a running job."""
        now = datetime.utcnow()
        new_locked_at = (now + timedelta(seconds=additional_seconds)).isoformat()

        cursor = await self._db.connection.execute(
            """
            UPDATE jobs
            SET locked_at = ?,
                updated_at = ?
            WHERE id = ? AND status = ?
            """,
            (new_locked_at, now.isoformat(), job_id, JobStatus.RUNNING.value),
        )
        await self._db.connection.commit()
        return cursor.rowcount > 0

    def _row_to_job(self, row: Any) -> Job:
        """Convert a database row to a Job model."""
        payload: dict[str, Any] = {}
        if row["payload"]:
            try:
                payload = json.loads(row["payload"])
            except Exception:
                payload = {}

        def _parse_dt(value: Any) -> datetime | None:
            if not value:
                return None
            return datetime.fromisoformat(value)

        return Job(
            id=row["id"],
            kind=JobKind(row["kind"]),
            ref_id=row["ref_id"],
            status=JobStatus(row["status"]),
            payload=payload,
            attempts=int(row["attempts"] or 0),
            max_attempts=int(row["max_attempts"] or 1),
            available_at=_parse_dt(row["available_at"]),
            locked_at=_parse_dt(row["locked_at"]),
            locked_by=row["locked_by"],
            last_error=row["last_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
