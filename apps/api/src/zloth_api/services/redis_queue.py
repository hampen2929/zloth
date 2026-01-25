"""Redis-backed queue implementation.

This module provides a Redis-based implementation of the QueueBackend
interface, enabling distributed job processing across multiple workers.

Design notes:
- Uses Redis sorted sets for priority queue with delayed jobs
- Atomic job claiming via Lua scripts to prevent double-claiming
- Visibility timeout via separate sorted set for running jobs
- Job data stored in Redis hashes for efficient access

Redis data structures:
- zloth:queue:jobs:{job_id} - Hash with job data
- zloth:queue:pending - Sorted set (score = priority * -1e12 + available_at_timestamp)
- zloth:queue:running - Sorted set (score = visibility_timeout_timestamp)
- zloth:queue:stats - Hash with queue statistics
"""

from __future__ import annotations

import json
import logging
import time
from datetime import datetime
from typing import Any

from zloth_api.domain.enums import JobKind, JobStatus
from zloth_api.domain.models import Job
from zloth_api.services.queue_backend import QueueBackend, QueueStats

logger = logging.getLogger(__name__)

# Redis key prefixes
KEY_PREFIX = "zloth:queue"
KEY_JOBS = f"{KEY_PREFIX}:jobs"
KEY_PENDING = f"{KEY_PREFIX}:pending"
KEY_RUNNING = f"{KEY_PREFIX}:running"
KEY_STATS = f"{KEY_PREFIX}:stats"
KEY_BY_REF = f"{KEY_PREFIX}:by_ref"

# Lua script for atomic dequeue operation
DEQUEUE_SCRIPT = """
-- KEYS[1] = pending set
-- KEYS[2] = running set
-- KEYS[3] = job hash prefix
-- ARGV[1] = current timestamp
-- ARGV[2] = worker_id
-- ARGV[3] = visibility timeout timestamp

-- Get the first available job (score <= current timestamp)
local result = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 1)
if #result == 0 then
    return nil
end

local job_id = result[1]
local job_key = KEYS[3] .. ':' .. job_id

-- Remove from pending, add to running
redis.call('ZREM', KEYS[1], job_id)
redis.call('ZADD', KEYS[2], ARGV[3], job_id)

-- Update job status
redis.call('HSET', job_key, 'status', 'running', 'locked_by', ARGV[2], 'locked_at', ARGV[1])
local attempts = redis.call('HINCRBY', job_key, 'attempts', 1)

return job_id
"""

# Lua script for reclaiming timed-out jobs
RECLAIM_SCRIPT = """
-- KEYS[1] = running set
-- KEYS[2] = pending set
-- KEYS[3] = job hash prefix
-- ARGV[1] = current timestamp

-- Get jobs that have exceeded visibility timeout
local result = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', ARGV[1], 'LIMIT', 0, 10)
local reclaimed = 0

for _, job_id in ipairs(result) do
    local job_key = KEYS[3] .. ':' .. job_id
    local job_data = redis.call('HGETALL', job_key)
    if #job_data > 0 then
        -- Move back to pending with same priority
        local priority = redis.call('HGET', job_key, 'priority') or 0
        local score = -tonumber(priority) * 1e12 + tonumber(ARGV[1])
        redis.call('ZREM', KEYS[1], job_id)
        redis.call('ZADD', KEYS[2], score, job_id)
        redis.call('HSET', job_key, 'status', 'queued', 'locked_by', '', 'locked_at', '')
        reclaimed = reclaimed + 1
    end
end

return reclaimed
"""


def _generate_id() -> str:
    """Generate a unique job ID."""
    import uuid

    return uuid.uuid4().hex[:16]


def _now_timestamp() -> float:
    """Get current UTC timestamp."""
    return time.time()


def _timestamp_to_iso(ts: float) -> str:
    """Convert timestamp to ISO format."""
    return datetime.utcfromtimestamp(ts).isoformat()


def _iso_to_timestamp(iso: str) -> float:
    """Convert ISO format to timestamp."""
    return datetime.fromisoformat(iso).timestamp()


class RedisQueueBackend(QueueBackend):
    """Redis-backed queue implementation.

    Provides a distributed queue using Redis data structures:
    - Sorted sets for priority/delayed job ordering
    - Lua scripts for atomic operations
    - Visibility timeout for job reliability
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
    ) -> None:
        """Initialize the Redis queue backend.

        Args:
            host: Redis host
            port: Redis port
            db: Redis database number
            password: Optional Redis password
        """
        self._host = host
        self._port = port
        self._db = db
        self._password = password
        self._redis: Any = None
        self._dequeue_sha: str | None = None
        self._reclaim_sha: str | None = None

    async def _get_redis(self) -> Any:
        """Get or create Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis  # type: ignore[import-not-found]
            except ImportError:
                raise ImportError(
                    "redis package is required for Redis queue backend. "
                    "Install with: pip install redis"
                )

            self._redis = aioredis.Redis(
                host=self._host,
                port=self._port,
                db=self._db,
                password=self._password,
                decode_responses=True,
            )

            # Load Lua scripts
            self._dequeue_sha = await self._redis.script_load(DEQUEUE_SCRIPT)
            self._reclaim_sha = await self._redis.script_load(RECLAIM_SCRIPT)

        return self._redis

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._redis:
            await self._redis.close()
            self._redis = None

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
        redis = await self._get_redis()
        job_id = _generate_id()
        now = _now_timestamp()
        available_at = now + delay_seconds

        # Calculate score: negative priority (higher priority = lower score) + timestamp
        # This ensures higher priority jobs come first, then FIFO within same priority
        score = -priority * 1e12 + available_at

        job_data = {
            "id": job_id,
            "kind": kind.value,
            "ref_id": ref_id,
            "status": JobStatus.QUEUED.value,
            "payload": json.dumps(payload or {}),
            "attempts": "0",
            "max_attempts": str(max_attempts),
            "priority": str(priority),
            "available_at": _timestamp_to_iso(available_at),
            "locked_at": "",
            "locked_by": "",
            "last_error": "",
            "created_at": _timestamp_to_iso(now),
            "updated_at": _timestamp_to_iso(now),
        }

        # Use pipeline for atomic multi-command
        async with redis.pipeline() as pipe:
            pipe.hset(f"{KEY_JOBS}:{job_id}", mapping=job_data)
            pipe.zadd(KEY_PENDING, {job_id: score})
            pipe.sadd(f"{KEY_BY_REF}:{kind.value}:{ref_id}", job_id)
            pipe.hincrby(KEY_STATS, f"total_{kind.value}", 1)
            await pipe.execute()

        return self._dict_to_job(job_data)

    async def dequeue(
        self,
        *,
        worker_id: str,
        visibility_timeout_seconds: float = 300,
    ) -> Job | None:
        """Atomically claim the next available job."""
        redis = await self._get_redis()
        now = _now_timestamp()
        visibility_timeout = now + visibility_timeout_seconds

        # First, reclaim any timed-out jobs
        if self._reclaim_sha:
            await redis.evalsha(
                self._reclaim_sha,
                3,
                KEY_RUNNING,
                KEY_PENDING,
                KEY_JOBS,
                str(now),
            )

        # Dequeue using Lua script for atomicity
        if not self._dequeue_sha:
            return None

        job_id = await redis.evalsha(
            self._dequeue_sha,
            3,
            KEY_PENDING,
            KEY_RUNNING,
            KEY_JOBS,
            str(now),
            worker_id,
            str(visibility_timeout),
        )

        if not job_id:
            return None

        return await self.get(job_id)

    async def complete(self, job_id: str) -> None:
        """Mark a job as succeeded."""
        redis = await self._get_redis()
        job_key = f"{KEY_JOBS}:{job_id}"
        now = _timestamp_to_iso(_now_timestamp())

        async with redis.pipeline() as pipe:
            pipe.zrem(KEY_RUNNING, job_id)
            pipe.hset(
                job_key,
                mapping={
                    "status": JobStatus.SUCCEEDED.value,
                    "locked_at": "",
                    "locked_by": "",
                    "last_error": "",
                    "updated_at": now,
                },
            )
            pipe.hincrby(KEY_STATS, "succeeded", 1)
            await pipe.execute()

    async def fail(
        self,
        job_id: str,
        *,
        error: str,
        retry: bool = True,
        retry_delay_seconds: int = 10,
    ) -> None:
        """Mark a job as failed, optionally requeuing for retry."""
        redis = await self._get_redis()
        job = await self.get(job_id)
        if not job:
            return

        job_key = f"{KEY_JOBS}:{job_id}"
        now = _now_timestamp()
        now_iso = _timestamp_to_iso(now)

        async with redis.pipeline() as pipe:
            pipe.zrem(KEY_RUNNING, job_id)

            if retry and job.attempts < job.max_attempts:
                # Requeue with delay
                available_at = now + retry_delay_seconds
                priority_str = await redis.hget(job_key, "priority") or "0"
                priority = int(priority_str)
                score = -priority * 1e12 + available_at

                pipe.hset(
                    job_key,
                    mapping={
                        "status": JobStatus.QUEUED.value,
                        "available_at": _timestamp_to_iso(available_at),
                        "locked_at": "",
                        "locked_by": "",
                        "last_error": error,
                        "updated_at": now_iso,
                    },
                )
                pipe.zadd(KEY_PENDING, {job_id: score})
            else:
                # Permanent failure
                pipe.hset(
                    job_key,
                    mapping={
                        "status": JobStatus.FAILED.value,
                        "locked_at": "",
                        "locked_by": "",
                        "last_error": error,
                        "updated_at": now_iso,
                    },
                )
                pipe.hincrby(KEY_STATS, "failed", 1)

            await pipe.execute()

    async def cancel(self, job_id: str, *, reason: str | None = None) -> None:
        """Cancel a job."""
        redis = await self._get_redis()
        job_key = f"{KEY_JOBS}:{job_id}"
        now_iso = _timestamp_to_iso(_now_timestamp())

        async with redis.pipeline() as pipe:
            pipe.zrem(KEY_PENDING, job_id)
            pipe.zrem(KEY_RUNNING, job_id)
            pipe.hset(
                job_key,
                mapping={
                    "status": JobStatus.CANCELED.value,
                    "locked_at": "",
                    "locked_by": "",
                    "last_error": reason or "",
                    "updated_at": now_iso,
                },
            )
            pipe.hincrby(KEY_STATS, "canceled", 1)
            await pipe.execute()

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        redis = await self._get_redis()
        job_data = await redis.hgetall(f"{KEY_JOBS}:{job_id}")
        if not job_data:
            return None
        return self._dict_to_job(job_data)

    async def get_latest_by_ref(self, *, kind: JobKind, ref_id: str) -> Job | None:
        """Get the most recent job for a reference ID."""
        redis = await self._get_redis()
        job_ids = await redis.smembers(f"{KEY_BY_REF}:{kind.value}:{ref_id}")
        if not job_ids:
            return None

        # Get all jobs and find the latest by created_at
        latest_job: Job | None = None
        latest_time: datetime | None = None

        for job_id in job_ids:
            job = await self.get(job_id)
            if job and (latest_time is None or job.created_at > latest_time):
                latest_job = job
                latest_time = job.created_at

        return latest_job

    async def cancel_queued_by_ref(self, *, kind: JobKind, ref_id: str) -> bool:
        """Cancel all queued jobs for a reference ID."""
        redis = await self._get_redis()
        job_ids = await redis.smembers(f"{KEY_BY_REF}:{kind.value}:{ref_id}")
        if not job_ids:
            return False

        canceled = False
        for job_id in job_ids:
            job = await self.get(job_id)
            if job and job.status == JobStatus.QUEUED:
                await self.cancel(job_id, reason="Canceled by ref")
                canceled = True

        return canceled

    async def fail_all_running(self, *, error: str) -> int:
        """Fail all running jobs (startup recovery)."""
        redis = await self._get_redis()
        running_ids = await redis.zrange(KEY_RUNNING, 0, -1)
        if not running_ids:
            return 0

        count = 0
        for job_id in running_ids:
            await self.fail(job_id, error=error, retry=False)
            count += 1

        return count

    async def get_stats(self) -> QueueStats:
        """Get queue statistics."""
        redis = await self._get_redis()

        # Count pending and running
        pending_count = await redis.zcard(KEY_PENDING)
        running_count = await redis.zcard(KEY_RUNNING)

        # Get stats hash
        stats_data = await redis.hgetall(KEY_STATS)

        return QueueStats(
            queued_count=pending_count,
            running_count=running_count,
            succeeded_count=int(stats_data.get("succeeded", 0)),
            failed_count=int(stats_data.get("failed", 0)),
            canceled_count=int(stats_data.get("canceled", 0)),
            counts_by_kind={
                k.replace("total_", ""): int(v)
                for k, v in stats_data.items()
                if k.startswith("total_")
            },
        )

    async def extend_visibility(
        self,
        job_id: str,
        *,
        additional_seconds: float,
    ) -> bool:
        """Extend the visibility timeout for a running job."""
        redis = await self._get_redis()
        now = _now_timestamp()
        new_timeout = now + additional_seconds

        # Check if job is in running set
        score = await redis.zscore(KEY_RUNNING, job_id)
        if score is None:
            return False

        # Update visibility timeout
        await redis.zadd(KEY_RUNNING, {job_id: new_timeout})
        await redis.hset(
            f"{KEY_JOBS}:{job_id}",
            "locked_at",
            _timestamp_to_iso(now),
        )
        return True

    def _dict_to_job(self, data: dict[str, str]) -> Job:
        """Convert a Redis hash to a Job model."""
        payload: dict[str, Any] = {}
        if data.get("payload"):
            try:
                payload = json.loads(data["payload"])
            except Exception:
                payload = {}

        def _parse_dt(value: str | None) -> datetime | None:
            if not value:
                return None
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None

        return Job(
            id=data["id"],
            kind=JobKind(data["kind"]),
            ref_id=data["ref_id"],
            status=JobStatus(data["status"]),
            payload=payload,
            attempts=int(data.get("attempts", "0") or "0"),
            max_attempts=int(data.get("max_attempts", "1") or "1"),
            available_at=_parse_dt(data.get("available_at")),
            locked_at=_parse_dt(data.get("locked_at")),
            locked_by=data.get("locked_by") or None,
            last_error=data.get("last_error") or None,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
