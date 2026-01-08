"""Run routes."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from dursor_api.domain.models import Run, RunCreate, RunLogEntry, RunsCreated
from dursor_api.dependencies import get_run_service
from dursor_api.services.run_service import RunService

router = APIRouter(tags=["runs"])


@router.post("/tasks/{task_id}/runs", response_model=RunsCreated, status_code=201)
async def create_runs(
    task_id: str,
    data: RunCreate,
    run_service: RunService = Depends(get_run_service),
) -> RunsCreated:
    """Create runs for multiple models (parallel execution)."""
    try:
        runs = await run_service.create_runs(task_id, data)
        return RunsCreated(run_ids=[r.id for r in runs])
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/runs", response_model=list[Run])
async def list_runs(
    task_id: str,
    run_service: RunService = Depends(get_run_service),
) -> list[Run]:
    """List runs for a task."""
    return await run_service.list(task_id)


@router.get("/runs/{run_id}", response_model=Run)
async def get_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
) -> Run:
    """Get a run by ID."""
    run = await run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.get("/runs/{run_id}/logs", response_model=list[RunLogEntry])
async def list_run_logs(
    run_id: str,
    after_seq: int = Query(0, ge=0),
    limit: int = Query(500, ge=1, le=2000),
    run_service: RunService = Depends(get_run_service),
) -> list[RunLogEntry]:
    """List persisted log entries for a run."""
    run = await run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return await run_service.run_log_service.list(run_id=run_id, after_seq=after_seq, limit=limit)


@router.get("/runs/{run_id}/logs/stream")
async def stream_run_logs(
    run_id: str,
    request: Request,
    from_seq: int = Query(0, ge=0),
    run_service: RunService = Depends(get_run_service),
) -> StreamingResponse:
    """Stream run logs as Server-Sent Events (SSE)."""
    run = await run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def gen():
        # Backlog first
        backlog = await run_service.run_log_service.list(run_id=run_id, after_seq=from_seq, limit=1000)
        for entry in backlog:
            if await request.is_disconnected():
                return
            payload = {"type": "log", "data": entry.model_dump(mode="json")}
            yield f"event: log\ndata: {json.dumps(payload)}\n\n"

        queue, is_finished = await run_service.run_log_service.subscribe(run_id)
        try:
            if is_finished:
                yield f"event: done\ndata: {json.dumps({'type': 'done', 'data': {'run_id': run_id}})}\n\n"
                return

            while True:
                if await request.is_disconnected():
                    return

                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15.0)
                except TimeoutError:
                    # Keep-alive to prevent proxy timeouts
                    yield ": ping\n\n"
                    continue

                yield f"event: {event.type}\ndata: {json.dumps({'type': event.type, 'data': event.data})}\n\n"
                if event.type == "done":
                    return
        finally:
            await run_service.run_log_service.unsubscribe(run_id, queue)

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable buffering on some reverse proxies (nginx)
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/runs/{run_id}/cancel", status_code=204)
async def cancel_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
) -> None:
    """Cancel a run."""
    cancelled = await run_service.cancel(run_id)
    if not cancelled:
        raise HTTPException(status_code=400, detail="Run cannot be cancelled")


@router.delete("/runs/{run_id}/worktree", status_code=204)
async def cleanup_worktree(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
) -> None:
    """Clean up the worktree for a Claude Code run.

    This endpoint removes the worktree without creating a PR.
    Use this when you want to discard the changes.
    """
    cleaned = await run_service.cleanup_worktree(run_id)
    if not cleaned:
        raise HTTPException(status_code=400, detail="Run has no worktree or not found")
