"""Pull Request management service."""

from __future__ import annotations

import subprocess
import uuid
from pathlib import Path
from typing import TYPE_CHECKING
from urllib.parse import urlparse

import git

from dursor_api.domain.models import PR, PRCreate, PRUpdate
from dursor_api.services.repo_service import RepoService
from dursor_api.storage.dao import PRDAO, RunDAO, TaskDAO

if TYPE_CHECKING:
    from dursor_api.services.github_service import GitHubService


class GitHubPermissionError(Exception):
    """Raised when GitHub App lacks required permissions."""

    pass


class PRService:
    """Service for managing Pull Requests."""

    def __init__(
        self,
        pr_dao: PRDAO,
        task_dao: TaskDAO,
        run_dao: RunDAO,
        repo_service: RepoService,
        github_service: GitHubService,
    ):
        self.pr_dao = pr_dao
        self.task_dao = task_dao
        self.run_dao = run_dao
        self.repo_service = repo_service
        self.github_service = github_service

    def _parse_github_url(self, repo_url: str) -> tuple[str, str]:
        """Parse owner and repo from GitHub URL.

        Args:
            repo_url: GitHub repository URL.

        Returns:
            Tuple of (owner, repo_name).
        """
        # Handle different URL formats
        if repo_url.startswith("git@github.com:"):
            path = repo_url.replace("git@github.com:", "").replace(".git", "")
        else:
            parsed = urlparse(repo_url)
            path = parsed.path.strip("/").replace(".git", "")

        parts = path.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid GitHub URL: {repo_url}")

        return parts[0], parts[1]

    async def create(self, task_id: str, data: PRCreate) -> PR:
        """Create a new Pull Request.

        Args:
            task_id: Task ID.
            data: PR creation data.

        Returns:
            Created PR object.
        """
        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")
        if not run.patch:
            raise ValueError("Run has no patch to apply")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # Create branch name
        branch_name = f"dursor/{uuid.uuid4().hex[:8]}"

        # Apply patch and create branch
        workspace_path = Path(repo_obj.workspace_path)
        repo = git.Repo(workspace_path)

        # Create and checkout new branch
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        # Apply patch
        patch_file = workspace_path / ".dursor_patch.diff"
        try:
            patch_file.write_text(run.patch)
            result = subprocess.run(
                ["git", "apply", "--whitespace=fix", str(patch_file)],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Clean up: switch back to default branch and delete the created branch
                repo.heads[repo_obj.default_branch].checkout()
                repo.delete_head(branch_name, force=True)
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise ValueError(f"Failed to apply patch: {error_msg}")
        finally:
            patch_file.unlink(missing_ok=True)

        # Commit changes
        repo.git.add(".")
        repo.index.commit(data.title)

        # Push branch using GitHub App authentication
        auth_url = await self.github_service.get_auth_url(owner, repo_name)
        try:
            repo.git.push(auth_url, branch_name)
        except git.exc.GitCommandError as e:
            # Clean up: switch back to default branch and delete the created branch
            repo.heads[repo_obj.default_branch].checkout()
            repo.delete_head(branch_name, force=True)

            if "403" in str(e) or "Write access" in str(e):
                raise GitHubPermissionError(
                    f"GitHub App lacks write access to {owner}/{repo_name}. "
                    "Please ensure the GitHub App has 'Contents' permission set to 'Read and write' "
                    "and is installed on this repository."
                ) from e
            raise

        # Create PR via GitHub API using GitHub App
        pr_data = await self.github_service.create_pull_request(
            owner=owner,
            repo=repo_name,
            title=data.title,
            head=branch_name,
            base=repo_obj.default_branch,
            body=data.body or f"Generated by dursor\n\n{run.summary}",
        )

        # Switch back to default branch
        repo.heads[repo_obj.default_branch].checkout()

        # Save to database
        return await self.pr_dao.create(
            task_id=task_id,
            number=pr_data["number"],
            url=pr_data["html_url"],
            branch=branch_name,
            title=data.title,
            body=data.body,
            latest_commit=repo.head.commit.hexsha,
        )

    async def update(self, task_id: str, pr_id: str, data: PRUpdate) -> PR:
        """Update an existing Pull Request.

        Args:
            task_id: Task ID.
            pr_id: PR ID.
            data: PR update data.

        Returns:
            Updated PR object.
        """
        # Get PR
        pr = await self.pr_dao.get(pr_id)
        if not pr or pr.task_id != task_id:
            raise ValueError(f"PR not found: {pr_id}")

        # Get task and repo
        task = await self.task_dao.get(task_id)
        if not task:
            raise ValueError(f"Task not found: {task_id}")

        repo_obj = await self.repo_service.get(task.repo_id)
        if not repo_obj:
            raise ValueError(f"Repo not found: {task.repo_id}")

        # Get run
        run = await self.run_dao.get(data.selected_run_id)
        if not run:
            raise ValueError(f"Run not found: {data.selected_run_id}")
        if not run.patch:
            raise ValueError("Run has no patch to apply")

        # Parse GitHub info
        owner, repo_name = self._parse_github_url(repo_obj.repo_url)

        # Apply patch to existing branch
        workspace_path = Path(repo_obj.workspace_path)
        repo = git.Repo(workspace_path)

        # Checkout PR branch
        repo.git.checkout(pr.branch)

        # Apply patch
        patch_file = workspace_path / ".dursor_patch.diff"
        try:
            patch_file.write_text(run.patch)
            result = subprocess.run(
                ["git", "apply", "--whitespace=fix", str(patch_file)],
                cwd=workspace_path,
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                # Switch back to default branch
                repo.heads[repo_obj.default_branch].checkout()
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                raise ValueError(f"Failed to apply patch: {error_msg}")
        finally:
            patch_file.unlink(missing_ok=True)

        # Commit changes
        repo.git.add(".")
        commit_message = data.message or f"Update: {run.summary}"
        repo.index.commit(commit_message)

        # Push using GitHub App authentication
        auth_url = await self.github_service.get_auth_url(owner, repo_name)
        try:
            repo.git.push(auth_url, pr.branch)
        except git.exc.GitCommandError as e:
            if "403" in str(e) or "Write access" in str(e):
                raise GitHubPermissionError(
                    f"GitHub App lacks write access to {owner}/{repo_name}. "
                    "Please ensure the GitHub App has 'Contents' permission set to 'Read and write' "
                    "and is installed on this repository."
                ) from e
            raise

        latest_commit = repo.head.commit.hexsha

        # Switch back to default branch
        repo.heads[repo_obj.default_branch].checkout()

        # Update database
        await self.pr_dao.update(pr_id, latest_commit)

        return await self.pr_dao.get(pr_id)

    async def get(self, task_id: str, pr_id: str) -> PR | None:
        """Get a PR by ID.

        Args:
            task_id: Task ID.
            pr_id: PR ID.

        Returns:
            PR object or None if not found.
        """
        pr = await self.pr_dao.get(pr_id)
        if pr and pr.task_id == task_id:
            return pr
        return None

    async def list(self, task_id: str) -> list[PR]:
        """List PRs for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of PR objects.
        """
        return await self.pr_dao.list(task_id)
