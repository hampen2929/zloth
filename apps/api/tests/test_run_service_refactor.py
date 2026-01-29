"""Regression tests for RunService refactor utilities."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from zloth_api.domain.models import Repo
from zloth_api.services.diff_parser import parse_unified_diff
from zloth_api.services.git_service import (
    GitService,
    PullResult,
    PushResult,
    WorktreeInfo,
)
from zloth_api.services.git_service import (
    MergeResult as GitMergeResult,
)
from zloth_api.services.workspace_adapters import (
    CloneWorkspaceAdapter,
    WorktreeWorkspaceAdapter,
)
from zloth_api.services.workspace_service import (
    MergeResult as WorkspaceMergeResult,
)
from zloth_api.services.workspace_service import (
    WorkspaceInfo,
    WorkspaceService,
)
from zloth_api.utils.github_url import parse_github_owner_repo


class TestGitHubUrlParsing:
    def test_parse_https_git(self) -> None:
        assert parse_github_owner_repo("https://github.com/owner/repo.git") == ("owner", "repo")

    def test_parse_https_no_git(self) -> None:
        assert parse_github_owner_repo("https://github.com/owner/repo") == ("owner", "repo")

    def test_parse_ssh_git(self) -> None:
        assert parse_github_owner_repo("git@github.com:owner/repo.git") == ("owner", "repo")

    def test_parse_ssh_no_git(self) -> None:
        assert parse_github_owner_repo("git@github.com:owner/repo") == ("owner", "repo")

    def test_parse_invalid_raises(self) -> None:
        with pytest.raises(ValueError):
            parse_github_owner_repo("https://example.com/not-github/owner/repo")


class TestDiffParser:
    def test_parse_two_files_counts(self) -> None:
        diff = "\n".join(
            [
                "--- a/foo.txt",
                "+++ b/foo.txt",
                "@@",
                "-old",
                "+new",
                "--- a/bar.txt",
                "+++ b/bar.txt",
                "@@",
                "+added",
                "+added2",
            ]
        )
        files = parse_unified_diff(diff)
        assert [f.path for f in files] == ["foo.txt", "bar.txt"]
        assert files[0].added_lines == 1
        assert files[0].removed_lines == 1
        assert files[1].added_lines == 2
        assert files[1].removed_lines == 0


@pytest.mark.asyncio
async def test_clone_workspace_adapter_maps_results() -> None:
    ws = AsyncMock(spec=WorkspaceService)
    git = AsyncMock(spec=GitService)
    created_at = datetime.utcnow()
    ws.create_workspace.return_value = WorkspaceInfo(
        path=Path("/tmp/run_x"),
        branch_name="zloth/1234",
        base_branch="main",
        created_at=created_at,
    )
    ws.sync_with_remote.return_value = WorkspaceMergeResult(
        success=False, has_conflicts=True, conflict_files=["a"]
    )
    ws.is_behind_remote.return_value = True
    ws.is_valid_workspace.return_value = True

    git.push_with_retry.return_value = PushResult(success=True, required_pull=True)
    ws.merge_base_branch.return_value = WorkspaceMergeResult(
        success=False, has_conflicts=True, conflict_files=["b"]
    )

    adapter = CloneWorkspaceAdapter(ws, git)

    repo = Repo(
        id="r1",
        repo_url="https://github.com/owner/repo",
        default_branch="main",
        latest_commit="abc",
        workspace_path="/tmp/repo",
        created_at=datetime.utcnow(),
    )

    info = await adapter.create(repo=repo, base_branch="main", run_id="run1")
    assert info.path == Path("/tmp/run_x")
    assert info.branch_name == "zloth/1234"

    behind = await adapter.is_behind_remote(Path("/tmp/run_x"), branch="zloth/1234")
    assert behind is True

    sync = await adapter.sync_with_remote(Path("/tmp/run_x"), branch="zloth/1234")
    assert sync.success is False
    assert sync.has_conflicts is True
    assert sync.conflict_files == ["a"]

    base_merge = await adapter.merge_base_branch(Path("/tmp/run_x"), base_branch="main")
    assert base_merge.success is False
    assert base_merge.has_conflicts is True
    assert base_merge.conflict_files == ["b"]

    pushed = await adapter.push(Path("/tmp/run_x"), branch="zloth/1234")
    assert pushed.success is True
    assert pushed.required_pull is True


@pytest.mark.asyncio
async def test_worktree_workspace_adapter_maps_results() -> None:
    git = AsyncMock(spec=GitService)
    created_at = datetime.utcnow()
    git.create_worktree.return_value = WorktreeInfo(
        path=Path("/tmp/run_x"),
        branch_name="zloth/1234",
        base_branch="main",
        created_at=created_at,
    )
    git.pull.return_value = PullResult(success=True)
    git.is_behind_remote.return_value = False
    git.is_valid_worktree.return_value = True
    git.push_with_retry.return_value = PushResult(success=True, required_pull=True)
    git.merge_base_branch.return_value = GitMergeResult(success=True)

    adapter = WorktreeWorkspaceAdapter(git)

    repo = Repo(
        id="r1",
        repo_url="https://github.com/owner/repo",
        default_branch="main",
        latest_commit="abc",
        workspace_path="/tmp/repo",
        created_at=datetime.utcnow(),
    )

    info = await adapter.create(repo=repo, base_branch="main", run_id="run1")
    assert info.path == Path("/tmp/run_x")

    behind = await adapter.is_behind_remote(Path("/tmp/run_x"), branch="zloth/1234")
    assert behind is False

    sync = await adapter.sync_with_remote(Path("/tmp/run_x"), branch="zloth/1234")
    assert sync.success is True

    pushed = await adapter.push(Path("/tmp/run_x"), branch="zloth/1234")
    assert pushed.success is True
    assert pushed.required_pull is True

    base_merge = await adapter.merge_base_branch(Path("/tmp/run_x"), base_branch="main")
    assert base_merge.success is True
