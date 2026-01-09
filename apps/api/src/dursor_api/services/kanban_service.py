"""Kanban board service for task status management."""

from dursor_api.domain.enums import TaskBaseKanbanStatus, TaskKanbanStatus
from dursor_api.domain.models import (
    PR,
    KanbanBoard,
    KanbanColumn,
    Task,
    TaskWithKanbanStatus,
)
from dursor_api.services.github_service import GitHubService
from dursor_api.storage.dao import PRDAO, RunDAO, TaskDAO


class KanbanService:
    """Kanban status management service.

    Status calculation priority:
    1. PR is merged -> Done (highest priority)
    2. Run is running -> InProgress
    3. All runs completed -> InReview
    4. DB stored base status (backlog/todo/archived)
    """

    def __init__(
        self,
        task_dao: TaskDAO,
        run_dao: RunDAO,
        pr_dao: PRDAO,
        github_service: GitHubService,
    ):
        self.task_dao = task_dao
        self.run_dao = run_dao
        self.pr_dao = pr_dao
        self.github_service = github_service

    def _compute_kanban_status(
        self,
        base_status: str,  # DB stored status (backlog/todo/archived)
        run_count: int,
        running_count: int,
        completed_count: int,
        latest_pr_status: str | None,
    ) -> TaskKanbanStatus:
        """Compute final kanban status.

        Dynamic computation overrides base status, except for archived.
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
        # Runs that are queued also fall here (not started yet)
        return TaskKanbanStatus(base_status)

    async def get_board(self, repo_id: str | None = None) -> KanbanBoard:
        """Get full kanban board."""
        tasks_with_aggregates = await self.task_dao.list_with_aggregates(repo_id)

        # Group tasks by computed status
        columns: dict[TaskKanbanStatus, list[TaskWithKanbanStatus]] = {
            status: [] for status in TaskKanbanStatus
        }

        for task_data in tasks_with_aggregates:
            computed_status = self._compute_kanban_status(
                base_status=task_data["kanban_status"],
                run_count=task_data["run_count"],
                running_count=task_data["running_count"],
                completed_count=task_data["completed_count"],
                latest_pr_status=task_data["latest_pr_status"],
            )

            task_with_status = TaskWithKanbanStatus(
                id=task_data["id"],
                repo_id=task_data["repo_id"],
                title=task_data["title"],
                kanban_status=task_data["kanban_status"],
                created_at=task_data["created_at"],
                updated_at=task_data["updated_at"],
                computed_status=computed_status,
                run_count=task_data["run_count"],
                running_count=task_data["running_count"],
                completed_count=task_data["completed_count"],
                pr_count=task_data["pr_count"],
                latest_pr_status=task_data["latest_pr_status"],
            )
            columns[computed_status].append(task_with_status)

        return KanbanBoard(
            columns=[
                KanbanColumn(status=status, tasks=tasks, count=len(tasks))
                for status, tasks in columns.items()
            ],
            total_tasks=sum(len(tasks) for tasks in columns.values()),
        )

    async def move_to_todo(self, task_id: str) -> Task:
        """Move task from Backlog to ToDo (manual transition)."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Only allow moving from backlog
        if task.kanban_status != "backlog":
            raise ValueError(f"Can only move from backlog to todo, current: {task.kanban_status}")

        await self.task_dao.update_kanban_status(task_id, TaskBaseKanbanStatus.TODO)
        updated_task = await self.task_dao.get(task_id)
        if not updated_task:
            raise ValueError(f"Task not found after update: {task_id}")
        return updated_task

    async def move_to_backlog(self, task_id: str) -> Task:
        """Move task back to Backlog (manual transition)."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        # Only allow moving from todo or archived
        if task.kanban_status not in ("todo", "archived"):
            raise ValueError(
                f"Can only move to backlog from todo/archived, current: {task.kanban_status}"
            )

        await self.task_dao.update_kanban_status(task_id, TaskBaseKanbanStatus.BACKLOG)
        updated_task = await self.task_dao.get(task_id)
        if not updated_task:
            raise ValueError(f"Task not found after update: {task_id}")
        return updated_task

    async def archive_task(self, task_id: str) -> Task:
        """Archive a task (manual transition)."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        await self.task_dao.update_kanban_status(task_id, TaskBaseKanbanStatus.ARCHIVED)
        updated_task = await self.task_dao.get(task_id)
        if not updated_task:
            raise ValueError(f"Task not found after update: {task_id}")
        return updated_task

    async def unarchive_task(self, task_id: str) -> Task:
        """Unarchive a task (restore to backlog)."""
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        if task.kanban_status != "archived":
            raise ValueError(
                f"Can only unarchive from archived status, current: {task.kanban_status}"
            )

        await self.task_dao.update_kanban_status(task_id, TaskBaseKanbanStatus.BACKLOG)
        updated_task = await self.task_dao.get(task_id)
        if not updated_task:
            raise ValueError(f"Task not found after update: {task_id}")
        return updated_task

    async def sync_pr_status(self, task_id: str, pr_id: str) -> PR:
        """Sync PR status from GitHub.

        Fetches the current PR state from GitHub and updates the local DB.
        """
        pr = await self.pr_dao.get(pr_id)
        if not pr:
            raise ValueError(f"PR not found: {pr_id}")

        if pr.task_id != task_id:
            raise ValueError(f"PR {pr_id} does not belong to task {task_id}")

        # Parse owner/repo from PR URL
        # URL format: https://github.com/{owner}/{repo}/pull/{number}
        url_parts = pr.url.split("/")
        if len(url_parts) < 5:
            raise ValueError(f"Invalid PR URL format: {pr.url}")

        owner = url_parts[-4]
        repo = url_parts[-3]

        # Get PR status from GitHub
        pr_data = await self.github_service.get_pull_request_status(owner, repo, pr.number)

        # Determine status
        new_status: str
        if pr_data.get("merged"):
            new_status = "merged"
        elif pr_data.get("state") == "closed":
            new_status = "closed"
        else:
            new_status = "open"

        # Update local PR status
        await self.pr_dao.update_status(pr_id, new_status)

        updated_pr = await self.pr_dao.get(pr_id)
        if not updated_pr:
            raise ValueError(f"PR not found after update: {pr_id}")
        return updated_pr
