"""Task routes."""

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException

from dursor_api.dependencies import (
    get_ci_check_dao,
    get_message_dao,
    get_pr_dao,
    get_run_dao,
    get_task_dao,
)
from dursor_api.domain.enums import CodingMode, TaskBaseKanbanStatus, TaskKanbanStatus
from dursor_api.domain.models import (
    AgenticStartRequest,
    AgenticStartResponse,
    AgenticStatusResponse,
    CICheckSummary,
    Message,
    MessageCreate,
    PRSummary,
    RejectMergeRequest,
    RunSummary,
    Task,
    TaskBulkCreate,
    TaskBulkCreated,
    TaskCreate,
    TaskDetail,
)
from dursor_api.storage.dao import PRDAO, CICheckDAO, MessageDAO, RunDAO, TaskDAO


def _compute_kanban_status(
    base_status: str,
    run_count: int,
    running_count: int,
    completed_count: int,
    latest_pr_status: str | None,
) -> TaskKanbanStatus:
    """Compute final kanban status.

    Dynamic computation overrides base status, except for archived.
    This logic mirrors KanbanService._compute_kanban_status.
    """
    # 1. Archived status takes priority - user explicitly archived this task
    if base_status == TaskBaseKanbanStatus.ARCHIVED.value:
        return TaskKanbanStatus.ARCHIVED

    # 2. PR is merged -> Done (highest priority for active tasks)
    if latest_pr_status == "merged":
        return TaskKanbanStatus.DONE

    # 3. Run is running -> InProgress
    if running_count > 0:
        return TaskKanbanStatus.IN_PROGRESS

    # 4. Runs exist and all completed -> InReview
    if run_count > 0 and completed_count == run_count:
        return TaskKanbanStatus.IN_REVIEW

    # 5. Use base status (backlog/todo)
    return TaskKanbanStatus(base_status)


if TYPE_CHECKING:
    from dursor_api.services.agentic_orchestrator import AgenticOrchestrator

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.post("", response_model=Task, status_code=201)
async def create_task(
    data: TaskCreate,
    task_dao: TaskDAO = Depends(get_task_dao),
) -> Task:
    """Create a new task."""
    return await task_dao.create(
        repo_id=data.repo_id,
        title=data.title,
        coding_mode=data.coding_mode,
    )


@router.get("", response_model=list[Task])
async def list_tasks(
    repo_id: str | None = None,
    task_dao: TaskDAO = Depends(get_task_dao),
) -> list[Task]:
    """List tasks, optionally filtered by repo.

    Returns tasks with computed kanban_status based on run/PR state:
    - in_progress: if any run is currently running
    - in_review: if all runs are completed
    - done: if PR is merged
    - backlog/todo/archived: base status from DB
    """
    tasks_with_aggregates = await task_dao.list_with_aggregates(repo_id=repo_id)

    result: list[Task] = []
    for task_data in tasks_with_aggregates:
        computed_status = _compute_kanban_status(
            base_status=task_data["kanban_status"],
            run_count=task_data["run_count"],
            running_count=task_data["running_count"],
            completed_count=task_data["completed_count"],
            latest_pr_status=task_data["latest_pr_status"],
        )

        result.append(
            Task(
                id=task_data["id"],
                repo_id=task_data["repo_id"],
                title=task_data["title"],
                coding_mode=task_data["coding_mode"],
                kanban_status=computed_status.value,
                created_at=task_data["created_at"],
                updated_at=task_data["updated_at"],
            )
        )

    return result


@router.get("/{task_id}", response_model=TaskDetail)
async def get_task(
    task_id: str,
    task_dao: TaskDAO = Depends(get_task_dao),
    message_dao: MessageDAO = Depends(get_message_dao),
    run_dao: RunDAO = Depends(get_run_dao),
    pr_dao: PRDAO = Depends(get_pr_dao),
    ci_check_dao: CICheckDAO = Depends(get_ci_check_dao),
) -> TaskDetail:
    """Get a task with details."""
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    messages = await message_dao.list(task_id)
    runs = await run_dao.list(task_id)
    prs = await pr_dao.list(task_id)
    ci_checks = await ci_check_dao.list_by_task_id(task_id)

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

    ci_check_summaries = [
        CICheckSummary(
            id=c.id,
            pr_id=c.pr_id,
            status=c.status,
            created_at=c.created_at,
            updated_at=c.updated_at,
        )
        for c in ci_checks
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
        ci_checks=ci_check_summaries,
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
            coding_mode=task_create.coding_mode,
        )
        created_tasks.append(task)

    return TaskBulkCreated(
        created_tasks=created_tasks,
        count=len(created_tasks),
    )


# ============================================================
# Agentic Execution Endpoints
# ============================================================


async def get_agentic_orchestrator() -> "AgenticOrchestrator":
    """Get agentic orchestrator dependency.

    Returns:
        AgenticOrchestrator instance.
    """
    from dursor_api.dependencies import get_agentic_orchestrator

    return await get_agentic_orchestrator()


@router.post("/{task_id}/agentic", response_model=AgenticStartResponse, status_code=201)
async def start_agentic_execution(
    task_id: str,
    data: AgenticStartRequest,
    task_dao: TaskDAO = Depends(get_task_dao),
    orchestrator: "AgenticOrchestrator" = Depends(get_agentic_orchestrator),
) -> AgenticStartResponse:
    """Start agentic execution for a task.

    This endpoint starts the autonomous development cycle:
    1. Coding (Claude Code)
    2. Wait for CI
    3. If CI fails → Auto-fix and retry
    4. Review (Codex)
    5. If review rejects → Fix and retry
    6. Merge (Full Auto) or wait for human (Semi Auto)

    Args:
        task_id: Target task ID.
        data: Agentic start request with instruction and mode.
        task_dao: Task DAO.
        orchestrator: Agentic orchestrator service.

    Returns:
        AgenticStartResponse with run ID and status.

    Raises:
        HTTPException: If task not found or mode is invalid.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Validate mode
    if data.mode == CodingMode.INTERACTIVE:
        raise HTTPException(
            status_code=400,
            detail="Interactive mode is not supported by agentic execution",
        )

    try:
        state = await orchestrator.start_task(
            task_id=task_id,
            instruction=data.instruction,
            mode=data.mode,
            config=data.config,
        )

        return AgenticStartResponse(
            agentic_run_id=state.id,
            status="started",
            mode=state.mode,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{task_id}/agentic/status", response_model=AgenticStatusResponse)
async def get_agentic_status(
    task_id: str,
    task_dao: TaskDAO = Depends(get_task_dao),
    orchestrator: "AgenticOrchestrator" = Depends(get_agentic_orchestrator),
) -> AgenticStatusResponse:
    """Get agentic execution status for a task.

    Args:
        task_id: Target task ID.
        task_dao: Task DAO.
        orchestrator: Agentic orchestrator service.

    Returns:
        AgenticStatusResponse with current status.

    Raises:
        HTTPException: If task or agentic run not found.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    state = await orchestrator.get_status(task_id)
    if not state:
        raise HTTPException(status_code=404, detail="No agentic execution found for this task")

    return AgenticStatusResponse(
        agentic_run_id=state.id,
        task_id=state.task_id,
        mode=state.mode,
        phase=state.phase,
        iteration=state.iteration,
        ci_iterations=state.ci_iterations,
        review_iterations=state.review_iterations,
        pr_number=state.pr_number,
        last_review_score=state.last_review_score,
        human_approved=state.human_approved,
        error=state.error,
        started_at=state.started_at,
        last_activity=state.last_activity,
    )


@router.post("/{task_id}/agentic/cancel")
async def cancel_agentic_execution(
    task_id: str,
    task_dao: TaskDAO = Depends(get_task_dao),
    orchestrator: "AgenticOrchestrator" = Depends(get_agentic_orchestrator),
) -> dict[str, bool]:
    """Cancel agentic execution for a task.

    Args:
        task_id: Target task ID.
        task_dao: Task DAO.
        orchestrator: Agentic orchestrator service.

    Returns:
        Dict with cancelled status.

    Raises:
        HTTPException: If task not found.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    cancelled = await orchestrator.cancel(task_id)
    return {"cancelled": cancelled}


@router.post("/{task_id}/approve-merge")
async def approve_merge(
    task_id: str,
    task_dao: TaskDAO = Depends(get_task_dao),
    orchestrator: "AgenticOrchestrator" = Depends(get_agentic_orchestrator),
) -> dict[str, str]:
    """Human approves merge for Semi Auto mode.

    Transitions from AWAITING_HUMAN to MERGE_CHECK phase.

    Args:
        task_id: Target task ID.
        task_dao: Task DAO.
        orchestrator: Agentic orchestrator service.

    Returns:
        Dict with status and phase.

    Raises:
        HTTPException: If task not found or not in correct phase.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        state = await orchestrator.approve_merge(task_id)
        return {
            "status": "merging",
            "phase": state.phase.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/{task_id}/reject-merge")
async def reject_merge(
    task_id: str,
    data: RejectMergeRequest,
    task_dao: TaskDAO = Depends(get_task_dao),
    orchestrator: "AgenticOrchestrator" = Depends(get_agentic_orchestrator),
) -> dict[str, str]:
    """Human rejects merge for Semi Auto mode.

    If feedback is provided, transitions to CODING phase to address it.
    Otherwise, transitions to FAILED phase.

    Args:
        task_id: Target task ID.
        data: Reject request with optional feedback.
        task_dao: Task DAO.
        orchestrator: Agentic orchestrator service.

    Returns:
        Dict with status and phase.

    Raises:
        HTTPException: If task not found or not in correct phase.
    """
    # Verify task exists
    task = await task_dao.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    try:
        state = await orchestrator.reject_merge(task_id, data.feedback)
        return {
            "status": "rejected",
            "phase": state.phase.value,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
