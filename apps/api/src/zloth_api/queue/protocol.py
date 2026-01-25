"""QueueBackend protocol definition for architecture v2.

This module defines the abstract interface that all queue implementations must follow.
This enables swapping between SQLite, Redis, and Azure Service Bus backends.

Architecture v2 Reference: docs/architecture-v2.md
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from zloth_api.queue.models import (
    EnqueueOptions,
    Job,
    JobKind,
    QueueStats,
)


@runtime_checkable
class QueueBackend(Protocol):
    """Protocol for queue backend implementations.

    All queue backends (SQLite, Redis, Azure Service Bus) must implement
    this interface to ensure consistent behavior across environments.

    Design principles:
    - At-least-once delivery: Failed jobs are retried up to max_attempts.
    - Visibility timeout: Running jobs are locked to prevent double-processing.
    - Dead letter queue: Jobs exceeding max_attempts are moved to DLQ.
    - Delayed delivery: Jobs can be scheduled for future processing.

    Usage:
        ```python
        # Enqueue a job
        job_id = await queue.enqueue(
            kind=JobKind.RUN_EXECUTE,
            ref_id="run_123",
            payload={"task_id": "task_456"},
            options=EnqueueOptions(priority=JobPriority.HIGH),
        )

        # Dequeue and process
        job = await queue.dequeue(
            locked_by="worker-001",
            visibility_timeout_seconds=600,
        )
        if job:
            try:
                await process(job)
                await queue.complete(job.id)
            except Exception as e:
                await queue.fail(job.id, error=str(e))
        ```
    """

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
        ...

    async def dequeue(
        self,
        *,
        locked_by: str,
        visibility_timeout_seconds: int = 600,
    ) -> Job | None:
        """Atomically claim the next available job.

        The job is marked as RUNNING and locked by the specified worker.
        If no job is available, returns None.

        Args:
            locked_by: Unique identifier for the claiming worker.
            visibility_timeout_seconds: How long the job remains invisible
                to other workers (default: 10 minutes).

        Returns:
            The claimed job, or None if no jobs are available.
        """
        ...

    async def complete(self, job_id: str) -> None:
        """Mark a job as successfully completed.

        The job status is updated to SUCCEEDED and the lock is released.

        Args:
            job_id: ID of the job to complete.
        """
        ...

    async def fail(
        self,
        job_id: str,
        *,
        error: str,
        retry_delay_seconds: int = 10,
    ) -> None:
        """Record a job failure.

        If the job has remaining attempts, it is requeued with a delay.
        Otherwise, it is marked as FAILED (moved to dead letter queue).

        Args:
            job_id: ID of the job that failed.
            error: Error message describing the failure.
            retry_delay_seconds: Delay before retrying (default: 10 seconds).
        """
        ...

    async def cancel(
        self,
        job_id: str,
        *,
        reason: str | None = None,
    ) -> bool:
        """Cancel a queued or running job.

        Args:
            job_id: ID of the job to cancel.
            reason: Optional reason for cancellation.

        Returns:
            True if the job was canceled, False if not found or already completed.
        """
        ...

    async def cancel_by_ref(
        self,
        *,
        kind: JobKind,
        ref_id: str,
        reason: str | None = None,
    ) -> bool:
        """Cancel jobs by their reference ID.

        Cancels all queued jobs matching the kind and ref_id.

        Args:
            kind: Type of job to cancel.
            ref_id: Reference ID to match.
            reason: Optional reason for cancellation.

        Returns:
            True if any jobs were canceled.
        """
        ...

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID.

        Args:
            job_id: ID of the job to retrieve.

        Returns:
            The job if found, None otherwise.
        """
        ...

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
        ...

    async def get_stats(self) -> QueueStats:
        """Get current queue statistics.

        Returns:
            Statistics about the queue's current state.
        """
        ...

    async def fail_all_running(self, *, error: str) -> int:
        """Mark all running jobs as failed.

        Used for startup recovery after process crashes.

        Args:
            error: Error message to record.

        Returns:
            Number of jobs marked as failed.
        """
        ...

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
        ...


class QueueBackendFactory(Protocol):
    """Factory protocol for creating queue backend instances.

    This enables dependency injection and configuration-based backend selection.
    """

    def create(self, url: str) -> QueueBackend:
        """Create a queue backend from a connection URL.

        Args:
            url: Connection URL (e.g., "sqlite:///data/queue.db",
                 "redis://localhost:6379", "servicebus://...")

        Returns:
            Configured queue backend instance.
        """
        ...
