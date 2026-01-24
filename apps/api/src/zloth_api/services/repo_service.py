"""Repository management service."""

from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path
from typing import TYPE_CHECKING

import git

from zloth_api.config import settings
from zloth_api.domain.models import Repo, RepoCloneRequest, RepoSelectRequest
from zloth_api.errors import ForbiddenError
from zloth_api.storage.dao import RepoDAO

if TYPE_CHECKING:
    from zloth_api.services.github_service import GitHubService


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
            ForbiddenError: If the directory is not writable.
        """
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        if not os.access(self.workspaces_dir, os.W_OK):
            raise ForbiddenError(
                f"Workspaces directory '{self.workspaces_dir}' is not writable.",
                details={
                    "path": str(self.workspaces_dir),
                    "hint": f"chmod -R u+w {self.workspaces_dir}",
                },
            )

    async def clone(self, data: RepoCloneRequest) -> Repo:
        """Clone a repository.

        Args:
            data: Clone request with repo URL and optional ref.

        Returns:
            Repo object with clone information.

        Raises:
            ForbiddenError: If the workspaces directory is not writable.
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
            ForbiddenError: If the workspaces directory is not writable.
        """
        # Construct the repo URL
        repo_url = f"https://github.com/{data.owner}/{data.repo}"

        # Check if already cloned
        existing = await self.find_by_url(repo_url)
        if existing:
            # Update selected_branch if a branch is specified
            if data.branch:
                # Save selected_branch to database for use as default base_ref
                await self.dao.update_selected_branch(existing.id, data.branch)
                # Update the existing object to reflect the change
                existing.selected_branch = data.branch

                workspace_path = Path(existing.workspace_path)
                if workspace_path.exists():
                    repo = git.Repo(workspace_path)
                    fetch_succeeded = False
                    try:
                        # Fetch the branch from origin with auth, updating remote tracking branch
                        # Use refspec to explicitly update refs/remotes/origin/{branch}
                        auth_url = await github_service.clone_url(data.owner, data.repo)
                        refspec = f"+refs/heads/{data.branch}:refs/remotes/origin/{data.branch}"
                        repo.git.fetch(auth_url, refspec, depth=1)
                        fetch_succeeded = True
                    except git.GitCommandError:
                        # Branch might not exist on remote, will try local branch below
                        pass

                    try:
                        if fetch_succeeded:
                            # Use origin/{branch} instead of FETCH_HEAD for reliability
                            # Using -B to reset the local branch if it already exists
                            repo.git.checkout("-B", data.branch, f"origin/{data.branch}")
                        else:
                            # Fetch failed - try to checkout existing local branch
                            # or the branch may already exist from a previous clone
                            try:
                                repo.git.checkout(data.branch)
                            except git.GitCommandError:
                                # Branch doesn't exist locally either, try to create from HEAD
                                repo.git.checkout("-b", data.branch)
                    except git.GitCommandError as e:
                        # Branch might already be checked out in a worktree, which is fine.
                        # Git prevents checking out the same branch in multiple places,
                        # but the branch exists and is available for worktree operations.
                        if "already checked out at" in str(e):
                            pass  # Safe to ignore - branch exists in a worktree
                        else:
                            raise
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
