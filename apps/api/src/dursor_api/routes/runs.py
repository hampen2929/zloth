"""Run routes."""

import json
import logging
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from dursor_api.domain.models import Run, RunCreate, RunsCreated
from dursor_api.dependencies import get_output_manager, get_run_service
from dursor_api.services.output_manager import OutputManager
from dursor_api.services.run_service import RunService

logger = logging.getLogger(__name__)

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


@router.get("/runs/{run_id}/logs")
async def get_run_logs(
    run_id: str,
    from_line: int = Query(0, ge=0, description="Line number to start from (0-based)"),
    run_service: RunService = Depends(get_run_service),
    output_manager: OutputManager = Depends(get_output_manager),
) -> dict[str, object]:
    """Get run logs (for polling).

    Returns logs from OutputManager if the run is in progress,
    or from the Run record if completed.

    Returns:
        Object with logs array, is_complete flag, and total line count.
    """
    # Verify run exists
    run = await run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Get logs from OutputManager (for in-progress runs)
    output_logs = await output_manager.get_history(run_id, from_line)
    is_complete = await output_manager.is_complete(run_id)

    # If we have output logs, use them
    if output_logs:
        return {
            "logs": [{"line_number": ol.line_number, "content": ol.content, "timestamp": ol.timestamp} for ol in output_logs],
            "is_complete": is_complete or run.status in ("succeeded", "failed", "canceled"),
            "total_lines": from_line + len(output_logs),
            "run_status": run.status,
        }

    # Fallback to run.logs (for completed runs or when OutputManager has no data)
    run_logs = run.logs[from_line:] if run.logs else []
    return {
        "logs": [{"line_number": from_line + i, "content": log, "timestamp": 0} for i, log in enumerate(run_logs)],
        "is_complete": run.status in ("succeeded", "failed", "canceled"),
        "total_lines": len(run.logs) if run.logs else 0,
        "run_status": run.status,
    }


@router.get("/runs/{run_id}/logs/stream")
async def stream_run_logs(
    run_id: str,
    from_line: int = Query(0, ge=0, description="Line number to start from (0-based)"),
    run_service: RunService = Depends(get_run_service),
    output_manager: OutputManager = Depends(get_output_manager),
) -> StreamingResponse:
    """Stream run logs via Server-Sent Events (SSE).

    This endpoint provides real-time streaming of CLI output during run execution.
    - Historical lines from `from_line` onwards are sent immediately
    - New lines are streamed as they arrive
    - A 'complete' event is sent when the run finishes

    Event format:
    - data events: {"line_number": int, "content": str, "timestamp": float}
    - complete event: signals end of stream
    """
    # Verify run exists
    run = await run_service.get(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    async def generate_sse() -> AsyncGenerator[str, None]:
        """Generate SSE events from output stream."""
        logger.info(f"SSE stream started for run {run_id}, from_line={from_line}")
        line_count = 0
        try:
            async for output_line in output_manager.subscribe(run_id, from_line):
                data = json.dumps({
                    "line_number": output_line.line_number,
                    "content": output_line.content,
                    "timestamp": output_line.timestamp,
                })
                yield f"data: {data}\n\n"
                line_count += 1
                if line_count % 10 == 0:
                    logger.debug(f"SSE sent {line_count} lines for run {run_id}")

            # Send completion event
            logger.info(f"SSE stream completed for run {run_id}, sent {line_count} lines")
            yield "event: complete\ndata: {}\n\n"

        except Exception as e:
            # Send error event
            logger.error(f"SSE stream error for run {run_id}: {e}")
            error_data = json.dumps({"error": str(e)})
            yield f"event: error\ndata: {error_data}\n\n"

    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )
