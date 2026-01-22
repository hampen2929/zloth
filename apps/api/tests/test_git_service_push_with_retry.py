from __future__ import annotations

from pathlib import Path

import pytest

from zloth_api.services.git_service import GitService, PullResult


@pytest.mark.asyncio
async def test_push_with_retry_skips_pull_when_remote_branch_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = GitService(workspaces_dir=tmp_path / "workspaces", worktrees_dir=tmp_path / "worktrees")

    calls: dict[str, int] = {"push": 0, "pull": 0, "exists": 0}

    async def fake_push(repo_path: Path, branch: str, auth_url: str | None = None, force: bool = False) -> None:
        calls["push"] += 1
        if calls["push"] == 1:
            # Match non-ff detection pattern to trigger retry path
            raise Exception("failed to push some refs")

    async def fake_remote_branch_exists(
        *, repo_path: Path, branch: str, auth_url: str | None = None
    ) -> bool:
        calls["exists"] += 1
        return False

    async def fake_pull(repo_path: Path, branch: str | None = None, auth_url: str | None = None) -> PullResult:
        calls["pull"] += 1
        return PullResult(success=True)

    monkeypatch.setattr(svc, "push", fake_push)
    monkeypatch.setattr(svc, "remote_branch_exists", fake_remote_branch_exists)
    monkeypatch.setattr(svc, "pull", fake_pull)

    result = await svc.push_with_retry(tmp_path, branch="zloth/abcd1234", max_retries=2)

    assert result.success is True
    assert result.required_pull is False
    assert calls["push"] == 2
    assert calls["exists"] >= 1
    assert calls["pull"] == 0


@pytest.mark.asyncio
async def test_push_with_retry_pulls_when_remote_branch_exists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    svc = GitService(workspaces_dir=tmp_path / "workspaces", worktrees_dir=tmp_path / "worktrees")

    calls: dict[str, int] = {"push": 0, "pull": 0, "exists": 0}

    async def fake_push(repo_path: Path, branch: str, auth_url: str | None = None, force: bool = False) -> None:
        calls["push"] += 1
        if calls["push"] == 1:
            raise Exception("updates were rejected: failed to push some refs")

    async def fake_remote_branch_exists(
        *, repo_path: Path, branch: str, auth_url: str | None = None
    ) -> bool:
        calls["exists"] += 1
        return True

    async def fake_pull(repo_path: Path, branch: str | None = None, auth_url: str | None = None) -> PullResult:
        calls["pull"] += 1
        return PullResult(success=True)

    monkeypatch.setattr(svc, "push", fake_push)
    monkeypatch.setattr(svc, "remote_branch_exists", fake_remote_branch_exists)
    monkeypatch.setattr(svc, "pull", fake_pull)

    result = await svc.push_with_retry(tmp_path, branch="zloth/abcd1234", max_retries=2)

    assert result.success is True
    assert result.required_pull is True
    assert calls["push"] == 2
    assert calls["exists"] >= 1
    assert calls["pull"] == 1

