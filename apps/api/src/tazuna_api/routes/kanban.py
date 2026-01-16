"""Kanban board API routes."""

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_kanban_service
from dursor_api.domain.models import PR, KanbanBoard, Task
from dursor_api.services.kanban_service import KanbanService

router = APIRouter(prefix="/kanban", tags=["kanban"])


@router.get("", response_model=KanbanBoard)
async def get_kanban_board(
    repo_id: str | None = None,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> KanbanBoard:
    """Get kanban board with all columns."""
    return await kanban_service.get_board(repo_id)


@router.post("/tasks/{task_id}/move-to-todo", response_model=Task)
async def move_to_todo(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Move task from Backlog to ToDo (manual transition)."""
    try:
        return await kanban_service.move_to_todo(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/move-to-backlog", response_model=Task)
async def move_to_backlog(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Move task back to Backlog (manual transition)."""
    try:
        return await kanban_service.move_to_backlog(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/archive", response_model=Task)
async def archive_task(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Archive a task (manual transition)."""
    try:
        return await kanban_service.archive_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/unarchive", response_model=Task)
async def unarchive_task(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Unarchive a task (restore to backlog)."""
    try:
        return await kanban_service.unarchive_task(task_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/tasks/{task_id}/prs/{pr_id}/sync-status", response_model=PR)
async def sync_pr_status(
    task_id: str,
    pr_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> PR:
    """Sync PR status from GitHub (check if merged/closed)."""
    try:
        return await kanban_service.sync_pr_status(task_id, pr_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
