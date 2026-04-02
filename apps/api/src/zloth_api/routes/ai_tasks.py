"""AI task creation routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from zloth_api.domain.enums import CodingMode
from zloth_api.domain.models import (
    AITaskCreateRequest,
    AITaskCreateResponse,
)

router = APIRouter(prefix="/tasks/ai-create", tags=["ai-tasks"])


async def get_ai_task_creator() -> Any:
    """Get AI task creator service dependency."""
    from zloth_api.dependencies import get_ai_task_creator_service

    return await get_ai_task_creator_service()


async def get_agentic_orchestrator() -> Any:
    """Get agentic orchestrator dependency."""
    from zloth_api.dependencies import get_agentic_orchestrator

    return await get_agentic_orchestrator()


@router.post("", response_model=AITaskCreateResponse, status_code=201)
async def create_ai_tasks(
    data: AITaskCreateRequest,
    ai_task_creator: Any = Depends(get_ai_task_creator),
) -> AITaskCreateResponse:
    """Start AI-driven task creation.

    Analyzes the codebase using a CLI executor and creates tasks
    based on the provided instruction. Runs in background.

    Args:
        data: AI task creation request.
        ai_task_creator: AI task creator service.

    Returns:
        AITaskCreateResponse with session_id for polling.
    """
    return await ai_task_creator.start(data)


@router.get("/{session_id}", response_model=AITaskCreateResponse)
async def get_ai_task_result(
    session_id: str,
    ai_task_creator: Any = Depends(get_ai_task_creator),
) -> AITaskCreateResponse:
    """Get AI task creation result.

    Poll this endpoint to check if the AI task creation is complete.

    Args:
        session_id: Session ID from the create response.
        ai_task_creator: AI task creator service.

    Returns:
        AITaskCreateResponse with current status and results.

    Raises:
        HTTPException: If session not found.
    """
    result = await ai_task_creator.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.get("/{session_id}/logs")
async def get_ai_task_logs(
    session_id: str,
    from_line: int = 0,
    ai_task_creator: Any = Depends(get_ai_task_creator),
) -> dict[str, Any]:
    """Get AI task creation logs.

    Args:
        session_id: Session ID.
        from_line: Line number to start from.
        ai_task_creator: AI task creator service.

    Returns:
        Dict with logs, is_complete, and total_lines.
    """
    logs, is_complete = await ai_task_creator.get_logs(session_id, from_line)
    return {
        "logs": logs,
        "is_complete": is_complete,
        "total_lines": len(logs) + from_line,
    }


@router.post("/{session_id}/auto-start")
async def auto_start_tasks(
    session_id: str,
    ai_task_creator: Any = Depends(get_ai_task_creator),
    orchestrator: Any = Depends(get_agentic_orchestrator),
) -> dict[str, Any]:
    """Auto-start agentic execution for AI-created tasks.

    Call this after AI task creation completes to start execution
    on all created tasks.

    Args:
        session_id: Session ID.
        ai_task_creator: AI task creator service.
        orchestrator: Agentic orchestrator service.

    Returns:
        Dict with started task IDs and any errors.

    Raises:
        HTTPException: If session not found or not completed.
    """
    result = await ai_task_creator.get_result(session_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Session not found")

    if result.status.value != "succeeded":
        raise HTTPException(
            status_code=400,
            detail=f"Session is not completed (status: {result.status.value})",
        )

    started: list[str] = []
    errors: list[dict[str, str]] = []

    for task in result.created_tasks:
        try:
            mode = task.coding_mode
            if mode == CodingMode.INTERACTIVE:
                mode = CodingMode.SEMI_AUTO

            await orchestrator.start_task(
                task_id=task.id,
                instruction=task.instruction,
                mode=mode,
            )
            started.append(task.id)
        except (ValueError, RuntimeError) as e:
            errors.append({"task_id": task.id, "error": str(e)})

    return {
        "started_task_ids": started,
        "errors": errors,
    }
