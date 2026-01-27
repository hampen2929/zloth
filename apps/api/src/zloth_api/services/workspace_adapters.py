"""Workspace adapter layer for clone/worktree isolation.

This module isolates the differences between clone-based workspaces
(`WorkspaceService`) and worktree-based isolation (`GitService`), so callers
do not need to branch on `settings.use_clone_isolation`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Protocol

from zloth_api.domain.models import Repo
from zloth_api.services.git_service import GitService
from zloth_api.services.workspace_service import WorkspaceService


@dataclass(frozen=True)
class ExecutionWorkspaceInfo:
    """Normalized workspace info used by execution services."""

    path: Path
    branch_name: str
    base_branch: str
    created_at: datetime


@dataclass(frozen=True)
class SyncResult:
    """Normalized result of a remote sync operation (pull/merge)."""

    success: bool
    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass(frozen=True)
class PushAttemptResult:
    """Normalized result of a push operation."""

    success: bool
    required_pull: bool = False
    error: str | None = None


class WorkspaceAdapter(Protocol):
    """Interface for workspace operations required by run execution."""

    async def is_valid(self, path: Path) -> bool: ...

    async def create(
        self,
        *,
        repo: Repo,
        base_branch: str,
        run_id: str,
        branch_prefix: str | None = None,
        auth_url: str | None = None,
    ) -> ExecutionWorkspaceInfo: ...

    async def restore_from_branch(
        self,
        *,
        repo: Repo,
        branch_name: str,
        base_branch: str,
        run_id: str,
        auth_url: str | None = None,
    ) -> ExecutionWorkspaceInfo: ...

    async def cleanup(self, *, path: Path, delete_branch: bool) -> None: ...

    async def stage_all(self, path: Path) -> None: ...

    async def get_diff(self, path: Path, *, staged: bool = True) -> str: ...

    async def commit(self, path: Path, *, message: str) -> str: ...

    async def is_behind_remote(
        self,
        path: Path,
        *,
        branch: str,
        auth_url: str | None = None,
    ) -> bool: ...

    async def sync_with_remote(
        self, path: Path, *, branch: str, auth_url: str | None = None
    ) -> SyncResult: ...

    async def push(
        self, path: Path, *, branch: str, auth_url: str | None = None
    ) -> PushAttemptResult: ...


class CloneWorkspaceAdapter:
    """Adapter for clone-based isolation using WorkspaceService."""

    def __init__(self, workspace_service: WorkspaceService) -> None:
        self._ws = workspace_service

    async def is_valid(self, path: Path) -> bool:
        return await self._ws.is_valid_workspace(path)

    async def create(
        self,
        *,
        repo: Repo,
        base_branch: str,
        run_id: str,
        branch_prefix: str | None = None,
        auth_url: str | None = None,
    ) -> ExecutionWorkspaceInfo:
        if not repo.repo_url:
            raise ValueError("repo.repo_url is required for clone-based workspace creation")
        info = await self._ws.create_workspace(
            repo_url=repo.repo_url,
            base_branch=base_branch,
            run_id=run_id,
            branch_prefix=branch_prefix,
            auth_url=auth_url,
        )
        return ExecutionWorkspaceInfo(
            path=info.path,
            branch_name=info.branch_name,
            base_branch=info.base_branch,
            created_at=info.created_at,
        )

    async def restore_from_branch(
        self,
        *,
        repo: Repo,
        branch_name: str,
        base_branch: str,
        run_id: str,
        auth_url: str | None = None,
    ) -> ExecutionWorkspaceInfo:
        """Restore workspace from an existing remote branch.

        This is used when a workspace is invalid but the branch exists on remote.
        """
        if not repo.repo_url:
            raise ValueError("repo.repo_url is required for workspace restoration")
        info = await self._ws.restore_workspace(
            repo_url=repo.repo_url,
            branch_name=branch_name,
            base_branch=base_branch,
            run_id=run_id,
            auth_url=auth_url,
        )
        return ExecutionWorkspaceInfo(
            path=info.path,
            branch_name=info.branch_name,
            base_branch=info.base_branch,
            created_at=info.created_at,
        )

    async def cleanup(self, *, path: Path, delete_branch: bool) -> None:
        # delete_branch is not applicable in clone mode
        await self._ws.cleanup_workspace(path)

    async def stage_all(self, path: Path) -> None:
        await self._ws.stage_all(path)

    async def get_diff(self, path: Path, *, staged: bool = True) -> str:
        return await self._ws.get_diff(path, staged=staged)

    async def commit(self, path: Path, *, message: str) -> str:
        return await self._ws.commit(path, message=message)

    async def is_behind_remote(
        self,
        path: Path,
        *,
        branch: str,
        auth_url: str | None = None,
    ) -> bool:
        return await self._ws.is_behind_remote(path, branch=branch, auth_url=auth_url)

    async def sync_with_remote(
        self, path: Path, *, branch: str, auth_url: str | None = None
    ) -> SyncResult:
        res = await self._ws.sync_with_remote(path, branch=branch, auth_url=auth_url)
        return SyncResult(
            success=res.success,
            has_conflicts=res.has_conflicts,
            conflict_files=list(res.conflict_files),
            error=res.error,
        )

    async def push(
        self, path: Path, *, branch: str, auth_url: str | None = None
    ) -> PushAttemptResult:
        try:
            await self._ws.push(path, branch=branch, auth_url=auth_url)
            return PushAttemptResult(success=True, required_pull=False)
        except Exception as e:
            return PushAttemptResult(success=False, required_pull=False, error=str(e))


class WorktreeWorkspaceAdapter:
    """Adapter for worktree-based isolation using GitService."""

    def __init__(self, git_service: GitService) -> None:
        self._git = git_service

    async def is_valid(self, path: Path) -> bool:
        return await self._git.is_valid_worktree(path)

    async def create(
        self,
        *,
        repo: Repo,
        base_branch: str,
        run_id: str,
        branch_prefix: str | None = None,
        auth_url: str | None = None,
    ) -> ExecutionWorkspaceInfo:
        info = await self._git.create_worktree(
            repo=repo,
            base_branch=base_branch,
            run_id=run_id,
            branch_prefix=branch_prefix,
            auth_url=auth_url,
        )
        return ExecutionWorkspaceInfo(
            path=info.path,
            branch_name=info.branch_name,
            base_branch=info.base_branch,
            created_at=info.created_at,
        )

    async def restore_from_branch(
        self,
        *,
        repo: Repo,
        branch_name: str,
        base_branch: str,
        run_id: str,
        auth_url: str | None = None,
    ) -> ExecutionWorkspaceInfo:
        """Restore workspace from an existing branch.

        For worktree adapter, we fall back to creating a new workspace
        since worktree restoration from remote branch is not straightforward.
        """
        # Worktree mode is deprecated; fallback to creating new workspace
        return await self.create(
            repo=repo,
            base_branch=base_branch,
            run_id=run_id,
            branch_prefix=None,
            auth_url=auth_url,
        )

    async def cleanup(self, *, path: Path, delete_branch: bool) -> None:
        await self._git.cleanup_worktree(path, delete_branch=delete_branch)

    async def stage_all(self, path: Path) -> None:
        await self._git.stage_all(path)

    async def get_diff(self, path: Path, *, staged: bool = True) -> str:
        return await self._git.get_diff(path, staged=staged)

    async def commit(self, path: Path, *, message: str) -> str:
        return await self._git.commit(path, message=message)

    async def is_behind_remote(
        self,
        path: Path,
        *,
        branch: str,
        auth_url: str | None = None,
    ) -> bool:
        return await self._git.is_behind_remote(path, branch=branch, auth_url=auth_url)

    async def sync_with_remote(
        self, path: Path, *, branch: str, auth_url: str | None = None
    ) -> SyncResult:
        res = await self._git.pull(path, branch=branch, auth_url=auth_url)
        return SyncResult(
            success=res.success,
            has_conflicts=res.has_conflicts,
            conflict_files=list(res.conflict_files),
            error=res.error,
        )

    async def push(
        self, path: Path, *, branch: str, auth_url: str | None = None
    ) -> PushAttemptResult:
        res = await self._git.push_with_retry(path, branch=branch, auth_url=auth_url)
        return PushAttemptResult(
            success=res.success,
            required_pull=res.required_pull,
            error=res.error,
        )
