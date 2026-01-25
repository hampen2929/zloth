"""Queue abstraction layer for zloth.

This module provides the QueueBackend protocol and implementations for
different queue backends (SQLite, Redis, Azure Service Bus).

Architecture v2 Reference: docs/architecture-v2.md
"""

from zloth_api.queue.models import Job, JobKind, JobPriority, JobStatus, QueueStats
from zloth_api.queue.protocol import QueueBackend

__all__ = [
    "Job",
    "JobKind",
    "JobPriority",
    "JobStatus",
    "QueueBackend",
    "QueueStats",
]
