"""Compare routes for multi-executor output comparison."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from zloth_api.dependencies import get_compare_service, get_output_manager
from zloth_api.domain.models import (
    Comparison,
    ComparisonCreated,
    ComparisonRequest,
)
from zloth_api.services.compare_service import CompareService
from zloth_api.services.output_manager import OutputManager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["compare"])


@router.post("/tasks/{task_id}/compare", response_model=ComparisonCreated, status_code=201)
async def create_comparison(
    task_id: str,
    data: ComparisonRequest,
    compare_service: CompareService = Depends(get_compare_service),
) -> ComparisonCreated:
    """Create a new comparison for runs in a task.

    This endpoint starts a background comparison analysis of multiple runs
    from different executors. Use the GET endpoint or logs endpoint to
    check status and results.

    Args:
        task_id: The task ID.
        data: Comparison request with run IDs and analysis model/executor.

    Returns:
        The created comparison ID.
    """
    try:
        comparison = await compare_service.create_comparison(task_id, data)
        return ComparisonCreated(comparison_id=comparison.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/comparisons", response_model=list[Comparison])
async def list_comparisons(
    task_id: str,
    compare_service: CompareService = Depends(get_compare_service),
) -> list[Comparison]:
    """List all comparisons for a task."""
    return await compare_service.list_comparisons(task_id)


@router.get("/comparisons/{comparison_id}", response_model=Comparison)
async def get_comparison(
    comparison_id: str,
    compare_service: CompareService = Depends(get_compare_service),
) -> Comparison:
    """Get comparison details."""
    comparison = await compare_service.get_comparison(comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return comparison


@router.get("/comparisons/{comparison_id}/logs")
async def get_comparison_logs(
    comparison_id: str,
    from_line: int = Query(0, ge=0, description="Line number to start from (0-based)"),
    compare_service: CompareService = Depends(get_compare_service),
    output_manager: OutputManager = Depends(get_output_manager),
) -> dict[str, object]:
    """Get comparison execution logs (for polling).

    Returns logs from OutputManager if the comparison is in progress,
    or indicates completion if finished.

    Args:
        comparison_id: The comparison ID.
        from_line: Line number to start from (0-based).

    Returns:
        Object with logs array (OutputLine format), is_complete flag, and total line count.
    """
    comparison = await compare_service.get_comparison(comparison_id)
    if not comparison:
        raise HTTPException(status_code=404, detail="Comparison not found")

    # Get logs from OutputManager
    output_logs = await output_manager.get_history(comparison_id, from_line)
    is_complete = await output_manager.is_complete(comparison_id)

    status_val = (
        comparison.status.value if hasattr(comparison.status, "value") else comparison.status
    )

    return {
        "logs": [
            {
                "line_number": ol.line_number,
                "content": ol.content,
                "timestamp": ol.timestamp,
            }
            for ol in output_logs
        ],
        "is_complete": is_complete or status_val in ("succeeded", "failed"),
        "total_lines": from_line + len(output_logs),
        "comparison_status": status_val,
    }
