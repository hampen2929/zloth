"""Backlog routes for managing backlog items."""

from fastapi import APIRouter, Depends, HTTPException

from tazuna_api.dependencies import get_backlog_dao, get_task_dao
from tazuna_api.domain.enums import TaskBaseKanbanStatus
from tazuna_api.domain.models import (
    BacklogItem,
    BacklogItemCreate,
    BacklogItemUpdate,
    Task,
)
from tazuna_api.storage.dao import BacklogDAO, TaskDAO

router = APIRouter(prefix="/backlog", tags=["backlog"])


@router.get("", response_model=list[BacklogItem])
async def list_backlog_items(
    repo_id: str | None = None,
    backlog_dao: BacklogDAO = Depends(get_backlog_dao),
) -> list[BacklogItem]:
    """List backlog items with optional filters.

    Args:
        repo_id: Filter by repository ID.
        backlog_dao: Backlog DAO instance.

    Returns:
        List of BacklogItem.
    """
    return await backlog_dao.list(repo_id=repo_id)


@router.post("", response_model=BacklogItem, status_code=201)
async def create_backlog_item(
    request: BacklogItemCreate,
    backlog_dao: BacklogDAO = Depends(get_backlog_dao),
) -> BacklogItem:
    """Create a new backlog item.

    Args:
        request: Backlog item creation request.
        backlog_dao: Backlog DAO instance.

    Returns:
        Created BacklogItem.
    """
    subtasks = [{"title": st.title} for st in request.subtasks] if request.subtasks else None

    return await backlog_dao.create(
        repo_id=request.repo_id,
        title=request.title,
        description=request.description,
        type=request.type,
        estimated_size=request.estimated_size,
        target_files=request.target_files,
        implementation_hint=request.implementation_hint,
        tags=request.tags,
        subtasks=subtasks,
    )


@router.get("/{item_id}", response_model=BacklogItem)
async def get_backlog_item(
    item_id: str,
    backlog_dao: BacklogDAO = Depends(get_backlog_dao),
) -> BacklogItem:
    """Get a backlog item by ID.

    Args:
        item_id: Backlog item ID.
        backlog_dao: Backlog DAO instance.

    Returns:
        BacklogItem.

    Raises:
        HTTPException: If item not found.
    """
    item = await backlog_dao.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    return item


@router.put("/{item_id}", response_model=BacklogItem)
async def update_backlog_item(
    item_id: str,
    request: BacklogItemUpdate,
    backlog_dao: BacklogDAO = Depends(get_backlog_dao),
) -> BacklogItem:
    """Update a backlog item.

    Args:
        item_id: Backlog item ID.
        request: Update request.
        backlog_dao: Backlog DAO instance.

    Returns:
        Updated BacklogItem.

    Raises:
        HTTPException: If item not found.
    """
    # Convert subtasks to dict format if provided
    subtasks = None
    if request.subtasks is not None:
        subtasks = [st.model_dump() for st in request.subtasks]

    item = await backlog_dao.update(
        id=item_id,
        title=request.title,
        description=request.description,
        type=request.type,
        estimated_size=request.estimated_size,
        target_files=request.target_files,
        implementation_hint=request.implementation_hint,
        tags=request.tags,
        subtasks=subtasks,
    )

    if not item:
        raise HTTPException(status_code=404, detail="Backlog item not found")
    return item


@router.delete("/{item_id}", status_code=204)
async def delete_backlog_item(
    item_id: str,
    backlog_dao: BacklogDAO = Depends(get_backlog_dao),
) -> None:
    """Delete a backlog item.

    Args:
        item_id: Backlog item ID.
        backlog_dao: Backlog DAO instance.

    Raises:
        HTTPException: If item not found.
    """
    deleted = await backlog_dao.delete(item_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Backlog item not found")


@router.post("/{item_id}/start", response_model=Task)
async def start_work_on_backlog_item(
    item_id: str,
    backlog_dao: BacklogDAO = Depends(get_backlog_dao),
    task_dao: TaskDAO = Depends(get_task_dao),
) -> Task:
    """Promote a backlog item to a task and move it to ToDo.

    This endpoint:
    1. Creates a new Task from the backlog item
    2. Sets the Task kanban_status to 'todo'
    3. Links the backlog item to the created task

    Args:
        item_id: Backlog item ID.
        backlog_dao: Backlog DAO instance.
        task_dao: Task DAO instance.

    Returns:
        Created Task.

    Raises:
        HTTPException: If item not found or already has a linked task.
    """
    item = await backlog_dao.get(item_id)
    if not item:
        raise HTTPException(status_code=404, detail="Backlog item not found")

    if item.task_id:
        raise HTTPException(
            status_code=400,
            detail="Backlog item already has a linked task",
        )

    # Create task from backlog item
    task = await task_dao.create(
        repo_id=item.repo_id,
        title=item.title,
    )

    # Set task kanban_status to 'todo' (Backlog -> ToDo transition)
    await task_dao.update_kanban_status(task.id, TaskBaseKanbanStatus.TODO)

    # Update backlog item with task reference
    await backlog_dao.update(
        id=item_id,
        task_id=task.id,
    )

    # Fetch updated task with correct kanban_status
    updated_task = await task_dao.get(task.id)
    if not updated_task:
        raise HTTPException(status_code=500, detail="Failed to fetch created task")

    return updated_task
