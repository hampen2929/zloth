"""Kanban board API routes."""

from fastapi import APIRouter, Depends

from zloth_api.dependencies import get_kanban_service
from zloth_api.domain.models import KanbanBoard, PR, RepoSummary, Task
from zloth_api.errors import ZlothError
from zloth_api.services.kanban_service import KanbanService

router = APIRouter(prefix="/kanban", tags=["kanban"])


@router.get("", response_model=KanbanBoard)
async def get_kanban_board(
    repo_id: str | None = None,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> KanbanBoard:
    """Get kanban board with all columns."""
    return await kanban_service.get_board(repo_id)


@router.get("/repos", response_model=list[RepoSummary])
async def get_repo_summaries(
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> list[RepoSummary]:
    """Get all repositories with task count summaries.

    Returns a list of repositories with task counts by computed kanban status,
    sorted by latest activity (most recent first).
    """
    return await kanban_service.get_repo_summaries()


@router.post("/tasks/{task_id}/move-to-todo", response_model=Task)
async def move_to_todo(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Move task from Backlog to ToDo (manual transition)."""
    try:
        return await kanban_service.move_to_todo(task_id)
    except ZlothError:
        raise


@router.post("/tasks/{task_id}/move-to-backlog", response_model=Task)
async def move_to_backlog(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Move task back to Backlog (manual transition)."""
    try:
        return await kanban_service.move_to_backlog(task_id)
    except ZlothError:
        raise


@router.post("/tasks/{task_id}/archive", response_model=Task)
async def archive_task(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Archive a task (manual transition)."""
    try:
        return await kanban_service.archive_task(task_id)
    except ZlothError:
        raise


@router.post("/tasks/{task_id}/unarchive", response_model=Task)
async def unarchive_task(
    task_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> Task:
    """Unarchive a task (restore to backlog)."""
    try:
        return await kanban_service.unarchive_task(task_id)
    except ZlothError:
        raise


@router.post("/tasks/{task_id}/prs/{pr_id}/sync-status", response_model=PR)
async def sync_pr_status(
    task_id: str,
    pr_id: str,
    kanban_service: KanbanService = Depends(get_kanban_service),
) -> PR:
    """Sync PR status from GitHub (check if merged/closed)."""
    try:
        return await kanban_service.sync_pr_status(task_id, pr_id)
    except ZlothError:
        raise
