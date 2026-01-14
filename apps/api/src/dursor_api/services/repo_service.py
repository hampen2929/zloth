"""Repository management service."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import git

from dursor_api.config import settings
from dursor_api.domain.models import Repo, RepoCloneRequest, RepoSelectRequest
from dursor_api.storage.dao import RepoDAO

if TYPE_CHECKING:
    from dursor_api.services.github_service import GitHubService


class RepoService:
    """Service for managing Git repositories."""

    def __init__(self, dao: RepoDAO, github_service: GitHubService | None = None):
        self.dao = dao
        if settings.workspaces_dir:
            self.workspaces_dir: Path = settings.workspaces_dir
        else:
            raise ValueError("workspaces_dir must be set in settings")
        self._github_service = github_service

    def set_github_service(self, github_service: GitHubService) -> None:
        """Set the GitHub service (for dependency injection)."""
        self._github_service = github_service

    def _ensure_workspaces_writable(self) -> None:
        """Ensure the workspaces directory exists and is writable.

        Raises:
            PermissionError: If the directory is not writable.
        """
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(self.workspaces_dir, os.W_OK):
            raise PermissionError(
                f"Workspaces directory '{self.workspaces_dir}' is not writable. "
                f"Please fix permissions with: chmod -R u+w {self.workspaces_dir}"
            )

    async def clone(self, data: RepoCloneRequest) -> Repo:
        """Clone a repository.

        Args:
            data: Clone request with repo URL and optional ref.

        Returns:
            Repo object with clone information.

        Raises:
            PermissionError: If the workspaces directory is not writable.
        """
        # Ensure workspaces directory is writable
        self._ensure_workspaces_writable()

        # Generate unique workspace path
        workspace_id = str(uuid.uuid4())
        workspace_path = self.workspaces_dir / workspace_id

        # Clone the repository
        repo = git.Repo.clone_from(
            data.repo_url,
            workspace_path,
            depth=1,  # Shallow clone for faster initial clone
        )

        # Checkout specific ref if provided
        if data.ref:
            repo.git.checkout(data.ref)

        # Get repository info
        default_branch = repo.active_branch.name
        latest_commit = repo.head.commit.hexsha

        # Save to database
        return await self.dao.create(
            repo_url=data.repo_url,
            default_branch=default_branch,
            latest_commit=latest_commit,
            workspace_path=str(workspace_path),
        )

    async def get(self, repo_id: str) -> Repo | None:
        """Get a repository by ID.

        Args:
            repo_id: Repository ID.

        Returns:
            Repo object or None if not found.
        """
        return await self.dao.get(repo_id)

    async def find_by_url(self, repo_url: str) -> Repo | None:
        """Find a repository by URL.

        Args:
            repo_url: Git repository URL.

        Returns:
            Repo object or None if not found.
        """
        return await self.dao.find_by_url(repo_url)

    async def select(self, data: RepoSelectRequest, github_service: GitHubService) -> Repo:
        """Select and clone a repository by owner/repo name using GitHub App auth.

        Args:
            data: Selection request with owner, repo, and optional branch.
            github_service: GitHub service for authenticated cloning.

        Returns:
            Repo object with clone information.

        Raises:
            PermissionError: If the workspaces directory is not writable.
        """
        # Construct the repo URL
        repo_url = f"https://github.com/{data.owner}/{data.repo}"

        # Check if already cloned
        existing = await self.find_by_url(repo_url)
        if existing:
            # Always fetch the latest from remote to ensure we have the most recent state
            workspace_path = Path(existing.workspace_path)
            if workspace_path.exists():
                repo = git.Repo(workspace_path)
                auth_url = await github_service.clone_url(data.owner, data.repo)

                # Determine which branch to fetch and checkout
                branch_to_use = data.branch or existing.default_branch or "main"

                try:
                    # Fetch the branch from origin with auth (shallow clone may not have it)
                    repo.git.fetch(auth_url, branch_to_use, depth=1)
                except git.GitCommandError:
                    # Branch might not exist on remote, ignore fetch errors
                    pass

                try:
                    # Force checkout to FETCH_HEAD to ensure we have the latest remote state.
                    # Using -B to reset the local branch if it already exists.
                    repo.git.checkout("-B", branch_to_use, "FETCH_HEAD")
                except git.GitCommandError as e:
                    # Branch might already be checked out in a worktree, which is fine.
                    # Git prevents checking out the same branch in multiple places,
                    # but the branch exists and is available for worktree operations.
                    if "already checked out at" in str(e):
                        pass  # Safe to ignore - branch exists in a worktree
                    else:
                        raise

            # Update selected_branch if a branch is specified
            if data.branch:
                # Save selected_branch to database for use as default base_ref
                await self.dao.update_selected_branch(existing.id, data.branch)
                # Update the existing object to reflect the change
                existing.selected_branch = data.branch

            return existing

        # Ensure workspaces directory is writable before cloning
        self._ensure_workspaces_writable()

        # Get authenticated clone URL
        clone_url = await github_service.clone_url(data.owner, data.repo)

        # Generate unique workspace path
        workspace_id = str(uuid.uuid4())
        workspace_path = self.workspaces_dir / workspace_id

        # Clone the repository
        branch = data.branch or "main"
        repo = git.Repo.clone_from(
            clone_url,
            workspace_path,
            depth=1,
            branch=branch,
        )

        # Get repository info
        default_branch = repo.active_branch.name
        latest_commit = repo.head.commit.hexsha

        # Determine selected_branch (only if explicitly specified and different from default)
        selected_branch = data.branch if data.branch and data.branch != default_branch else None

        # Save to database (store public URL, not auth URL)
        return await self.dao.create(
            repo_url=repo_url,
            default_branch=default_branch,
            selected_branch=selected_branch,
            latest_commit=latest_commit,
            workspace_path=str(workspace_path),
        )

    async def update_workspace(self, repo_id: str) -> Repo | None:
        """Pull latest changes to workspace.

        Args:
            repo_id: Repository ID.

        Returns:
            Updated Repo object or None if not found.
        """
        db_repo = await self.dao.get(repo_id)
        if not db_repo:
            return None

        workspace_path = Path(db_repo.workspace_path)
        if not workspace_path.exists():
            return None

        repo = git.Repo(workspace_path)
        repo.remotes.origin.pull()

        return db_repo

    def create_working_copy(self, repo: Repo, run_id: str) -> Path:
        """Create a working copy of a repository for a run.

        Args:
            repo: Repository object.
            run_id: Run ID for the working copy.

        Returns:
            Path to the working copy.

        Raises:
            PermissionError: If the workspaces directory is not writable.
        """
        # Ensure workspaces directory is writable
        self._ensure_workspaces_writable()

        source_path = Path(repo.workspace_path)
        target_path = self.workspaces_dir / f"run_{run_id}"

        # Copy the workspace (excluding .git for speed, we'll init fresh)
        shutil.copytree(
            source_path,
            target_path,
            ignore=shutil.ignore_patterns(".git"),
        )

        # Initialize a fresh git repo
        git.Repo.init(target_path)
        work_repo = git.Repo(target_path)
        work_repo.git.add(".")
        work_repo.index.commit("Initial state")

        return target_path

    def cleanup_working_copy(self, run_id: str) -> None:
        """Clean up a working copy after a run.

        Args:
            run_id: Run ID of the working copy.
        """
        target_path = self.workspaces_dir / f"run_{run_id}"
        if target_path.exists():
            shutil.rmtree(target_path)
