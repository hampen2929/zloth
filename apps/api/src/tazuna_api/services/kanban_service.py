"""Kanban board service for task status management."""

from tazuna_api.domain.enums import ExecutorType, RunStatus, TaskBaseKanbanStatus, TaskKanbanStatus
from tazuna_api.domain.models import (
    PR,
    ExecutorRunStatus,
    KanbanBoard,
    KanbanColumn,
    Task,
    TaskWithKanbanStatus,
)
from tazuna_api.services.github_service import GitHubService
from tazuna_api.storage.dao import PRDAO, ReviewDAO, RunDAO, TaskDAO, UserPreferencesDAO


class KanbanService:
    """Kanban status management service.

    Status calculation priority:
    1. Archived (highest) - User explicitly archived this task
    2. Done - PR is merged
    3. In Progress - Run is running
    4. Gating - All runs completed + PR is open + CI is pending/null + enable_gating_status
    5. In Review - All runs completed
    6. Base Status (lowest) - DB stored status (backlog/todo)
    """

    def __init__(
        self,
        task_dao: TaskDAO,
        run_dao: RunDAO,
        pr_dao: PRDAO,
        review_dao: ReviewDAO,
        github_service: GitHubService,
        user_preferences_dao: UserPreferencesDAO,
    ):
        self.task_dao = task_dao
        self.run_dao = run_dao
        self.pr_dao = pr_dao
        self.review_dao = review_dao
        self.github_service = github_service
        self.user_preferences_dao = user_preferences_dao

    def _compute_kanban_status(
        self,
        base_status: str,  # DB stored status (backlog/todo/archived)
        run_count: int,
        running_count: int,
        completed_count: int,
        latest_pr_status: str | None,
        latest_ci_status: str | None = None,
        enable_gating_status: bool = False,
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

        # 4. All runs completed
        if run_count > 0 and completed_count == run_count:
            # 4a. Gating: All runs completed + PR is open + CI is pending/null + enabled
            if enable_gating_status and latest_pr_status == "open":
                if latest_ci_status in ("pending", None):
                    return TaskKanbanStatus.GATING
            # 4b. InReview: All runs completed
            return TaskKanbanStatus.IN_REVIEW

        # 5. Use base status (backlog/todo)
        # Runs that are queued also fall here (not started yet)
        return TaskKanbanStatus(base_status)

    async def get_board(self, repo_id: str | None = None) -> KanbanBoard:
        """Get full kanban board."""
        tasks_with_aggregates = await self.task_dao.list_with_aggregates(repo_id)

        # Fetch user preferences for gating status
        user_prefs = await self.user_preferences_dao.get()
        enable_gating_status = user_prefs.enable_gating_status if user_prefs else False

        # Get task IDs for fetching executor-level run data
        task_ids = [task_data["id"] for task_data in tasks_with_aggregates]

        # Fetch latest runs per executor for all tasks
        executor_runs = await self.run_dao.get_latest_runs_by_executor_for_tasks(task_ids)

        # Collect all run IDs to check for reviews
        all_run_ids: list[str] = []
        for task_executor_data in executor_runs.values():
            for run_data in task_executor_data.values():
                all_run_ids.append(run_data["run_id"])

        # Get reviewed run IDs
        reviewed_run_ids = await self.review_dao.get_reviewed_run_ids(all_run_ids)

        # CLI executor types to display (excluding patch_agent)
        cli_executor_types = [
            ExecutorType.CLAUDE_CODE,
            ExecutorType.CODEX_CLI,
            ExecutorType.GEMINI_CLI,
        ]

        # Note: We do NOT automatically refresh CI status here because it would
        # cause unrelated tasks to unexpectedly transition to Gating status.
        # CI status should only be refreshed explicitly when viewing a specific task.

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
                latest_ci_status=task_data.get("latest_ci_status"),
                enable_gating_status=enable_gating_status,
            )

            # Build executor statuses for this task
            task_executor_runs = executor_runs.get(task_data["id"], {})
            executor_statuses: list[ExecutorRunStatus] = []
            for exec_type in cli_executor_types:
                run_info = task_executor_runs.get(exec_type.value)
                if run_info:
                    executor_statuses.append(
                        ExecutorRunStatus(
                            executor_type=exec_type,
                            run_id=run_info["run_id"],
                            status=RunStatus(run_info["status"]),
                            has_review=run_info["run_id"] in reviewed_run_ids,
                        )
                    )
                else:
                    executor_statuses.append(
                        ExecutorRunStatus(
                            executor_type=exec_type,
                            run_id=None,
                            status=None,
                            has_review=False,
                        )
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
                latest_ci_status=task_data.get("latest_ci_status"),
                executor_statuses=executor_statuses,
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
