"""Tests for push_with_retry handling shallow clones and single-branch fetch.

These tests verify that when a remote branch is updated independently (e.g.
via GitHub's "Update branch" button), the push_with_retry logic correctly:

1. Unshallows the repository before attempting to pull.
2. Fetches the specific working branch (not just the base branch).
3. Successfully pulls + pushes after retry.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import git
import pytest

from zloth_api.services.git_service import GitService


def _run(coro: object) -> object:
    """Helper to run a coroutine in the current event loop or create one."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)  # type: ignore[arg-type]
    finally:
        loop.close()


def _create_bare_remote_with_commit(tmp_path: Path) -> Path:
    """Create a bare repository with multiple commits on 'main'.

    We need at least 2 commits so that ``--depth 1`` actually creates a
    shallow clone (a single-commit repo has nothing to truncate).
    """
    seed_path = tmp_path / "_seed"
    seed_repo = git.Repo.init(seed_path)
    seed_repo.git.checkout("-b", "main")

    readme = seed_path / "README.md"
    readme.write_text("# Hello\n")
    seed_repo.index.add(["README.md"])
    seed_repo.index.commit("Initial commit")

    readme.write_text("# Hello\nUpdated.\n")
    seed_repo.index.add(["README.md"])
    seed_repo.index.commit("Second commit")

    remote_path = tmp_path / "remote.git"
    git.Repo.clone_from(str(seed_path), str(remote_path), bare=True)
    return remote_path


def _shallow_clone_workspace(
    remote_path: Path,
    workspace_path: Path,
    base_branch: str = "main",
    work_branch: str = "zloth/test1234",
) -> git.Repo:
    """Simulate WorkspaceService.create_workspace: shallow single-branch clone.

    Uses ``file://`` URL so that ``--depth`` is honoured for local repos
    (plain path clones ignore ``--depth``).
    """
    repo = git.Repo.clone_from(
        f"file://{remote_path}",
        str(workspace_path),
        depth=1,
        single_branch=True,
        branch=base_branch,
    )
    # Restore plain path as remote URL (matches production behaviour where
    # auth URL is swapped back after clone).
    repo.remotes.origin.set_url(str(remote_path))
    repo.git.checkout("-b", work_branch)
    return repo


@pytest.fixture
def git_service() -> GitService:
    return GitService()


@pytest.fixture
def setup_repos(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Set up: bare remote, a 'committer' clone, and a shallow workspace.

    Returns (remote_path, committer_path, workspace_path).
    """
    remote_path = _create_bare_remote_with_commit(tmp_path)

    # Create a normal clone for simulating remote-side changes
    committer_path = tmp_path / "committer"
    git.Repo.clone_from(str(remote_path), str(committer_path))

    workspace_path = tmp_path / "workspace"
    return remote_path, committer_path, workspace_path


# ------------------------------------------------------------------ #
# _ensure_unshallow
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_ensure_unshallow_converts_shallow_clone(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """A shallow clone should be unshallowed."""
    remote_path, _, workspace_path = setup_repos

    repo = _shallow_clone_workspace(remote_path, workspace_path)
    shallow_file = workspace_path / ".git" / "shallow"
    assert shallow_file.exists(), "Precondition: clone must be shallow"

    await git_service._ensure_unshallow(workspace_path)

    assert not shallow_file.exists(), "Repository should no longer be shallow"
    # Verify git operations still work
    repo.git.log("--oneline")


@pytest.mark.asyncio
async def test_ensure_unshallow_noop_on_full_clone(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """A full clone should be left untouched."""
    remote_path, _, workspace_path = setup_repos

    # Full (non-shallow) clone
    repo = git.Repo.clone_from(str(remote_path), str(workspace_path))
    shallow_file = workspace_path / ".git" / "shallow"
    assert not shallow_file.exists()

    # Should be a no-op
    await git_service._ensure_unshallow(workspace_path)
    assert not shallow_file.exists()
    repo.git.log("--oneline")


# ------------------------------------------------------------------ #
# _fetch_branch
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_fetch_branch_retrieves_remote_branch(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """_fetch_branch should make a remote branch visible locally."""
    remote_path, committer_path, workspace_path = setup_repos
    branch_name = "zloth/test1234"

    # Create the branch on the remote via the committer clone
    committer_repo = git.Repo(committer_path)
    committer_repo.git.checkout("-b", branch_name)
    test_file = committer_path / "test.txt"
    test_file.write_text("test content\n")
    committer_repo.index.add(["test.txt"])
    committer_repo.index.commit("Add test file")
    committer_repo.git.push("-u", "origin", branch_name)

    # Shallow clone (single-branch, base=main) — won't know about the branch
    _shallow_clone_workspace(remote_path, workspace_path)
    repo = git.Repo(workspace_path)

    # Before fetch: remote ref should not exist
    with pytest.raises(git.GitCommandError):
        repo.git.show_ref("--verify", f"refs/remotes/origin/{branch_name}")

    await git_service._fetch_branch(workspace_path, branch=branch_name)

    # After fetch: remote ref should exist
    repo.git.show_ref("--verify", f"refs/remotes/origin/{branch_name}")


@pytest.mark.asyncio
async def test_fetch_branch_noop_when_branch_not_on_remote(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """_fetch_branch should silently succeed if branch doesn't exist on remote."""
    remote_path, _, workspace_path = setup_repos

    _shallow_clone_workspace(remote_path, workspace_path)

    # Should not raise
    await git_service._fetch_branch(workspace_path, branch="nonexistent/branch")


# ------------------------------------------------------------------ #
# push_with_retry — integration
# ------------------------------------------------------------------ #


@pytest.mark.asyncio
async def test_push_with_retry_succeeds_after_remote_update(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """Simulate GitHub 'Update branch': remote has a commit the local doesn't.

    push_with_retry should unshallow, fetch, pull, and successfully push.
    """
    remote_path, committer_path, workspace_path = setup_repos
    branch_name = "zloth/test1234"

    # 1. Create shallow workspace and push initial work
    ws_repo = _shallow_clone_workspace(remote_path, workspace_path, work_branch=branch_name)
    work_file = workspace_path / "feature.txt"
    work_file.write_text("feature code\n")
    ws_repo.index.add(["feature.txt"])
    ws_repo.index.commit("Add feature")
    ws_repo.git.push("-u", "origin", branch_name)

    # 2. Simulate 'Update branch' — someone pushes a commit to the remote branch
    committer_repo = git.Repo(committer_path)
    committer_repo.git.fetch("origin")
    committer_repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
    extra_file = committer_path / "update.txt"
    extra_file.write_text("from update branch\n")
    committer_repo.index.add(["update.txt"])
    committer_repo.index.commit("Update branch merge")
    committer_repo.git.push("origin", branch_name)

    # 3. Make another local commit in the workspace
    work_file.write_text("feature code v2\n")
    ws_repo.index.add(["feature.txt"])
    ws_repo.index.commit("Update feature")

    # 4. push_with_retry should handle the non-fast-forward
    result = await git_service.push_with_retry(workspace_path, branch=branch_name, max_retries=2)

    assert result.success, f"Push should succeed but got error: {result.error}"
    assert result.required_pull, "Should have needed a pull"

    # 5. Verify both files exist on the remote
    verify_path = workspace_path.parent / "verify"
    git.Repo.clone_from(str(remote_path), str(verify_path), branch=branch_name)
    assert (verify_path / "feature.txt").exists()
    assert (verify_path / "update.txt").exists()
    assert (verify_path / "feature.txt").read_text() == "feature code v2\n"


@pytest.mark.asyncio
async def test_push_with_retry_succeeds_on_first_try(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """When remote hasn't changed, push should succeed on the first attempt."""
    remote_path, _, workspace_path = setup_repos
    branch_name = "zloth/test1234"

    ws_repo = _shallow_clone_workspace(remote_path, workspace_path, work_branch=branch_name)
    work_file = workspace_path / "feature.txt"
    work_file.write_text("feature code\n")
    ws_repo.index.add(["feature.txt"])
    ws_repo.index.commit("Add feature")

    result = await git_service.push_with_retry(workspace_path, branch=branch_name, max_retries=2)

    assert result.success
    assert not result.required_pull


@pytest.mark.asyncio
async def test_push_with_retry_handles_conflict(
    git_service: GitService, setup_repos: tuple[Path, Path, Path]
) -> None:
    """When pull results in a conflict, push_with_retry should report it."""
    remote_path, committer_path, workspace_path = setup_repos
    branch_name = "zloth/test1234"

    # 1. Create workspace and push
    ws_repo = _shallow_clone_workspace(remote_path, workspace_path, work_branch=branch_name)
    conflict_file = workspace_path / "shared.txt"
    conflict_file.write_text("local version\n")
    ws_repo.index.add(["shared.txt"])
    ws_repo.index.commit("Add shared file (local)")
    ws_repo.git.push("-u", "origin", branch_name)

    # 2. Create conflicting change on remote
    committer_repo = git.Repo(committer_path)
    committer_repo.git.fetch("origin")
    committer_repo.git.checkout("-b", branch_name, f"origin/{branch_name}")
    (committer_path / "shared.txt").write_text("remote version\n")
    committer_repo.index.add(["shared.txt"])
    committer_repo.index.commit("Modify shared file (remote)")
    committer_repo.git.push("origin", branch_name)

    # 3. Create conflicting local change
    conflict_file.write_text("conflicting local version\n")
    ws_repo.index.add(["shared.txt"])
    ws_repo.index.commit("Modify shared file (local)")

    # 4. push_with_retry should detect the conflict
    result = await git_service.push_with_retry(workspace_path, branch=branch_name, max_retries=2)

    assert not result.success
    assert result.required_pull
    assert result.error is not None
    assert "conflict" in result.error.lower() or "Merge" in result.error
