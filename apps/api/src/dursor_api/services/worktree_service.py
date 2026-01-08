"""Git worktree management service for Claude Code execution."""

import asyncio
import shutil
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import git

from dursor_api.config import settings
from dursor_api.domain.models import Repo


@dataclass
class WorktreeInfo:
    """Information about a git worktree."""

    path: Path
    branch_name: str
    base_branch: str
    created_at: datetime


class WorktreeService:
    """Manages git worktrees for isolated branch development."""

    def __init__(self, workspaces_dir: Path | None = None):
        """Initialize WorktreeService.

        Args:
            workspaces_dir: Base directory for worktrees. Defaults to settings.
        """
        self.workspaces_dir = workspaces_dir or settings.workspaces_dir
        self.worktrees_dir = self.workspaces_dir / "worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    def _generate_branch_name(self, run_id: str) -> str:
        """Generate a unique branch name for a run.

        Args:
            run_id: Run ID.

        Returns:
            Branch name in format: dursor/{short_id}
        """
        short_id = run_id[:8]
        return f"dursor/{short_id}"

    async def create_worktree(
        self,
        repo: Repo,
        base_branch: str,
        run_id: str,
    ) -> WorktreeInfo:
        """Create a new git worktree for the run.

        Args:
            repo: Repository object with workspace_path.
            base_branch: Base branch to create worktree from.
            run_id: Run ID for naming.

        Returns:
            WorktreeInfo with path and branch information.

        Raises:
            git.GitCommandError: If git worktree creation fails.
        """
        branch_name = self._generate_branch_name(run_id)
        worktree_path = self.worktrees_dir / f"run_{run_id}"

        # Run git commands in a thread pool to avoid blocking
        def _create_worktree():
            source_repo = git.Repo(repo.workspace_path)

            # Fetch to ensure we have latest refs
            try:
                source_repo.remotes.origin.fetch()
            except Exception:
                # Ignore fetch errors (might be offline)
                pass

            # Ensure base branch exists locally
            try:
                # Try to checkout the base branch first to ensure it exists
                source_repo.git.checkout(base_branch)
            except git.GitCommandError:
                # If checkout fails, try to create from origin
                try:
                    source_repo.git.checkout("-b", base_branch, f"origin/{base_branch}")
                except git.GitCommandError:
                    # Branch might already exist, just use it
                    pass

            # Create worktree with new branch
            # git worktree add -b <branch> <path> <base>
            source_repo.git.worktree(
                "add",
                "-b", branch_name,
                str(worktree_path),
                base_branch,
            )

            return WorktreeInfo(
                path=worktree_path,
                branch_name=branch_name,
                base_branch=base_branch,
                created_at=datetime.utcnow(),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create_worktree)

    async def cleanup_worktree(self, worktree_path: Path, delete_branch: bool = False) -> None:
        """Remove a worktree after PR creation or run cancellation.

        Args:
            worktree_path: Path to the worktree to remove.
            delete_branch: Whether to also delete the branch.
        """
        def _cleanup():
            if not worktree_path.exists():
                return

            # Find the parent repo by looking for .git file in worktree
            git_file = worktree_path / ".git"
            if git_file.exists():
                # Read the gitdir from .git file to find parent repo
                with open(git_file) as f:
                    content = f.read().strip()
                    # Format: gitdir: /path/to/parent/.git/worktrees/<name>
                    if content.startswith("gitdir: "):
                        gitdir = content[8:]
                        # Navigate up to find parent .git directory
                        parent_git = Path(gitdir).parent.parent.parent
                        if parent_git.exists() and (parent_git / "HEAD").exists():
                            parent_repo = git.Repo(parent_git.parent)
                            # Get branch name before removal
                            try:
                                worktree_repo = git.Repo(worktree_path)
                                branch_name = worktree_repo.active_branch.name
                            except Exception:
                                branch_name = None

                            # Remove worktree
                            try:
                                parent_repo.git.worktree("remove", str(worktree_path), "--force")
                            except git.GitCommandError:
                                # If git worktree remove fails, try manual cleanup
                                shutil.rmtree(worktree_path, ignore_errors=True)

                            # Optionally delete the branch
                            if delete_branch and branch_name:
                                try:
                                    parent_repo.git.branch("-D", branch_name)
                                except git.GitCommandError:
                                    pass
                            return

            # Fallback: just remove the directory
            shutil.rmtree(worktree_path, ignore_errors=True)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _cleanup)

    async def list_worktrees(self, repo: Repo) -> list[WorktreeInfo]:
        """List all worktrees for a repository.

        Args:
            repo: Repository object.

        Returns:
            List of WorktreeInfo objects.
        """
        def _list():
            source_repo = git.Repo(repo.workspace_path)
            worktrees = []

            # Parse git worktree list --porcelain output
            try:
                output = source_repo.git.worktree("list", "--porcelain")
                current_path = None
                current_branch = None

                for line in output.split("\n"):
                    if line.startswith("worktree "):
                        current_path = Path(line[9:])
                    elif line.startswith("branch refs/heads/"):
                        current_branch = line[18:]
                    elif line == "" and current_path and current_branch:
                        # Only include worktrees in our worktrees directory
                        if str(current_path).startswith(str(self.worktrees_dir)):
                            worktrees.append(WorktreeInfo(
                                path=current_path,
                                branch_name=current_branch,
                                base_branch="",  # Not easily available
                                created_at=datetime.utcnow(),  # Not easily available
                            ))
                        current_path = None
                        current_branch = None

            except git.GitCommandError:
                pass

            return worktrees

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list)

    async def get_worktree_changes(self, worktree_path: Path) -> tuple[str, list[str]]:
        """Get the diff and list of changed files in a worktree.

        Args:
            worktree_path: Path to the worktree.

        Returns:
            Tuple of (unified diff string, list of changed file paths).
        """
        def _get_changes():
            repo = git.Repo(worktree_path)

            # Get list of changed files
            changed_files = []

            # Untracked files
            for item in repo.untracked_files:
                changed_files.append(item)

            # Modified and deleted files
            for item in repo.index.diff(None):
                changed_files.append(item.a_path)

            # Staged files
            for item in repo.index.diff("HEAD"):
                if item.a_path not in changed_files:
                    changed_files.append(item.a_path)

            # Generate diff
            # First, stage all changes
            repo.git.add("-A")

            # Get diff against HEAD
            try:
                diff = repo.git.diff("HEAD", "--cached")
            except git.GitCommandError:
                diff = ""

            return diff, changed_files

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_changes)

    async def commit_changes(
        self,
        worktree_path: Path,
        message: str,
    ) -> str:
        """Commit all changes in the worktree.

        Args:
            worktree_path: Path to the worktree.
            message: Commit message.

        Returns:
            Commit SHA.
        """
        def _commit():
            repo = git.Repo(worktree_path)
            repo.git.add("-A")
            repo.index.commit(message)
            return repo.head.commit.hexsha

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _commit)
