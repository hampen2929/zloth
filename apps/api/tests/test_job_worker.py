from __future__ import annotations

import asyncio

import pytest

from zloth_api.services.job_worker import JobWorker


class _FlakyQueue:
    def __init__(self) -> None:
        self.calls = 0

    async def dequeue(self, *, locked_by: str, visibility_timeout_seconds: int) -> None:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("boom")
        return None


@pytest.mark.asyncio
async def test_worker_survives_dequeue_exception() -> None:
    queue = _FlakyQueue()
    worker = JobWorker(queue=queue, handlers={}, poll_interval_seconds=0.01)

    worker.start()

    for _ in range(50):
        if queue.calls >= 2:
            break
        await asyncio.sleep(0.01)

    assert worker.is_running is True
    await worker.stop()
