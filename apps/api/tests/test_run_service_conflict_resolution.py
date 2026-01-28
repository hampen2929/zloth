from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from zloth_api.domain.enums import ExecutorType, RunStatus
from zloth_api.domain.models import Run
from zloth_api.executors.base_executor import ExecutorResult
from zloth_api.services.git_service import GitService
from zloth_api.services.model_service import ModelService
from zloth_api.services.repo_service import RepoService
from zloth_api.services.run_service import RunService
from zloth_api.services.workspace_service import WorkspaceService
from zloth_api.storage.dao import JobDAO, RunDAO, TaskDAO, UserPreferencesDAO


def _build_run() -> Run:
    return Run(
        id="run-1",
        task_id="task-1",
        model_id=None,
        model_name=None,
        provider=None,
        executor_type=ExecutorType.CLAUDE_CODE,
        instruction="Resolve conflicts",
        base_ref="main",
        status=RunStatus.RUNNING,
        created_at=datetime.utcnow(),
    )


@pytest.mark.asyncio
async def test_resolve_conflicts_completes_merge(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "MERGE_HEAD").write_text("merge")

    workspace_service = AsyncMock(spec=WorkspaceService)
    workspace_service.get_conflict_files.return_value = []
    workspace_service.complete_merge.return_value = "abc1234"

    run_service = RunService(
        run_dao=AsyncMock(spec=RunDAO),
        task_dao=AsyncMock(spec=TaskDAO),
        job_dao=AsyncMock(spec=JobDAO),
        model_service=AsyncMock(spec=ModelService),
        repo_service=AsyncMock(spec=RepoService),
        git_service=AsyncMock(spec=GitService),
        workspace_service=workspace_service,
        user_preferences_dao=AsyncMock(spec=UserPreferencesDAO),
    )

    executor = AsyncMock()
    executor.execute.return_value = ExecutorResult(
        success=True,
        summary="",
        patch="",
        files_changed=[],
        logs=["resolved"],
    )

    logs: list[str] = []

    await run_service._resolve_conflicts_with_ai(
        run=_build_run(),
        worktree_path=tmp_path,
        conflict_files=["file.txt"],
        executor=executor,
        executor_name="Claude Code",
        logs=logs,
    )

    workspace_service.complete_merge.assert_awaited_once()
    assert any("Completed merge after conflict resolution" in entry for entry in logs)


@pytest.mark.asyncio
async def test_resolve_conflicts_raises_on_remaining_conflicts(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()

    workspace_service = AsyncMock(spec=WorkspaceService)
    workspace_service.get_conflict_files.return_value = ["file.txt"]

    run_service = RunService(
        run_dao=AsyncMock(spec=RunDAO),
        task_dao=AsyncMock(spec=TaskDAO),
        job_dao=AsyncMock(spec=JobDAO),
        model_service=AsyncMock(spec=ModelService),
        repo_service=AsyncMock(spec=RepoService),
        git_service=AsyncMock(spec=GitService),
        workspace_service=workspace_service,
        user_preferences_dao=AsyncMock(spec=UserPreferencesDAO),
    )

    executor = AsyncMock()
    executor.execute.return_value = ExecutorResult(
        success=True,
        summary="",
        patch="",
        files_changed=[],
        logs=[],
    )

    logs: list[str] = []

    with pytest.raises(RuntimeError, match="Unresolved merge conflicts remain"):
        await run_service._resolve_conflicts_with_ai(
            run=_build_run(),
            worktree_path=tmp_path,
            conflict_files=["file.txt"],
            executor=executor,
            executor_name="Claude Code",
            logs=logs,
        )
