"""Task routes."""

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import get_message_dao, get_pr_dao, get_run_dao, get_task_dao
from dursor_api.domain.models import (
    Message,
    MessageCreate,
    PRSummary,
    RunSummary,
    Task,
    TaskBulkCreate,
    TaskBulkCreated,
    TaskCreate,
    TaskDetail,
)
from dursor_api.storage.dao import PRDAO, MessageDAO, RunDAO, TaskDAO

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=Task, status_code=201)
async def create_task(
    data: TaskCreate,
    task_dao: TaskDAO = Depends(get_task_dao),
) -> Task:
    """Create a new task."""
    return await task_dao.create(repo_id=data.repo_id, title=data.title)


@router.get("", response_model=list[Task])
async def list_tasks(
    repo_id: str | None = None,
    task_dao: TaskDAO = Depends(get_task_dao),
) -> list[Task]:
    """List tasks, optionally filtered by repo."""
    return await task_dao.list(repo_id=repo_id)


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    task_dao: TaskDAO = Depends(get_task_dao),
    message_dao: MessageDAO = Depends(get_message_dao),
    run_dao: RunDAO = Depends(get_run_dao),
    pr_dao: PRDAO = Depends(get_pr_dao),
) -> TaskDetail:
    """Get a task with details."""
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    messages = await message_dao.list(task_id)
    runs = await run_dao.list(task_id)
    prs = await pr_dao.list(task_id)

    run_summaries = [
        RunSummary(
            id=r.id,
            message_id=r.message_id,
            model_id=r.model_id,
            model_name=r.model_name,
            provider=r.provider,
            executor_type=r.executor_type,
            working_branch=r.working_branch,
            status=r.status,
            created_at=r.created_at,
        )
        for r in runs
    ]

    pr_summaries = [
        PRSummary(
            id=p.id,
            number=p.number,
            url=p.url,
            branch=p.branch,
            status=p.status,
        )
        for p in prs
    ]

    return TaskDetail(
        id=task.id,
        repo_id=task.repo_id,
        title=task.title,
        created_at=task.created_at,
        updated_at=task.updated_at,
        messages=messages,
        runs=run_summaries,
        prs=pr_summaries,
    )


@router.post("/{task_id}/messages", response_model=Message, status_code=201)
async def add_message(
    task_id: str,
    data: MessageCreate,
    task_dao: TaskDAO = Depends(get_task_dao),
    message_dao: MessageDAO = Depends(get_message_dao),
) -> Message:
    """Add a message to a task."""
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    message = await message_dao.create(
        task_id=task_id,
        role=data.role,
        content=data.content,
    )

    await task_dao.update_timestamp(task_id)
    return message


@router.get("/{task_id}/messages", response_model=list[Message])
async def list_messages(
    task_id: str,
    task_dao: TaskDAO = Depends(get_task_dao),
    message_dao: MessageDAO = Depends(get_message_dao),
) -> list[Message]:
    """List messages for a task."""
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    return await message_dao.list(task_id)


@router.post("/bulk", response_model=TaskBulkCreated, status_code=201)
async def bulk_create_tasks(
    data: TaskBulkCreate,
    task_dao: TaskDAO = Depends(get_task_dao),
) -> TaskBulkCreated:
    """Bulk create multiple tasks.

    This endpoint is typically used after task breakdown to register
    multiple decomposed tasks at once.

    Args:
        data: Bulk create request with repo_id and list of tasks.
        task_dao: Task data access object.

    Returns:
        TaskBulkCreated with created tasks and count.
    """
    created_tasks: list[Task] = []

    for task_create in data.tasks:
        task = await task_dao.create(
            repo_id=data.repo_id,
            title=task_create.title,
        )
        created_tasks.append(task)

    return TaskBulkCreated(
        created_tasks=created_tasks,
        count=len(created_tasks),
    )
