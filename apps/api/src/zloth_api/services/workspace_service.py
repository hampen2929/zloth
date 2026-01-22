"""Clone-based workspace management service.

This service implements the clone-based isolation workflow described in
docs/worktree_workflow_diagram.md ("Clone方式"). It creates an isolated
shallow clone per run, prepares a working branch, and provides helpers for
remote sync and conflict-aware merging. Git operations that are common to
both clone/worktree modes are delegated to GitService.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import git

from zloth_api.config import settings
from zloth_api.domain.models import Repo
from zloth_api.services.git_service import (
    GitService,
    PullResult,
    PushResult,
    WorktreeInfo,  # Reuse the same shape for workspace metadata
)

logger = logging.getLogger(__name__)


@dataclass
class MergeResult:
    """Result of a merge operation against base branch."""

    success: bool
    has_conflicts: bool = False
    conflict_files: list[str] | None = None
    error: str | None = None


class WorkspaceService:
    """Manages clone-based isolated workspaces for runs."""

    def __init__(self, workspaces_dir: Path | None = None, git_service: GitService | None = None):
        self.workspaces_dir = workspaces_dir or settings.workspaces_dir
        if not self.workspaces_dir:
            raise ValueError("workspaces_dir must be provided or set in settings")
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

        self.git_service = git_service or GitService()

    def _generate_branch_name(self, run_id: str, prefix: str | None = None) -> str:
        # Keep logic in sync with GitService's branch name generation
        from zloth_api.services.git_service import GitService as _GS

        return _GS()._generate_branch_name(run_id, branch_prefix=prefix)  # type: ignore[attr-defined]

    async def create_workspace(
        self,
        repo: Repo,
        base_branch: str,
        run_id: str,
        *,
        branch_prefix: str | None = None,
        auth_url: str | None = None,
    ) -> WorktreeInfo:
        """Create a shallow clone workspace and new working branch.

        Steps (matching the doc's Phase 1):
        - git clone --depth 1 --single-branch -b {base} {url} {workspace}
        - git checkout -b {branch_name}
        """

        branch_name = self._generate_branch_name(run_id, prefix=branch_prefix)
        workspace_path = self.workspaces_dir / f"run_{run_id}"
        clone_url = auth_url or repo.repo_url

        def _clone_and_checkout() -> WorktreeInfo:
            r = git.Repo.clone_from(
                clone_url,
                workspace_path,
                depth=1,
                single_branch=True,
                branch=base_branch,
            )

            # Create the working branch from the checked-out base
            try:
                r.git.checkout("-b", branch_name)
            except git.GitCommandError as e:
                # If branch exists (rare, e.g., reuse), switch to it
                logger.warning(f"checkout -b failed, trying checkout existing: {e}")
                r.git.checkout(branch_name)

            return WorktreeInfo(
                path=workspace_path,
                branch_name=branch_name,
                base_branch=base_branch,
                created_at=datetime.utcnow(),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _clone_and_checkout)

    async def cleanup_workspace(self, workspace_path: Path) -> None:
        """Remove an isolated workspace directory."""

        def _cleanup() -> None:
            if workspace_path.exists():
                shutil.rmtree(workspace_path, ignore_errors=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _cleanup)

    # =============================
    # Remote sync and merge helpers
    # =============================

    async def is_behind_remote(self, workspace_path: Path, branch: str, auth_url: str | None = None) -> bool:
        return await self.git_service.is_behind_remote(workspace_path, branch, auth_url=auth_url)

    async def sync_with_remote(self, workspace_path: Path, branch: str | None = None, auth_url: str | None = None) -> PullResult:
        return await self.git_service.pull(workspace_path, branch=branch, auth_url=auth_url)

    async def unshallow(self, workspace_path: Path, auth_url: str | None = None) -> None:
        """Convert a shallow clone into a full clone (best-effort)."""

        def _unshallow() -> None:
            repo = git.Repo(workspace_path)
            try:
                if auth_url:
                    repo.git.fetch(auth_url, "--unshallow")
                else:
                    repo.git.fetch("--unshallow")
            except git.GitCommandError:
                # If already unshallowed or remote doesn't support, ignore
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _unshallow)

    async def merge_base_branch(self, workspace_path: Path, base_branch: str) -> MergeResult:
        """Merge origin/{base_branch} into current branch, detecting conflicts."""

        def _merge() -> MergeResult:
            repo = git.Repo(workspace_path)
            try:
                # Ensure we have latest remote base
                try:
                    repo.git.fetch("origin", base_branch)
                except Exception:
                    pass
                repo.git.merge(f"origin/{base_branch}")
                return MergeResult(success=True)
            except git.GitCommandError as e:
                # Check for conflicts
                conflict_files: list[str] = []
                try:
                    unmerged = repo.index.unmerged_blobs()
                    conflict_files = sorted({path for path, _ in unmerged.items()})
                except Exception:
                    pass
                if conflict_files:
                    return MergeResult(success=False, has_conflicts=True, conflict_files=conflict_files)
                return MergeResult(success=False, error=str(e))

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _merge)

    async def get_conflict_files(self, workspace_path: Path) -> list[str]:
        def _get() -> list[str]:
            repo = git.Repo(workspace_path)
            try:
                unmerged = repo.index.unmerged_blobs()
                return sorted({path for path, _ in unmerged.items()})
            except Exception:
                return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get)

    async def complete_merge(self, workspace_path: Path, message: str = "Merge base branch") -> str:
        """Complete a merge after conflicts are resolved (creates a merge commit)."""

        def _complete() -> str:
            repo = git.Repo(workspace_path)
            repo.git.add("-A")
            repo.index.commit(message)
            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _complete)

    # =============================
    # Thin wrappers to GitService
    # =============================

    async def stage_all(self, workspace_path: Path) -> None:
        await self.git_service.stage_all(workspace_path)

    async def get_diff(self, workspace_path: Path, staged: bool = True) -> str:
        return await self.git_service.get_diff(workspace_path, staged=staged)

    async def commit(self, workspace_path: Path, message: str) -> str:
        return await self.git_service.commit(workspace_path, message=message)

    async def push(self, workspace_path: Path, branch: str, auth_url: str | None = None, force: bool = False) -> None:
        await self.git_service.push(workspace_path, branch=branch, auth_url=auth_url, force=force)

    async def push_with_retry(
        self,
        workspace_path: Path,
        branch: str,
        auth_url: str | None = None,
        max_retries: int = 2,
    ) -> PushResult:
        return await self.git_service.push_with_retry(
            workspace_path, branch=branch, auth_url=auth_url, max_retries=max_retries
        )

