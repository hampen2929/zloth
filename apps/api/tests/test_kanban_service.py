"""Tests for Kanban status computation and minimal integration.

These tests validate the kanban status rules implemented in
`zloth_api.routes.tasks._compute_kanban_status` and exercise
`TaskDAO.list_with_aggregates` together with `KanbanService.get_board`.
"""

from __future__ import annotations

import pytest

from zloth_api.domain.enums import (
    RunStatus,
    TaskBaseKanbanStatus,
    TaskKanbanStatus,
)
from zloth_api.routes.tasks import _compute_kanban_status
from zloth_api.services.github_service import GitHubService
from zloth_api.services.kanban_service import KanbanService
from zloth_api.storage.dao import (
    PRDAO,
    RepoDAO,
    RunDAO,
    TaskDAO,
    UserPreferencesDAO,
    CICheckDAO,
    ReviewDAO,
)
from zloth_api.storage.db import Database


class TestComputeKanbanStatus:
    """Unit tests for the status computation helper."""

    def test_archived_overrides_all(self) -> None:
        status = _compute_kanban_status(
            base_status=TaskBaseKanbanStatus.ARCHIVED.value,
            run_count=3,
            running_count=1,
            completed_count=2,
            latest_pr_status="open",
            latest_ci_status="pending",
            enable_gating_status=True,
        )
        assert status == TaskKanbanStatus.ARCHIVED

    def test_done_when_pr_merged(self) -> None:
        status = _compute_kanban_status(
            base_status=TaskBaseKanbanStatus.BACKLOG.value,
            run_count=0,
            running_count=0,
            completed_count=0,
            latest_pr_status="merged",
        )
        assert status == TaskKanbanStatus.DONE

    def test_in_progress_when_any_run_running(self) -> None:
        status = _compute_kanban_status(
            base_status=TaskBaseKanbanStatus.TODO.value,
            run_count=2,
            running_count=1,
            completed_count=0,
            latest_pr_status=None,
        )
        assert status == TaskKanbanStatus.IN_PROGRESS

    def test_in_review_when_all_runs_completed(self) -> None:
        status = _compute_kanban_status(
            base_status=TaskBaseKanbanStatus.TODO.value,
            run_count=2,
            running_count=0,
            completed_count=2,
            latest_pr_status=None,
            enable_gating_status=False,
        )
        assert status == TaskKanbanStatus.IN_REVIEW

    def test_gating_when_enabled_and_pr_open_and_ci_pending(self) -> None:
        status = _compute_kanban_status(
            base_status=TaskBaseKanbanStatus.TODO.value,
            run_count=1,
            running_count=0,
            completed_count=1,
            latest_pr_status="open",
            latest_ci_status="pending",
            enable_gating_status=True,
        )
        assert status == TaskKanbanStatus.GATING

    def test_base_status_when_no_dynamic_signals(self) -> None:
        status = _compute_kanban_status(
            base_status=TaskBaseKanbanStatus.TODO.value,
            run_count=0,
            running_count=0,
            completed_count=0,
            latest_pr_status=None,
        )
        assert status == TaskKanbanStatus.TODO


class TestKanbanBoardIntegration:
    """Minimal DB-backed integration test for KanbanService.get_board."""

    @pytest.mark.asyncio
    async def test_board_groups_tasks_by_computed_status(self, test_db: Database) -> None:
        # DAOs and service wiring
        repo_dao = RepoDAO(test_db)
        task_dao = TaskDAO(test_db)
        run_dao = RunDAO(test_db)
        pr_dao = PRDAO(test_db)
        review_dao = ReviewDAO(test_db)
        ci_dao = CICheckDAO(test_db)
        prefs_dao = UserPreferencesDAO(test_db)

        # Enable gating status
        await prefs_dao.save(enable_gating_status=True)

        # Dummy GitHubService (not used in this test path)
        gh = GitHubService(test_db)

        kanban = KanbanService(
            task_dao=task_dao,
            run_dao=run_dao,
            pr_dao=pr_dao,
            review_dao=review_dao,
            github_service=gh,
            user_preferences_dao=prefs_dao,
            repo_dao=repo_dao,
        )

        # Create a repo
        repo = await repo_dao.create(
            repo_url="https://github.com/acme/example",
            default_branch="main",
            latest_commit="abc123",
            workspace_path="/tmp/ws",
        )

        # T1: backlog only
        t1 = await task_dao.create(repo_id=repo.id, title="Backlog task")

        # T2: todo base status
        t2 = await task_dao.create(repo_id=repo.id, title="ToDo task")
        await task_dao.update_kanban_status(t2.id, TaskBaseKanbanStatus.TODO)

        # T3: in_progress (one running run)
        t3 = await task_dao.create(repo_id=repo.id, title="Running task")
        r3 = await run_dao.create(task_id=t3.id, instruction="run")
        await run_dao.update_status(r3.id, RunStatus.RUNNING)

        # T4: in_review (all runs completed, no PR)
        t4 = await task_dao.create(repo_id=repo.id, title="Completed runs task")
        r4a = await run_dao.create(task_id=t4.id, instruction="a")
        r4b = await run_dao.create(task_id=t4.id, instruction="b")
        await run_dao.update_status(r4a.id, RunStatus.SUCCEEDED)
        await run_dao.update_status(r4b.id, RunStatus.SUCCEEDED)

        # T5: gating (completed, PR open, CI pending)
        t5 = await task_dao.create(repo_id=repo.id, title="Gating task")
        r5 = await run_dao.create(task_id=t5.id, instruction="c")
        await run_dao.update_status(r5.id, RunStatus.SUCCEEDED)
        pr5 = await pr_dao.create(
            task_id=t5.id,
            number=42,
            url="https://github.com/acme/example/pull/42",
            branch="feat/x",
            title="PR 42",
            body=None,
            latest_commit="deadbeef",
        )
        # leave PR status as default "open"
        await ci_dao.create(task_id=t5.id, pr_id=pr5.id, status="pending")

        # T6: done (merged PR)
        t6 = await task_dao.create(repo_id=repo.id, title="Merged task")
        await pr_dao.create(
            task_id=t6.id,
            number=7,
            url="https://github.com/acme/example/pull/7",
            branch="feat/y",
            title="PR 7",
            body=None,
            latest_commit="beadfeed",
        )
        # Update latest PR to merged
        t6_prs = await pr_dao.list(t6.id)
        await pr_dao.update_status(t6_prs[0].id, "merged")

        # T7: archived (overrides any dynamic signals)
        t7 = await task_dao.create(repo_id=repo.id, title="Archived task")
        await task_dao.update_kanban_status(t7.id, TaskBaseKanbanStatus.ARCHIVED)

        board = await kanban.get_board(repo_id=repo.id)
        # Build mapping: status -> set of task ids in that column
        col_map = {c.status: {t.id for t in c.tasks} for c in board.columns}

        assert t1.id in col_map.get(TaskKanbanStatus.BACKLOG, set())
        assert t2.id in col_map.get(TaskKanbanStatus.TODO, set())
        assert t3.id in col_map.get(TaskKanbanStatus.IN_PROGRESS, set())
        assert t4.id in col_map.get(TaskKanbanStatus.IN_REVIEW, set())
        assert t5.id in col_map.get(TaskKanbanStatus.GATING, set())
        assert t6.id in col_map.get(TaskKanbanStatus.DONE, set())
        assert t7.id in col_map.get(TaskKanbanStatus.ARCHIVED, set())
