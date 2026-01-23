"""Comparison routes."""

from fastapi import APIRouter, Depends, HTTPException

from zloth_api.dependencies import get_model_service
from zloth_api.domain.models import Comparison, ComparisonCreate, ComparisonCreated
from zloth_api.services.comparison_service import ComparisonService
from zloth_api.storage.dao import ComparisonDAO, RunDAO, TaskDAO
from zloth_api.storage.db import get_db

router = APIRouter(tags=["comparisons"])


async def get_comparison_service() -> ComparisonService:
    db = await get_db()
    comparison_dao = ComparisonDAO(db)
    run_dao = RunDAO(db)
    task_dao = TaskDAO(db)
    model_service = await get_model_service()
    return ComparisonService(comparison_dao, run_dao, task_dao, model_service)


@router.post("/tasks/{task_id}/comparisons", response_model=ComparisonCreated, status_code=201)
async def create_comparison(
    task_id: str,
    data: ComparisonCreate,
    service: ComparisonService = Depends(get_comparison_service),
) -> ComparisonCreated:
    try:
        return await service.create(task_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks/{task_id}/comparisons", response_model=list[Comparison])
async def list_comparisons(
    task_id: str,
    service: ComparisonService = Depends(get_comparison_service),
) -> list[Comparison]:
    return await service.list_by_task(task_id)


@router.get("/comparisons/{comparison_id}", response_model=Comparison)
async def get_comparison(
    comparison_id: str,
    service: ComparisonService = Depends(get_comparison_service),
) -> Comparison:
    result = await service.get(comparison_id)
    if not result:
        raise HTTPException(status_code=404, detail="Comparison not found")
    return result

