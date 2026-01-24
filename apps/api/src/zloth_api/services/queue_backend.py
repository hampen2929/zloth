"""Abstract queue backend interface for job processing.

This module defines the abstract interface for queue backends, enabling
pluggable implementations (SQLite, Redis, etc.) for job processing.

Design goals:
- Abstract interface for queue operations
- Support for visibility timeout, priority, delayed jobs
- Queue statistics for observability
- Easy switching between backends via configuration
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from zloth_api.domain.enums import JobKind
from zloth_api.domain.models import Job


class QueueStats(BaseModel):
    """Queue statistics for observability."""

    queued_count: int = Field(default=0, description="Number of jobs in queued state")
    running_count: int = Field(default=0, description="Number of jobs currently running")
    succeeded_count: int = Field(default=0, description="Number of succeeded jobs")
    failed_count: int = Field(default=0, description="Number of failed jobs")
    canceled_count: int = Field(default=0, description="Number of canceled jobs")

    # By job kind
    counts_by_kind: dict[str, int] = Field(default_factory=dict, description="Job counts by kind")

    # Performance metrics
    avg_wait_time_seconds: float | None = Field(
        None, description="Average time jobs spend in queue"
    )
    avg_processing_time_seconds: float | None = Field(
        None, description="Average job processing time"
    )


class QueueBackend(ABC):
    """Abstract base class for queue backends.

    All queue implementations must provide these operations:
    - enqueue: Add a job to the queue
    - dequeue: Claim the next available job
    - complete: Mark a job as succeeded
    - fail: Mark a job as failed (with optional retry)
    - cancel: Cancel a job
    - get_stats: Get queue statistics

    Implementations should ensure atomic operations for dequeue to prevent
    double-claiming in concurrent environments.
    """

    @abstractmethod
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
        """Add a job to the queue.

        Args:
            kind: Type of job (e.g., run.execute, review.execute)
            ref_id: Reference ID linking to the entity (e.g., run_id)
            payload: Optional JSON-serializable payload
            max_attempts: Maximum number of execution attempts
            delay_seconds: Delay before job becomes available (default: 0)
            priority: Job priority (higher = processed first, default: 0)

        Returns:
            The created Job record.
        """
        pass

    @abstractmethod
    async def dequeue(
        self,
        *,
        worker_id: str,
        visibility_timeout_seconds: float = 300,
    ) -> Job | None:
        """Atomically claim the next available job.

        This operation must be atomic to prevent double-claiming in
        concurrent/distributed environments.

        Args:
            worker_id: Unique identifier for the claiming worker
            visibility_timeout_seconds: Time before job becomes visible again
                                        if not completed (default: 5 minutes)

        Returns:
            The claimed Job, or None if no jobs are available.
        """
        pass

    @abstractmethod
    async def complete(self, job_id: str) -> None:
        """Mark a job as succeeded.

        Args:
            job_id: ID of the job to complete
        """
        pass

    @abstractmethod
    async def fail(
        self,
        job_id: str,
        *,
        error: str,
        retry: bool = True,
        retry_delay_seconds: int = 10,
    ) -> None:
        """Mark a job as failed.

        If retry is True and attempts remain, the job will be requeued
        with the specified delay.

        Args:
            job_id: ID of the job to fail
            error: Error message
            retry: Whether to retry if attempts remain (default: True)
            retry_delay_seconds: Delay before retry (default: 10 seconds)
        """
        pass

    @abstractmethod
    async def cancel(self, job_id: str, *, reason: str | None = None) -> None:
        """Cancel a job.

        Args:
            job_id: ID of the job to cancel
            reason: Optional cancellation reason
        """
        pass

    @abstractmethod
    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID.

        Args:
            job_id: ID of the job to retrieve

        Returns:
            The Job, or None if not found.
        """
        pass

    @abstractmethod
    async def get_latest_by_ref(self, *, kind: JobKind, ref_id: str) -> Job | None:
        """Get the most recent job for a reference ID.

        Args:
            kind: Type of job
            ref_id: Reference ID

        Returns:
            The most recent Job, or None if not found.
        """
        pass

    @abstractmethod
    async def cancel_queued_by_ref(self, *, kind: JobKind, ref_id: str) -> bool:
        """Cancel all queued jobs for a reference ID.

        Args:
            kind: Type of job
            ref_id: Reference ID

        Returns:
            True if any jobs were canceled.
        """
        pass

    @abstractmethod
    async def fail_all_running(self, *, error: str) -> int:
        """Fail all running jobs (used for startup recovery).

        Args:
            error: Error message to set on failed jobs

        Returns:
            Number of jobs that were failed.
        """
        pass

    @abstractmethod
    async def get_stats(self) -> QueueStats:
        """Get queue statistics.

        Returns:
            QueueStats with current queue state.
        """
        pass

    @abstractmethod
    async def extend_visibility(
        self,
        job_id: str,
        *,
        additional_seconds: float,
    ) -> bool:
        """Extend the visibility timeout for a running job.

        Used to prevent timeout for long-running jobs.

        Args:
            job_id: ID of the job
            additional_seconds: Additional seconds to extend

        Returns:
            True if the visibility was extended successfully.
        """
        pass

    async def heartbeat(self, job_id: str) -> bool:
        """Send a heartbeat to keep a job alive.

        Default implementation extends visibility by 60 seconds.
        Subclasses can override for custom behavior.

        Args:
            job_id: ID of the job

        Returns:
            True if heartbeat was successful.
        """
        return await self.extend_visibility(job_id, additional_seconds=60)


class QueueBackendType:
    """Queue backend type identifiers."""

    SQLITE = "sqlite"
    REDIS = "redis"


def parse_queue_url(url: str) -> tuple[str, dict[str, str]]:
    """Parse a queue URL into backend type and connection params.

    Supported formats:
    - sqlite:// (uses default SQLite database)
    - redis://host:port/db

    Args:
        url: Queue URL (e.g., "redis://localhost:6379/0")

    Returns:
        Tuple of (backend_type, connection_params)
    """
    if url.startswith("sqlite://"):
        return QueueBackendType.SQLITE, {}

    if url.startswith("redis://"):
        # Parse redis://host:port/db
        parts = url[8:]  # Remove "redis://"
        params: dict[str, str] = {}

        if "/" in parts:
            host_port, db = parts.rsplit("/", 1)
            params["db"] = db
        else:
            host_port = parts

        if ":" in host_port:
            host, port = host_port.rsplit(":", 1)
            params["host"] = host
            params["port"] = port
        else:
            params["host"] = host_port

        return QueueBackendType.REDIS, params

    raise ValueError(f"Unsupported queue URL format: {url}")
