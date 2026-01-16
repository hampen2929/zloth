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


@router.post("", response_model=TaskBreakdownResponse, status_code=202)
async def start_breakdown(
    request: TaskBreakdownRequest,
    breakdown_service: BreakdownService = Depends(get_breakdown_service),
) -> TaskBreakdownResponse:
    """Start task breakdown in background.

    This endpoint starts an AI agent (Claude Code, Codex, or Gemini CLI)
    to analyze the codebase and decompose the provided content into tasks.
    The breakdown runs in the background and returns immediately with a
    breakdown_id that can be used to poll for results.

    Args:
        request: Breakdown request with content and executor type.
        breakdown_service: Breakdown service instance.

    Returns:
        TaskBreakdownResponse with RUNNING status and breakdown_id.
    """
    return await breakdown_service.start_breakdown(request)


@router.get("/{breakdown_id}", response_model=TaskBreakdownResponse)
async def get_breakdown_result(
    breakdown_id: str,
    breakdown_service: BreakdownService = Depends(get_breakdown_service),
) -> TaskBreakdownResponse:
    """Get breakdown result by ID.

    Poll this endpoint to check breakdown status and get results.
    The status will be RUNNING while in progress, SUCCEEDED when complete,
    or FAILED if an error occurred.

    Args:
        breakdown_id: Breakdown session ID.
        breakdown_service: Breakdown service instance.

    Returns:
        TaskBreakdownResponse with current status and results.
    """
    result = await breakdown_service.get_result(breakdown_id)
    if not result:
        raise HTTPException(status_code=404, detail="Breakdown not found")
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
