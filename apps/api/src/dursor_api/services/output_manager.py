"""Output Manager for streaming CLI output to clients.

This module provides a pub/sub mechanism for streaming CLI tool output
(Claude Code, Codex, Gemini) in real-time to connected clients via SSE.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import AsyncIterator

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

    Thread-safety: This class is designed for asyncio and uses asyncio.Queue
    for safe communication between publishers and subscribers.
    """

    def __init__(
        self,
        max_history: int = 10000,
        cleanup_after: float = 3600.0,
    ):
        """Initialize OutputManager.

        Args:
            max_history: Maximum number of lines to retain per run.
            cleanup_after: Seconds after completion to cleanup stream.
        """
        self.max_history = max_history
        self.cleanup_after = cleanup_after

        # run_id -> list of OutputLine (history)
        self._streams: dict[str, list[OutputLine]] = {}

        # run_id -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue[OutputLine | None]]] = {}

        # run_id -> completion timestamp (None if still running)
        self._completed: dict[str, float | None] = {}

        # Lock for thread-safe operations
        self._lock = asyncio.Lock()

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
        async with self._lock:
            # Initialize stream if needed
            if run_id not in self._streams:
                self._streams[run_id] = []
                self._subscribers[run_id] = []
                self._completed[run_id] = None
                logger.debug(f"Initialized stream for run {run_id}")

            # Create output line
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

            # Notify all subscribers
            subscriber_count = len(self._subscribers[run_id])
            logger.debug(f"Publishing line {line_number} to {subscriber_count} subscribers for run {run_id}")
            for queue in self._subscribers[run_id]:
                try:
                    queue.put_nowait(output_line)
                except asyncio.QueueFull:
                    logger.warning(f"Queue full for subscriber of run {run_id}")

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
        queue: asyncio.Queue[OutputLine | None] = asyncio.Queue(maxsize=1000)

        async with self._lock:
            # Initialize stream if needed
            if run_id not in self._streams:
                self._streams[run_id] = []
                self._subscribers[run_id] = []
                self._completed[run_id] = None
                logger.info(f"Subscriber initialized new stream for run {run_id}")

            # Register subscriber
            self._subscribers[run_id].append(queue)
            logger.info(f"Subscriber registered for run {run_id}, total subscribers: {len(self._subscribers[run_id])}")

            # Get existing history
            history = self._streams[run_id][from_line:]
            is_completed = self._completed[run_id] is not None
            logger.info(f"Subscribe to run {run_id}: history={len(history)} lines, completed={is_completed}")

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
                    output_line: OutputLine | None = await asyncio.wait_for(
                        queue.get(), timeout=1.0
                    )

                    if output_line is None:
                        # Completion signal
                        break

                    yield output_line

                except asyncio.TimeoutError:
                    # Check if completed while waiting
                    async with self._lock:
                        if self._completed.get(run_id) is not None:
                            break
                    continue

        finally:
            # Unregister subscriber
            async with self._lock:
                if run_id in self._subscribers:
                    try:
                        self._subscribers[run_id].remove(queue)
                    except ValueError:
                        pass  # Already removed

    async def mark_complete(self, run_id: str) -> None:
        """Mark a run as complete.

        This notifies all subscribers that no more output will be published.

        Args:
            run_id: The run ID.
        """
        async with self._lock:
            if run_id not in self._completed:
                return

            self._completed[run_id] = time.time()

            # Send completion signal to all subscribers
            for queue in self._subscribers.get(run_id, []):
                try:
                    queue.put_nowait(None)
                except asyncio.QueueFull:
                    pass

        logger.info(f"Marked run {run_id} as complete")

    async def get_history(self, run_id: str, from_line: int = 0) -> list[OutputLine]:
        """Get historical output lines for a run.

        Args:
            run_id: The run ID.
            from_line: Line number to start from (0-based).

        Returns:
            List of OutputLine objects.
        """
        async with self._lock:
            if run_id not in self._streams:
                return []
            return self._streams[run_id][from_line:]

    async def is_complete(self, run_id: str) -> bool:
        """Check if a run is marked as complete.

        Args:
            run_id: The run ID.

        Returns:
            True if complete, False otherwise.
        """
        async with self._lock:
            return self._completed.get(run_id) is not None

    async def cleanup_old_streams(self) -> int:
        """Clean up streams for completed runs that are past cleanup_after.

        Returns:
            Number of streams cleaned up.
        """
        now = time.time()
        to_cleanup: list[str] = []

        async with self._lock:
            for run_id, completed_at in self._completed.items():
                if completed_at is not None:
                    if now - completed_at > self.cleanup_after:
                        to_cleanup.append(run_id)

            for run_id in to_cleanup:
                self._streams.pop(run_id, None)
                self._subscribers.pop(run_id, None)
                self._completed.pop(run_id, None)

        if to_cleanup:
            logger.info(f"Cleaned up {len(to_cleanup)} old output streams")

        return len(to_cleanup)

    async def get_stats(self) -> dict[str, int]:
        """Get statistics about the output manager.

        Returns:
            Dict with stats.
        """
        async with self._lock:
            active_runs = sum(
                1 for completed in self._completed.values() if completed is None
            )
            completed_runs = sum(
                1 for completed in self._completed.values() if completed is not None
            )
            total_lines = sum(len(lines) for lines in self._streams.values())
            total_subscribers = sum(
                len(subs) for subs in self._subscribers.values()
            )

            return {
                "active_runs": active_runs,
                "completed_runs": completed_runs,
                "total_lines": total_lines,
                "total_subscribers": total_subscribers,
            }
