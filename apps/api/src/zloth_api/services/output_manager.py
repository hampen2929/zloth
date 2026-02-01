"""Output Manager for streaming CLI output to clients.

This module provides a pub/sub mechanism for streaming CLI tool output
(Claude Code, Codex, Gemini) in real-time to connected clients via SSE.

Additionally, it can persist output lines to the shared SQLite database so
that API and Worker processes can exchange logs across process boundaries.
When persistence is enabled, the API can serve live logs via REST polling
even if the Worker produced the logs in a different process.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Optional

from zloth_api.storage.db import Database

logger = logging.getLogger(__name__)


@dataclass
class OutputLine:
    """Represents a single line of CLI output."""

    line_number: int
    content: str
    timestamp: float = field(default_factory=time.time)


class OutputManager:
    """Manages output streams for runs with pub/sub pattern.

    This class provides:
    - Publishing output lines from CLI executors
    - Subscribing to output streams for SSE endpoints
    - History retention for late-joining subscribers
    - Automatic cleanup of completed runs

    Thread-safety: This class is designed for asyncio and uses per-run locks
    to minimize contention during concurrent task execution.
    """

    def __init__(
        self,
        max_history: int = 10000,
        cleanup_after: float = 3600.0,
        max_queue_size: int = 5000,
        *,
        db: Optional[Database] = None,
    ):
        """Initialize OutputManager.

        Args:
            max_history: Maximum number of lines to retain per run.
            cleanup_after: Seconds after completion to cleanup stream.
            max_queue_size: Maximum size of subscriber queues.
            db: Optional Database for persistence across processes.
        """
        self.max_history = max_history
        self.cleanup_after = cleanup_after
        self.max_queue_size = max_queue_size
        self._db = db

        # run_id -> list of OutputLine (history)
        self._streams: dict[str, list[OutputLine]] = {}

        # run_id -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[OutputLine | None]]] = {}

        # run_id -> completion timestamp (None if still running)
        self._completed: dict[str, float | None] = {}

        # Global lock for managing per-run locks (only used for lock creation/deletion)
        self._global_lock = asyncio.Lock()

        # Per-run locks to minimize contention during concurrent execution
        self._run_locks: dict[str, asyncio.Lock] = {}

        # Persisted line counters (next line number per stream when DB is used)
        self._counters: dict[str, int] = {}

    async def _get_run_lock(self, run_id: str) -> asyncio.Lock:
        """Get or create a lock for a specific run.

        Args:
            run_id: The run ID.

        Returns:
            Lock for the specified run.
        """
        if run_id not in self._run_locks:
            async with self._global_lock:
                # Double-check after acquiring global lock
                if run_id not in self._run_locks:
                    self._run_locks[run_id] = asyncio.Lock()
        return self._run_locks[run_id]

    async def _ensure_initialized(self, run_id: str) -> None:
        """Ensure stream data structures are initialized for a run.

        This must be called while holding the run's lock.

        Args:
            run_id: The run ID.
        """
        if run_id not in self._streams:
            self._streams[run_id] = []
            self._subscribers[run_id] = []
            self._completed[run_id] = None
            logger.debug(f"Initialized stream for run {run_id}")

    async def _ensure_counter(self, run_id: str) -> None:
        """Ensure persisted line counter is initialized from DB when available."""
        if self._db is None:
            return
        if run_id in self._counters:
            return
        # Read max line_number from DB for this stream
        try:
            conn = self._db.connection
            cursor = await conn.execute(
                "SELECT MAX(line_number) AS max_ln FROM output_streams WHERE stream_id = ?",
                (run_id,),
            )
            row = await cursor.fetchone()
            max_ln = int(row["max_ln"]) if row and row["max_ln"] is not None else -1
            self._counters[run_id] = max_ln + 1
        except Exception:
            # If anything goes wrong, start from 0 (better to stream than to fail)
            self._counters[run_id] = 0

    def publish(self, run_id: str, line: str) -> None:
        """Publish an output line for a run (sync version).

        This method is synchronous and schedules the async work to run
        in the event loop. Use publish_async for immediate delivery.

        Args:
            run_id: The run ID.
            line: The output line content.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._publish_async(run_id, line))
        except RuntimeError:
            # No running event loop - log and skip
            logger.warning(f"No event loop for publishing to run {run_id}")

    async def publish_async(self, run_id: str, line: str) -> None:
        """Publish an output line for a run (async version).

        This method awaits the publication, ensuring immediate delivery
        to all subscribers. Prefer this in async contexts.

        Args:
            run_id: The run ID.
            line: The output line content.
        """
        await self._publish_async(run_id, line)

    async def _publish_async(self, run_id: str, line: str) -> None:
        """Async implementation of publish.

        Args:
            run_id: The run ID.
            line: The output line content.
        """
        run_lock = await self._get_run_lock(run_id)
        async with run_lock:
            # Initialize stream if needed
            await self._ensure_initialized(run_id)
            await self._ensure_counter(run_id)

            # Create output line
            if self._db is not None:
                # Use persisted counter for cross-process consistency
                line_number = self._counters.get(run_id, 0)
                self._counters[run_id] = line_number + 1
            else:
                line_number = len(self._streams[run_id])
            output_line = OutputLine(
                line_number=line_number,
                content=line,
            )

            # Add to history (with limit)
            self._streams[run_id].append(output_line)
            if len(self._streams[run_id]) > self.max_history:
                # Remove oldest lines
                self._streams[run_id] = self._streams[run_id][-self.max_history :]

            # Persist to DB if available
            if self._db is not None:
                try:
                    await self._db.execute(
                        """
                        INSERT INTO output_streams (id, stream_id, line_number, content, ts, created_at)
                        VALUES (?, ?, ?, ?, ?, datetime('now'))
                        """,
                        (
                            f"out_{uuid.uuid4().hex[:16]}",
                            run_id,
                            output_line.line_number,
                            output_line.content,
                            float(output_line.timestamp),
                        ),
                    )
                except Exception as e:
                    logger.warning("Failed to persist output line for %s: %s", run_id, e)

            # Notify all subscribers (copy list to avoid modification during iteration)
            subscribers = list(self._subscribers[run_id])
            subscriber_count = len(subscribers)
            logger.debug(
                f"Publishing line {line_number} to {subscriber_count} subscribers for run {run_id}"
            )

        # Notify subscribers outside the lock to reduce contention
        dropped_count = 0
        for queue in subscribers:
            try:
                queue.put_nowait(output_line)
            except asyncio.QueueFull:
                dropped_count += 1

        if dropped_count > 0:
            logger.warning(
                f"Queue full for {dropped_count}/{subscriber_count} subscribers of run {run_id}"
            )

    async def subscribe(
        self,
        run_id: str,
        from_line: int = 0,
    ) -> AsyncIterator[OutputLine]:
        """Subscribe to output stream for a run.

        This yields:
        1. Historical lines from from_line onwards
        2. New lines as they are published
        3. Stops when the run is marked complete

        Args:
            run_id: The run ID.
            from_line: Line number to start from (0-based).

        Yields:
            OutputLine objects.
        """
        queue: asyncio.Queue[OutputLine | None] = asyncio.Queue(maxsize=self.max_queue_size)

        run_lock = await self._get_run_lock(run_id)
        async with run_lock:
            # Initialize stream if needed
            await self._ensure_initialized(run_id)

            # Register subscriber
            self._subscribers[run_id].append(queue)
            logger.info(
                f"Subscriber registered for run {run_id}, "
                f"total subscribers: {len(self._subscribers[run_id])}"
            )

            # Get existing history
            history = list(self._streams[run_id][from_line:])
            is_completed = self._completed[run_id] is not None
            logger.info(
                f"Subscribe to run {run_id}: history={len(history)} lines, completed={is_completed}"
            )

        try:
            # Yield historical lines
            for output_line in history:
                yield output_line

            # If already completed, we're done
            if is_completed:
                return

            # Wait for new lines
            while True:
                try:
                    # Wait with timeout to allow checking completion
                    # Note: queue.get() returns OutputLine | None per queue's type
                    output_line = await asyncio.wait_for(
                        queue.get(),  # type: ignore[arg-type]
                        timeout=1.0,
                    )

                    if output_line is None:
                        # Completion signal
                        break

                    yield output_line

                except TimeoutError:
                    # Check if completed while waiting (use run lock, not global lock)
                    async with run_lock:
                        if self._completed.get(run_id) is not None:
                            break
                    continue

        finally:
            # Unregister subscriber
            async with run_lock:
                if run_id in self._subscribers:
                    try:
                        self._subscribers[run_id].remove(queue)
                    except ValueError:
                        pass  # Already removed

    async def mark_complete(self, run_id: str) -> None:
        """Mark a run as complete.

        This notifies all subscribers that no more output will be published.
        If the run was never initialized (no output was published), it will
        be initialized first to ensure proper cleanup.

        Args:
            run_id: The run ID.
        """
        run_lock = await self._get_run_lock(run_id)
        async with run_lock:
            # Initialize if not yet done (handles case where run completes without output)
            await self._ensure_initialized(run_id)

            self._completed[run_id] = time.time()

            # Get subscribers list (copy to avoid modification during iteration)
            subscribers = list(self._subscribers.get(run_id, []))

        # Send completion signal outside the lock to reduce contention
        for queue in subscribers:
            try:
                queue.put_nowait(None)
            except asyncio.QueueFull:
                # Clear some space and retry
                try:
                    queue.get_nowait()
                    queue.put_nowait(None)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass  # Best effort

        logger.info(f"Marked run {run_id} as complete")

    async def get_history(self, run_id: str, from_line: int = 0) -> list[OutputLine]:
        """Get historical output lines for a run.

        Args:
            run_id: The run ID.
            from_line: Line number to start from (0-based).

        Returns:
            List of OutputLine objects.
        """
        # If DB is available, read from persisted storage for cross-process support
        if self._db is not None:
            try:
                conn = self._db.connection
                cursor = await conn.execute(
                    (
                        "SELECT line_number, content, ts "
                        "FROM output_streams "
                        "WHERE stream_id = ? AND line_number >= ? "
                        "ORDER BY line_number ASC"
                    ),
                    (run_id, from_line),
                )
                rows = await cursor.fetchall()
                result: list[OutputLine] = []
                for r in rows:
                    ts = float(r["ts"]) if r["ts"] is not None else time.time()
                    result.append(
                        OutputLine(
                            line_number=int(r["line_number"]),
                            content=r["content"],
                            timestamp=ts,
                        )
                    )
                return result
            except Exception as e:
                logger.warning("Failed to read persisted output for %s: %s", run_id, e)
                
        # Fallback to in-memory history
        run_lock = await self._get_run_lock(run_id)
        async with run_lock:
            if run_id not in self._streams:
                return []
            return list(self._streams[run_id][from_line:])

    async def is_complete(self, run_id: str) -> bool:
        """Check if a run is marked as complete.

        Args:
            run_id: The run ID.

        Returns:
            True if complete, False otherwise.
        """
        run_lock = await self._get_run_lock(run_id)
        async with run_lock:
            return self._completed.get(run_id) is not None

    async def cleanup_old_streams(self) -> int:
        """Clean up streams for completed runs that are past cleanup_after.

        Returns:
            Number of streams cleaned up.
        """
        now = time.time()
        to_cleanup: list[str] = []

        # First pass: identify runs to cleanup (using global lock for iteration)
        async with self._global_lock:
            for run_id, completed_at in list(self._completed.items()):
                if completed_at is not None:
                    if now - completed_at > self.cleanup_after:
                        to_cleanup.append(run_id)

        # Second pass: cleanup each run (using per-run locks)
        for run_id in to_cleanup:
            run_lock = await self._get_run_lock(run_id)
            async with run_lock:
                self._streams.pop(run_id, None)
                self._subscribers.pop(run_id, None)
                self._completed.pop(run_id, None)

            # Clean up the run lock itself
            async with self._global_lock:
                self._run_locks.pop(run_id, None)

        if to_cleanup:
            logger.info(f"Cleaned up {len(to_cleanup)} old output streams")

        return len(to_cleanup)

    async def get_stats(self) -> dict:
        """Get statistics about the output manager.

        Returns:
            Dict with stats.
        """
        # Use global lock for stats to get a consistent snapshot
        async with self._global_lock:
            active_runs = sum(1 for completed in self._completed.values() if completed is None)
            completed_runs = sum(
                1 for completed in self._completed.values() if completed is not None
            )
            total_lines = sum(len(lines) for lines in self._streams.values())
            total_subscribers = sum(len(subs) for subs in self._subscribers.values())

            return {
                "active_runs": active_runs,
                "completed_runs": completed_runs,
                "total_lines": total_lines,
                "total_subscribers": total_subscribers,
                "run_locks": len(self._run_locks),
            }
