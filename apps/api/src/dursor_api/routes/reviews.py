"""Review routes."""

import logging

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_review_service
from dursor_api.domain.models import (
    FixInstructionRequest,
    FixInstructionResponse,
    Message,
    Review,
    ReviewCreate,
    ReviewCreated,
    ReviewSummary,
)
from dursor_api.services.review_service import ReviewService

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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
    from_line: int = 0,
    review_service: ReviewService = Depends(get_review_service),
) -> dict[str, object]:
    """Get review execution logs."""
    try:
        return await review_service.get_logs(review_id, from_line)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/reviews/{review_id}/to-message", response_model=Message)
async def add_review_to_conversation(
    review_id: str,
    review_service: ReviewService = Depends(get_review_service),
) -> Message:
    """Add completed review as a conversation message."""
    try:
        return await review_service.add_review_to_conversation(review_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
