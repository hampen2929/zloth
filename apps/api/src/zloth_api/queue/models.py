"""Queue-related models for architecture v2.

These models define the contract for queue operations across different backends.

Re-exports domain models for consistent typing across the codebase.
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel

# Re-export from domain for type consistency
from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job

__all__ = [
    "Job",
    "JobKind",
    "JobPriority",
    "JobStatus",
    "QueueStats",
    "EnqueueOptions",
]


class JobPriority(int, Enum):
    """Job priority levels for queue ordering."""

    LOW = 0
    NORMAL = 5
    HIGH = 10


class QueueStats(BaseModel):
    """Statistics for a queue backend.

    Provides insight into queue health and performance.

    Attributes:
        queued: Number of jobs waiting to be processed.
        running: Number of jobs currently being processed.
        succeeded: Number of successfully completed jobs.
        failed: Number of failed jobs (max attempts exceeded).
        canceled: Number of canceled jobs.
        dead_letter: Number of jobs in dead letter queue.
        oldest_queued_at: Timestamp of the oldest queued job.
        avg_wait_time_seconds: Average time jobs spend in queue.
    """

    queued: int = 0
    running: int = 0
    succeeded: int = 0
    failed: int = 0
    canceled: int = 0
    dead_letter: int = 0
    oldest_queued_at: datetime | None = None
    avg_wait_time_seconds: float | None = None


class EnqueueOptions(BaseModel):
    """Options for enqueuing a job.

    Attributes:
        delay_seconds: Delay before the job becomes available.
        priority: Job priority level.
        max_attempts: Maximum retry attempts.
    """

    delay_seconds: int = 0
    priority: JobPriority = JobPriority.NORMAL
    max_attempts: int = 1
