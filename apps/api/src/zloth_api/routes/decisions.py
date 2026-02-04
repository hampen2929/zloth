"""Decision visibility API routes (P0).

Endpoints for recording and retrieving decision records.
"""

from __future__ import annotations

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from zloth_api.dependencies import get_decision_service
from zloth_api.domain.enums import DecisionType
from zloth_api.domain.models import Decision, DecisionCreate, OutcomeUpdate
from zloth_api.errors import NotFoundError, ValidationError
from zloth_api.services.decision_service import DecisionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["decisions"])


@router.post("/tasks/{task_id}/decisions", response_model=Decision)
async def create_decision(
    task_id: str,
    data: DecisionCreate,
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
) -> Decision:
    """Create a decision record.

    Creates a decision record for run selection, PR promotion, or merge.
    Evidence is automatically collected based on the decision type.

    Args:
        task_id: Task ID.
        data: Decision creation data.
        decision_service: Injected decision service.

    Returns:
        Created decision record.
    """
    try:
        return await decision_service.create_from_request(task_id, data)
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to create decision: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create decision: {e}",
        )


@router.get("/tasks/{task_id}/decisions", response_model=list[Decision])
async def list_decisions(
    task_id: str,
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
    decision_type: DecisionType | None = None,
) -> list[Decision]:
    """List decisions for a task.

    Returns all decisions for the task, optionally filtered by type.

    Args:
        task_id: Task ID.
        decision_service: Injected decision service.
        decision_type: Optional filter by decision type.

    Returns:
        List of decisions ordered by created_at.
    """
    try:
        decisions = await decision_service.list(task_id)
        if decision_type:
            decisions = [d for d in decisions if d.decision_type == decision_type]
        return decisions
    except Exception as e:
        logger.exception(f"Failed to list decisions: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list decisions: {e}",
        )


@router.get("/decisions/{decision_id}", response_model=Decision)
async def get_decision(
    decision_id: str,
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
) -> Decision:
    """Get a decision by ID.

    Args:
        decision_id: Decision ID.
        decision_service: Injected decision service.

    Returns:
        Decision record.
    """
    try:
        decision = await decision_service.get(decision_id)
        if not decision:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Decision not found: {decision_id}",
            )
        return decision
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Failed to get decision: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get decision: {e}",
        )


@router.patch("/decisions/{decision_id}/outcome", response_model=Decision)
async def update_decision_outcome(
    decision_id: str,
    data: OutcomeUpdate,
    decision_service: Annotated[DecisionService, Depends(get_decision_service)],
) -> Decision:
    """Update the outcome of a decision.

    Used to record whether a past decision was good or bad,
    enabling learning and improvement over time.

    Args:
        decision_id: Decision ID.
        data: Outcome update data.
        decision_service: Injected decision service.

    Returns:
        Updated decision record.
    """
    try:
        return await decision_service.update_outcome(
            decision_id=decision_id,
            outcome=data.outcome,
            reason=data.reason,
            refs=data.refs,
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        logger.exception(f"Failed to update decision outcome: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update decision outcome: {e}",
        )
