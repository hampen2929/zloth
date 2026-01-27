"""Model profile routes."""

from fastapi import APIRouter, Depends, HTTPException

from zloth_api.dependencies import get_idempotency_service, get_model_service
from zloth_api.domain.models import ModelProfile, ModelProfileCreate
from zloth_api.services.idempotency import (
    IdempotencyOperation,
    IdempotencyService,
    generate_idempotency_key,
)
from zloth_api.services.model_service import ModelService

router = APIRouter(prefix="/models", tags=["models"])


@router.get("", response_model=list[ModelProfile])
async def list_models(
    model_service: ModelService = Depends(get_model_service),
) -> list[ModelProfile]:
    """List all model profiles."""
    return await model_service.list()


@router.post("", response_model=ModelProfile, status_code=201)
async def create_model(
    data: ModelProfileCreate,
    model_service: ModelService = Depends(get_model_service),
    idempotency_service: IdempotencyService = Depends(get_idempotency_service),
) -> ModelProfile:
    """Create a new model profile.

    Supports idempotency via `idempotency_key` in request body.
    If the same key is used, returns 409 Conflict.
    """
    # Generate idempotency key
    idempotency_key = generate_idempotency_key(
        IdempotencyOperation.MODEL_CREATE,
        content={
            "provider": data.provider.value,
            "model_name": data.model_name,
        },
        client_key=data.idempotency_key,
    )

    # Check for duplicate request
    await idempotency_service.check_and_raise(idempotency_key, "model creation")

    model = await model_service.create(data)

    # Store idempotency key
    await idempotency_service.store(
        key=idempotency_key,
        operation=IdempotencyOperation.MODEL_CREATE,
        resource_id=model.id,
    )

    return model


@router.get("/{model_id}", response_model=ModelProfile)
async def get_model(
    model_id: str,
    model_service: ModelService = Depends(get_model_service),
) -> ModelProfile:
    """Get a model profile by ID."""
    model = await model_service.get(model_id)
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.delete("/{model_id}", status_code=204)
async def delete_model(
    model_id: str,
    model_service: ModelService = Depends(get_model_service),
) -> None:
    """Delete a model profile."""
    try:
        deleted = await model_service.delete(model_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Model not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
