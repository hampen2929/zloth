"""Workspace management helpers for run execution.

This module handles workspace lifecycle for run execution, including:
- Reusing existing workspaces when valid
- Restoring workspaces from remote branches when local workspace is invalid
- Creating new workspaces when needed
"""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from zloth_api.services.workspace_adapters import ExecutionWorkspaceInfo, WorkspaceAdapter
from zloth_api.storage.dao import RunDAO, UserPreferencesDAO
from zloth_api.utils.github_url import parse_github_owner_repo

logger = logging.getLogger(__name__)


class RunWorkspaceManager:
    """Handle workspace lifecycle for run execution."""

    def __init__(
        self,
        run_dao: RunDAO,
        workspace_adapter: WorkspaceAdapter,
        git_service: Any,
        user_preferences_dao: UserPreferencesDAO | None = None,
        github_service: Any | None = None,
    ) -> None:
        self.run_dao = run_dao
        self.workspace_adapter = workspace_adapter
        self.git_service = git_service
        self.user_preferences_dao = user_preferences_dao
        self.github_service = github_service

    async def get_reusable_workspace(
        self,
        existing_run: Any | None,
        repo: Any,
        base_ref: str,
    ) -> ExecutionWorkspaceInfo | None:
        """Return reusable workspace info when available."""
        if not existing_run or not existing_run.worktree_path:
            return None

        workspace_path: Path | None = Path(existing_run.worktree_path)

        worktrees_root = getattr(self.git_service, "worktrees_dir", None)
        if worktrees_root and str(workspace_path).startswith(str(worktrees_root)):
            logger.info("Skipping reuse of legacy worktree path: %s", workspace_path)
            workspace_path = None

        if workspace_path is None:
            is_valid = False
        else:
            is_valid = await self.workspace_adapter.is_valid(workspace_path)

        if not is_valid or workspace_path is None:
            logger.warning(f"Workspace invalid or broken, will create new: {workspace_path}")
            return None

        workspace_info = ExecutionWorkspaceInfo(
            path=workspace_path,
            branch_name=existing_run.working_branch or "",
            base_branch=existing_run.base_ref or base_ref,
            created_at=existing_run.created_at or datetime.utcnow(),
        )
        logger.info(f"Reusing existing workspace: {workspace_path}")
        return workspace_info

    async def get_or_restore_workspace(
        self,
        existing_run: Any | None,
        repo: Any,
        base_ref: str,
        run_id: str,
    ) -> ExecutionWorkspaceInfo:
        """Get existing workspace, restore from branch, or create new.

        This method implements workspace restoration logic for branch consistency:
        1. If existing workspace is valid, reuse it
        2. If existing run has a working_branch, try to restore from remote
        3. Fallback to creating a new workspace

        Args:
            existing_run: Previous run for this task/executor combination.
            repo: Repository object.
            base_ref: Base branch for the run.
            run_id: ID of the new run.

        Returns:
            ExecutionWorkspaceInfo for the workspace.
        """
        # 1. Try to reuse existing valid workspace
        workspace_info = await self.get_reusable_workspace(existing_run, repo, base_ref)
        if workspace_info:
            return workspace_info

        # 2. If existing run has a branch, try to restore from remote
        if existing_run and existing_run.working_branch:
            try:
                logger.info(
                    f"Attempting to restore workspace from branch '{existing_run.working_branch}'"
                )

                auth_url: str | None = None
                if self.github_service and repo.repo_url:
                    try:
                        owner, repo_name = parse_github_owner_repo(repo.repo_url)
                        auth_url = await self.github_service.get_auth_url(owner, repo_name)
                    except Exception as e:
                        logger.warning(f"Could not get auth_url for restoration: {e}")

                workspace_info = await self.workspace_adapter.restore_from_branch(
                    repo=repo,
                    branch_name=existing_run.working_branch,
                    base_branch=base_ref,
                    run_id=run_id,
                    auth_url=auth_url,
                )
                logger.info(
                    f"Successfully restored workspace from branch '{existing_run.working_branch}'"
                )
                return workspace_info

            except Exception as e:
                logger.warning(
                    f"Failed to restore workspace from branch "
                    f"'{existing_run.working_branch}': {e}. Will create new workspace."
                )

        # 3. Create new workspace
        return await self.create_workspace(run_id, repo, base_ref)

    async def restore_workspace(
        self,
        *,
        repo: Any,
        branch_name: str,
        base_ref: str,
        run_id: str,
        workspace_path: Path,
    ) -> ExecutionWorkspaceInfo:
        """Restore workspace from an existing branch at a fixed path."""
        auth_url: str | None = None
        if self.github_service and repo.repo_url:
            try:
                owner, repo_name = parse_github_owner_repo(repo.repo_url)
                auth_url = await self.github_service.get_auth_url(owner, repo_name)
            except Exception as e:
                logger.warning(f"Could not get auth_url for restoration: {e}")

        return await self.workspace_adapter.restore_from_branch(
            repo=repo,
            branch_name=branch_name,
            base_branch=base_ref,
            run_id=run_id,
            auth_url=auth_url,
            workspace_path=workspace_path,
        )

    async def create_workspace(
        self,
        run_id: str,
        repo: Any,
        base_ref: str,
    ) -> ExecutionWorkspaceInfo:
        """Create a new workspace for a run."""
        branch_prefix: str | None = None
        if self.user_preferences_dao:
            prefs = await self.user_preferences_dao.get()
            branch_prefix = prefs.default_branch_prefix if prefs else None

        auth_url: str | None = None
        if self.github_service and repo.repo_url:
            try:
                owner, repo_name = parse_github_owner_repo(repo.repo_url)
                auth_url = await self.github_service.get_auth_url(owner, repo_name)
            except Exception as e:
                logger.warning(f"Could not get auth_url for workspace creation: {e}")

        logger.info(f"Creating execution workspace for run {run_id[:8]}")
        return await self.workspace_adapter.create(
            repo=repo,
            base_branch=base_ref,
            run_id=run_id,
            branch_prefix=branch_prefix,
            auth_url=auth_url,
        )

    async def update_run_workspace(
        self,
        run_id: str,
        workspace_info: ExecutionWorkspaceInfo,
    ) -> None:
        """Persist workspace info for a run."""
        await self.run_dao.update_worktree(
            run_id,
            working_branch=workspace_info.branch_name,
            worktree_path=str(workspace_info.path),
        )

    async def cleanup_workspace(self, run: Any, delete_branch: bool) -> bool:
        """Cleanup workspace for a run if one exists."""
        if not run or not run.worktree_path:
            return False

        workspace_path = Path(run.worktree_path)
        await self.workspace_adapter.cleanup(path=workspace_path, delete_branch=delete_branch)
        return True
