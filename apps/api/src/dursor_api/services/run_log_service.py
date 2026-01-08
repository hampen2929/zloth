"""Run log service (persist + stream).

This service provides append-only run log storage in SQLite plus an in-memory
pub/sub layer for real-time streaming via SSE.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from dursor_api.domain.models import RunLogEntry
from dursor_api.storage.dao import RunLogDAO

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


@dataclass(frozen=True)
class RunLogStreamEvent:
    """Event emitted to SSE subscribers."""

    type: str  # "log" | "done"
    data: dict[str, Any]


class RunLogService:
    """Persisted run logs + in-memory streaming broker."""

    def __init__(self, dao: RunLogDAO):
        self._dao = dao
        self._lock = asyncio.Lock()
        self._subscribers: dict[str, set[asyncio.Queue[RunLogStreamEvent]]] = {}
        self._finished: set[str] = set()

    async def append(self, run_id: str, stream: str, text: str) -> RunLogEntry:
        """Append a log entry and publish to subscribers."""
        cleaned = text.rstrip("\n")
        now = datetime.utcnow()
        seq = await self._dao.append(run_id=run_id, stream=stream, text=cleaned, ts=now.isoformat())
        entry = RunLogEntry(
            seq=seq,
            ts=now,
            stream=stream,  # validated at API boundary
            text=cleaned,
        )
        await self._publish(run_id, RunLogStreamEvent(type="log", data=entry.model_dump(mode="json")))
        return entry

    async def list(self, run_id: str, after_seq: int = 0, limit: int = 500) -> list[RunLogEntry]:
        """List persisted log entries."""
        return await self._dao.list(run_id=run_id, after_seq=after_seq, limit=limit)

    async def mark_finished(self, run_id: str) -> None:
        """Mark a run as finished and notify subscribers."""
        async with self._lock:
            if run_id in self._finished:
                return
            self._finished.add(run_id)

        await self._publish(run_id, RunLogStreamEvent(type="done", data={"run_id": run_id}))

    async def subscribe(self, run_id: str) -> tuple[asyncio.Queue[RunLogStreamEvent], bool]:
        """Subscribe to live events for a run.

        Returns:
            (queue, is_finished)
        """
        queue: asyncio.Queue[RunLogStreamEvent] = asyncio.Queue(maxsize=500)
        async with self._lock:
            subs = self._subscribers.setdefault(run_id, set())
            subs.add(queue)
            is_finished = run_id in self._finished
        return queue, is_finished

    async def unsubscribe(self, run_id: str, queue: asyncio.Queue[RunLogStreamEvent]) -> None:
        async with self._lock:
            subs = self._subscribers.get(run_id)
            if not subs:
                return
            subs.discard(queue)
            if not subs:
                self._subscribers.pop(run_id, None)

    async def _publish(self, run_id: str, event: RunLogStreamEvent) -> None:
        async with self._lock:
            queues = list(self._subscribers.get(run_id, set()))

        if not queues:
            return

        for q in queues:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                # Best-effort: drop if subscriber is too slow.
                logger.debug("Dropping run log event due to full queue", extra={"run_id": run_id})

    async def stream(
        self,
        run_id: str,
        from_seq: int = 0,
        initial_limit: int = 500,
    ) -> AsyncGenerator[RunLogStreamEvent, None]:
        """Yield persisted backlog then live events."""
        backlog = await self.list(run_id=run_id, after_seq=from_seq, limit=initial_limit)
        for entry in backlog:
            yield RunLogStreamEvent(type="log", data=entry.model_dump(mode="json"))
            from_seq = max(from_seq, entry.seq)

        queue, is_finished = await self.subscribe(run_id)
        try:
            if is_finished:
                # Still allow consumers to reconnect and immediately terminate.
                yield RunLogStreamEvent(type="done", data={"run_id": run_id})
                return

            while True:
                event = await queue.get()
                yield event
                if event.type == "done":
                    return
        finally:
            await self.unsubscribe(run_id, queue)

