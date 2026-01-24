"""Review routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from zloth_api.dependencies import get_output_manager, get_review_service
from zloth_api.domain.models import (
    FixInstructionRequest,
    FixInstructionResponse,
    Message,
    Review,
    ReviewCreate,
    ReviewCreated,
    ReviewSummary,
)
from zloth_api.services.output_manager import OutputManager
from zloth_api.services.review_service import ReviewService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["reviews"])


@router.post("/tasks/{task_id}/reviews", response_model=ReviewCreated, status_code=201)
async def create_review(
    task_id: str,
    data: ReviewCreate,
    review_service: ReviewService = Depends(get_review_service),
) -> ReviewCreated:
    """Create a new review for runs in a task."""
    try:
        review = await review_service.create_review(task_id, data)
        return ReviewCreated(review_id=review.id)
    except ZlothError:
        raise


@router.get("/tasks/{task_id}/reviews", response_model=list[ReviewSummary])
async def list_reviews(
    task_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> list[ReviewSummary]:
    """List reviews for a task."""
    return await review_service.list_reviews(task_id)


@router.get("/reviews/{review_id}", response_model=Review)
async def get_review(
    review_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> Review:
    """Get review details."""
    review = await review_service.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review


@router.get("/reviews/{review_id}/logs")
async def get_review_logs(
    review_id: str,
    from_line: int = Query(0, ge=0, description="Line number to start from (0-based)"),
    review_service: ReviewService = Depends(get_review_service),
    output_manager: OutputManager = Depends(get_output_manager),
) -> dict[str, object]:
    """Get review execution logs (for polling).

    Returns logs from OutputManager if the review is in progress,
    or from the Review record if completed.

    Returns:
        Object with logs array (OutputLine format), is_complete flag, and total line count.
    """
    review = await review_service.get_review(review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Use review-prefixed ID for OutputManager (same as in review_service._log_output)
    output_key = f"review-{review_id}"

    # Get logs from OutputManager (for in-progress reviews)
    output_logs = await output_manager.get_history(output_key, from_line)
    is_complete = await output_manager.is_complete(output_key)

    # If we have output logs, use them
    if output_logs:
        status_val = review.status.value if hasattr(review.status, "value") else review.status
        return {
            "logs": [
                {
                    "line_number": ol.line_number,
                    "content": ol.content,
                    "timestamp": ol.timestamp,
                }
                for ol in output_logs
            ],
            "is_complete": is_complete or review.status in ("succeeded", "failed"),
            "total_lines": from_line + len(output_logs),
            "review_status": status_val,
        }

    # Fallback to review.logs (for completed reviews or when OutputManager has no data)
    review_logs = review.logs[from_line:] if review.logs else []
    status_val = review.status.value if hasattr(review.status, "value") else review.status
    return {
        "logs": [
            {"line_number": from_line + i, "content": log, "timestamp": 0}
            for i, log in enumerate(review_logs)
        ],
        "is_complete": review.status in ("succeeded", "failed"),
        "total_lines": len(review.logs) if review.logs else 0,
        "review_status": status_val,
    }


@router.post("/reviews/{review_id}/generate-fix", response_model=FixInstructionResponse)
async def generate_fix_instruction(
    review_id: str,
    data: FixInstructionRequest,
    review_service: ReviewService = Depends(get_review_service),
) -> FixInstructionResponse:
    """Generate fix instruction from review feedbacks."""
    data.review_id = review_id  # Set from URL path
    try:
        return await review_service.generate_fix_instruction(data)
    except ZlothError:
        raise


@router.post("/reviews/{review_id}/to-message", response_model=Message)
async def add_review_to_conversation(
    review_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> Message:
    """Add completed review as a conversation message."""
    try:
        return await review_service.add_review_to_conversation(review_id)
    except ZlothError:
        raise
