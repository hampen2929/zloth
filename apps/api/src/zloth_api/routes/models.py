"""Model profile routes."""

from fastapi import APIRouter, Depends, HTTPException

from zloth_api.dependencies import get_model_service
from zloth_api.domain.models import ModelProfile, ModelProfileCreate
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
) -> ModelProfile:
    """Create a new model profile."""
    return await model_service.create(data)


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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
