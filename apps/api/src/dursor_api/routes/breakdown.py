"""Task breakdown routes."""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from dursor_api.dependencies import get_breakdown_service
from dursor_api.domain.models import TaskBreakdownRequest, TaskBreakdownResponse
from dursor_api.services.breakdown_service import BreakdownService

router = APIRouter(prefix="/breakdown", tags=["breakdown"])


class BreakdownLogsResponse(BaseModel):
    """Response for breakdown logs."""

    logs: list[dict[str, Any]]
    is_complete: bool
    total_lines: int


@router.post("", response_model=TaskBreakdownResponse, status_code=201)
async def breakdown_tasks(
    request: TaskBreakdownRequest,
    breakdown_service: BreakdownService = Depends(get_breakdown_service),
) -> TaskBreakdownResponse:
    """Start breaking down hearing content into development tasks.

    This endpoint starts the breakdown process in the background and returns
    immediately with a 'running' status. Use GET /breakdown/{id} to poll
    for the final result.

    Args:
        request: Breakdown request with content and executor type.
        breakdown_service: Breakdown service instance.

    Returns:
        TaskBreakdownResponse with 'running' status and breakdown_id.
    """
    return await breakdown_service.breakdown(request)


@router.get("/{breakdown_id}", response_model=TaskBreakdownResponse)
async def get_breakdown_result(
    breakdown_id: str,
    breakdown_service: BreakdownService = Depends(get_breakdown_service),
) -> TaskBreakdownResponse:
    """Get the result of a breakdown.

    Poll this endpoint to get the final breakdown result.

    Args:
        breakdown_id: Breakdown session ID.
        breakdown_service: Breakdown service instance.

    Returns:
        TaskBreakdownResponse with current status and results.

    Raises:
        HTTPException: If breakdown not found.
    """
    result = await breakdown_service.get_result(breakdown_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Breakdown not found: {breakdown_id}")
    return result


@router.get("/{breakdown_id}/logs", response_model=BreakdownLogsResponse)
async def get_breakdown_logs(
    breakdown_id: str,
    from_line: int = 0,
    breakdown_service: BreakdownService = Depends(get_breakdown_service),
) -> BreakdownLogsResponse:
    """Get logs for a breakdown session.

    This endpoint is used for polling the breakdown execution logs.
    Clients can use from_line to get only new logs since the last poll.

    Args:
        breakdown_id: Breakdown session ID.
        from_line: Line number to start from (0-based).
        breakdown_service: Breakdown service instance.

    Returns:
        BreakdownLogsResponse with logs and completion status.
    """
    logs, is_complete = await breakdown_service.get_logs(breakdown_id, from_line)
    return BreakdownLogsResponse(
        logs=logs,
        is_complete=is_complete,
        total_lines=len(logs) + from_line,
    )
