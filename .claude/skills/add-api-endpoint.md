# Skill: Add New API Endpoint

## Description
Guide for adding a new API endpoint to the dursor backend.

## Steps

### 1. Create Route File (if new resource)
- Location: `apps/api/src/dursor_api/routes/{resource_name}.py`
- Follow existing patterns in `routes/models.py` or `routes/tasks.py`

### 2. Create Service (if needed)
- Location: `apps/api/src/dursor_api/services/{resource_name}_service.py`
- Implement business logic separate from routes

### 3. Add Domain Models (if needed)
- Add Pydantic models in `apps/api/src/dursor_api/domain/models.py`
- Add enums in `apps/api/src/dursor_api/domain/enums.py`

### 4. Add DAO Methods (if needed)
- Location: `apps/api/src/dursor_api/storage/dao.py`
- Update schema in `apps/api/src/dursor_api/storage/schema.sql`

### 5. Register Router
- Add router import and registration in `apps/api/src/dursor_api/main.py`

### 6. Verify
```bash
cd apps/api
uv run ruff check src/
uv run ruff format src/
uv run mypy src/
uv run pytest
```

## Template

```python
from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_dao
from dursor_api.domain.models import YourModel
from dursor_api.storage.dao import DAO

router = APIRouter(prefix="/v1/your-resource", tags=["your-resource"])

@router.get("/")
async def list_items(dao: DAO = Depends(get_dao)) -> list[YourModel]:
    return await dao.list_items()

@router.post("/")
async def create_item(item: YourModel, dao: DAO = Depends(get_dao)) -> YourModel:
    return await dao.create_item(item)

@router.get("/{item_id}")
async def get_item(item_id: str, dao: DAO = Depends(get_dao)) -> YourModel:
    item = await dao.get_item(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item
```
