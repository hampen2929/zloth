"""Run routes."""

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.domain.models import Run, RunCreate, RunsCreated
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
