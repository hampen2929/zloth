"""Agentic execution routes."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.config import settings
from dursor_api.domain.models import (
    AgenticCancelResponse,
    AgenticStartRequest,
    AgenticStartResponse,
    AgenticState,
    AgenticStatusResponse,
)
from dursor_api.services.agentic_orchestrator import AgenticOrchestrator
from dursor_api.storage.dao import TaskDAO

router = APIRouter(prefix="/tasks", tags=["agentic"])


# Placeholder for dependency injection - will be replaced in dependencies.py
async def get_orchestrator() -> AgenticOrchestrator:
    """Get the agentic orchestrator."""
    from dursor_api.dependencies import get_agentic_orchestrator

    return await get_agentic_orchestrator()


async def get_task_dao() -> TaskDAO:
    """Get task DAO."""
    from dursor_api.dependencies import get_task_dao as _get_task_dao

    return await _get_task_dao()


@router.post("/{task_id}/agentic", response_model=AgenticStartResponse)
async def start_agentic_execution(
    task_id: str,
    request: AgenticStartRequest,
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator),
    task_dao: TaskDAO = Depends(get_task_dao),
) -> AgenticStartResponse:
    """Start full agentic execution cycle for a task.

    This starts the autonomous development workflow:
    1. Claude Code generates/modifies code
    2. Commits and creates/updates PR
    3. Waits for CI
    4. If CI fails, auto-fixes
    5. Codex reviews code
    6. If review fails, addresses feedback
    7. Auto-merges on success

    Args:
        task_id: Task ID to start agentic execution for.
        request: Agentic start request with instruction and config.
        orchestrator: Agentic orchestrator service.
        task_dao: Task DAO.

    Returns:
        AgenticStartResponse with run ID and status.
    """
    # Get task
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Check if agentic mode is enabled
    if not settings.agentic_enabled:
        raise HTTPException(status_code=400, detail="Agentic mode is disabled")

    # Check for existing active agentic execution
    existing = await orchestrator.get_status(task_id)
    if existing and existing.phase.value not in ("completed", "failed"):
        raise HTTPException(
            status_code=409,
            detail=f"Task already has active agentic execution in phase: {existing.phase.value}",
        )

    # Get workspace path
    workspace_path = Path(settings.workspaces_dir or ".") / task.repo_id

    # Start agentic execution
    state = await orchestrator.start_task(
        task=task,
        instruction=request.instruction,
        workspace_path=workspace_path,
        config=request.config,
    )

    return AgenticStartResponse(
        agentic_run_id=state.id,
        status="started",
    )


@router.get("/{task_id}/agentic/status", response_model=AgenticStatusResponse)
async def get_agentic_status(
    task_id: str,
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator),
    task_dao: TaskDAO = Depends(get_task_dao),
) -> AgenticStatusResponse:
    """Get agentic execution status for a task.

    Args:
        task_id: Task ID.
        orchestrator: Agentic orchestrator service.
        task_dao: Task DAO.

    Returns:
        AgenticStatusResponse with current phase and details.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Get status
    state = await orchestrator.get_status(task_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"No agentic execution found for task: {task_id}",
        )

    return AgenticStatusResponse(
        phase=state.phase,
        iteration=state.iteration,
        ci_iterations=state.ci_iterations,
        review_iterations=state.review_iterations,
        pr_number=state.pr_number,
        last_ci_result=state.last_ci_result,
        last_review_result=state.last_review_result,
        error=state.error,
    )


@router.post("/{task_id}/agentic/cancel", response_model=AgenticCancelResponse)
async def cancel_agentic_execution(
    task_id: str,
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator),
    task_dao: TaskDAO = Depends(get_task_dao),
) -> AgenticCancelResponse:
    """Cancel agentic execution for a task.

    Args:
        task_id: Task ID.
        orchestrator: Agentic orchestrator service.
        task_dao: Task DAO.

    Returns:
        AgenticCancelResponse with cancellation status.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Cancel
    cancelled = await orchestrator.cancel(task_id)

    if not cancelled:
        raise HTTPException(
            status_code=404,
            detail=f"No active agentic execution found for task: {task_id}",
        )

    return AgenticCancelResponse(cancelled=True)


@router.get("/{task_id}/agentic/state", response_model=AgenticState)
async def get_agentic_state(
    task_id: str,
    orchestrator: AgenticOrchestrator = Depends(get_orchestrator),
    task_dao: TaskDAO = Depends(get_task_dao),
) -> AgenticState:
    """Get full agentic state for a task.

    Args:
        task_id: Task ID.
        orchestrator: Agentic orchestrator service.
        task_dao: Task DAO.

    Returns:
        Full AgenticState object.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail=f"Task not found: {task_id}")

    # Get state
    state = await orchestrator.get_status(task_id)
    if not state:
        raise HTTPException(
            status_code=404,
            detail=f"No agentic execution found for task: {task_id}",
        )

    return state
