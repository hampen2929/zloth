"""Git operations service for centralized git management.

This service consolidates all git operations that were previously scattered
across WorktreeService and PRService, following the orchestrator management
pattern defined in docs/git_operation_design.md.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
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


@dataclass
class GitStatus:
    """Status of a git working directory."""

    staged: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    untracked: list[str] = field(default_factory=list)
    deleted: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.staged or self.modified or self.untracked or self.deleted)


class GitService:
    """Service for centralized git operation management.

    This service handles all git operations in dursor, ensuring consistent
    behavior across different execution flows. AI Agents should only edit
    files, while dursor manages all git operations through this service.
    """

    def __init__(self, workspaces_dir: Path | None = None):
        """Initialize GitService.

        Args:
            workspaces_dir: Base directory for workspaces. Defaults to settings.
        """
        self.workspaces_dir = workspaces_dir or settings.workspaces_dir
        self.worktrees_dir = self.workspaces_dir / "worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    # ============================================================
    # Worktree Management
    # ============================================================

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
                source_repo.git.checkout(base_branch)
            except git.GitCommandError:
                try:
                    source_repo.git.checkout("-b", base_branch, f"origin/{base_branch}")
                except git.GitCommandError:
                    pass

            # Create worktree with new branch
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

    async def cleanup_worktree(
        self,
        worktree_path: Path,
        delete_branch: bool = False,
    ) -> None:
        """Remove a worktree after PR creation or run cancellation.

        Args:
            worktree_path: Path to the worktree to remove.
            delete_branch: Whether to also delete the local branch.
        """
        def _cleanup():
            if not worktree_path.exists():
                return

            git_file = worktree_path / ".git"
            if git_file.exists():
                with open(git_file) as f:
                    content = f.read().strip()
                    if content.startswith("gitdir: "):
                        gitdir = content[8:]
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
                                shutil.rmtree(worktree_path, ignore_errors=True)

                            # Optionally delete the branch
                            if delete_branch and branch_name:
                                try:
                                    parent_repo.git.branch("-D", branch_name)
                                except git.GitCommandError:
                                    pass
                            return

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
                        if str(current_path).startswith(str(self.worktrees_dir)):
                            worktrees.append(WorktreeInfo(
                                path=current_path,
                                branch_name=current_branch,
                                base_branch="",
                                created_at=datetime.utcnow(),
                            ))
                        current_path = None
                        current_branch = None

            except git.GitCommandError:
                pass

            return worktrees

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list)

    async def is_valid_worktree(self, worktree_path: Path) -> bool:
        """Check if a path is a valid git worktree.

        This verifies that:
        1. The directory exists
        2. It's a valid git repository (worktree)
        3. Git commands can be executed in it

        Args:
            worktree_path: Path to check.

        Returns:
            True if valid, False otherwise.
        """
        def _check():
            if not worktree_path.exists():
                return False

            try:
                # Try to open as a git repo - this will fail if .git reference is broken
                repo = git.Repo(worktree_path)
                # Try a simple git command to verify it works
                repo.git.status()
                return True
            except (git.InvalidGitRepositoryError, git.GitCommandError):
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    # ============================================================
    # Change Management
    # ============================================================

    async def get_status(self, worktree_path: Path) -> GitStatus:
        """Get working directory status.

        Args:
            worktree_path: Path to the worktree.

        Returns:
            GitStatus with staged, modified, untracked, and deleted files.
        """
        def _get_status():
            repo = git.Repo(worktree_path)
            status = GitStatus()

            # Untracked files
            status.untracked = list(repo.untracked_files)

            # Modified and deleted (unstaged)
            for item in repo.index.diff(None):
                if item.deleted_file:
                    status.deleted.append(item.a_path)
                else:
                    status.modified.append(item.a_path)

            # Staged files
            try:
                for item in repo.index.diff("HEAD"):
                    status.staged.append(item.a_path)
            except git.GitCommandError:
                # No HEAD commit yet
                pass

            return status

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_status)

    async def stage_all(self, worktree_path: Path) -> None:
        """Stage all changes.

        Args:
            worktree_path: Path to the worktree.
        """
        def _stage_all():
            repo = git.Repo(worktree_path)
            repo.git.add("-A")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stage_all)

    async def unstage_all(self, worktree_path: Path) -> None:
        """Unstage all changes.

        Args:
            worktree_path: Path to the worktree.
        """
        def _unstage_all():
            repo = git.Repo(worktree_path)
            try:
                repo.git.reset("HEAD")
            except git.GitCommandError:
                # No HEAD commit yet
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _unstage_all)

    async def get_diff(self, worktree_path: Path, staged: bool = True) -> str:
        """Get diff.

        Args:
            worktree_path: Path to the worktree.
            staged: If True, get staged diff; otherwise get unstaged diff.

        Returns:
            Unified diff string.
        """
        def _get_diff():
            repo = git.Repo(worktree_path)
            try:
                if staged:
                    return repo.git.diff("HEAD", "--cached")
                else:
                    return repo.git.diff()
            except git.GitCommandError:
                return ""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_diff)

    async def get_diff_from_base(
        self,
        worktree_path: Path,
        base_ref: str,
    ) -> str:
        """Get cumulative diff from base branch.

        Args:
            worktree_path: Path to the worktree.
            base_ref: Base branch/commit reference.

        Returns:
            Unified diff string.
        """
        def _get_diff_from_base():
            repo = git.Repo(worktree_path)
            try:
                # Get diff from merge-base to HEAD
                merge_base = repo.git.merge_base(base_ref, "HEAD")
                return repo.git.diff(merge_base, "HEAD")
            except git.GitCommandError:
                # Fallback to simple diff
                try:
                    return repo.git.diff(base_ref, "HEAD")
                except git.GitCommandError:
                    return ""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_diff_from_base)

    async def reset_changes(
        self,
        worktree_path: Path,
        hard: bool = False,
    ) -> None:
        """Reset changes.

        Args:
            worktree_path: Path to the worktree.
            hard: If True, discard all changes; otherwise only unstage.
        """
        def _reset():
            repo = git.Repo(worktree_path)
            if hard:
                repo.git.reset("--hard", "HEAD")
                repo.git.clean("-fd")
            else:
                repo.git.reset("HEAD")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _reset)

    # ============================================================
    # Commit Management
    # ============================================================

    async def commit(
        self,
        worktree_path: Path,
        message: str,
    ) -> str:
        """Create a commit.

        Args:
            worktree_path: Path to the worktree.
            message: Commit message.

        Returns:
            Commit SHA.
        """
        def _commit():
            repo = git.Repo(worktree_path)
            repo.index.commit(message)
            return repo.head.commit.hexsha

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _commit)

    async def amend(
        self,
        worktree_path: Path,
        message: str | None = None,
    ) -> str:
        """Amend the last commit.

        Args:
            worktree_path: Path to the worktree.
            message: New commit message. If None, keeps the old message.

        Returns:
            New commit SHA.
        """
        def _amend():
            repo = git.Repo(worktree_path)
            if message:
                repo.git.commit("--amend", "-m", message)
            else:
                repo.git.commit("--amend", "--no-edit")
            return repo.head.commit.hexsha

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _amend)

    # ============================================================
    # Branch Management
    # ============================================================

    async def create_branch(
        self,
        repo_path: Path,
        branch_name: str,
        base: str,
    ) -> None:
        """Create a branch.

        Args:
            repo_path: Path to the repository.
            branch_name: Name of the new branch.
            base: Base branch/commit to create from.
        """
        def _create_branch():
            repo = git.Repo(repo_path)
            repo.git.checkout("-b", branch_name, base)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _create_branch)

    async def checkout(self, repo_path: Path, branch_name: str) -> None:
        """Checkout a branch.

        Args:
            repo_path: Path to the repository.
            branch_name: Branch name to checkout.
        """
        def _checkout():
            repo = git.Repo(repo_path)
            repo.git.checkout(branch_name)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _checkout)

    async def delete_branch(
        self,
        repo_path: Path,
        branch_name: str,
        force: bool = False,
    ) -> None:
        """Delete a branch.

        Args:
            repo_path: Path to the repository.
            branch_name: Branch name to delete.
            force: If True, force delete even if not merged.
        """
        def _delete_branch():
            repo = git.Repo(repo_path)
            flag = "-D" if force else "-d"
            repo.git.branch(flag, branch_name)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _delete_branch)

    # ============================================================
    # Remote Operations
    # ============================================================

    async def push(
        self,
        repo_path: Path,
        branch: str,
        auth_url: str | None = None,
        force: bool = False,
    ) -> None:
        """Push to remote.

        Args:
            repo_path: Path to the repository.
            branch: Branch name to push.
            auth_url: Authenticated URL for push (e.g., with token).
            force: If True, force push.
        """
        def _push():
            repo = git.Repo(repo_path)

            if auth_url:
                # Use authenticated URL temporarily
                with repo.config_writer() as config:
                    # Save original URL
                    try:
                        original_url = repo.remotes.origin.url
                    except Exception:
                        original_url = None

                try:
                    # Set authenticated URL
                    repo.remotes.origin.set_url(auth_url)

                    # Push
                    push_args = ["-u", "origin", branch]
                    if force:
                        push_args.insert(0, "--force")
                    repo.git.push(*push_args)
                finally:
                    # Restore original URL
                    if original_url:
                        repo.remotes.origin.set_url(original_url)
            else:
                push_args = ["-u", "origin", branch]
                if force:
                    push_args.insert(0, "--force")
                repo.git.push(*push_args)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _push)

    async def fetch(
        self,
        repo_path: Path,
        remote: str = "origin",
    ) -> None:
        """Fetch from remote.

        Args:
            repo_path: Path to the repository.
            remote: Remote name.
        """
        def _fetch():
            repo = git.Repo(repo_path)
            repo.remotes[remote].fetch()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _fetch)

    async def delete_remote_branch(
        self,
        repo_path: Path,
        branch: str,
        auth_url: str | None = None,
    ) -> None:
        """Delete remote branch.

        Args:
            repo_path: Path to the repository.
            branch: Branch name to delete.
            auth_url: Authenticated URL for push (e.g., with token).
        """
        def _delete_remote_branch():
            repo = git.Repo(repo_path)

            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                except Exception:
                    original_url = None

                try:
                    repo.remotes.origin.set_url(auth_url)
                    repo.git.push("origin", "--delete", branch)
                finally:
                    if original_url:
                        repo.remotes.origin.set_url(original_url)
            else:
                repo.git.push("origin", "--delete", branch)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _delete_remote_branch)

    # ============================================================
    # Reset Operations
    # ============================================================

    async def reset_to_previous(
        self,
        repo_path: Path,
        soft: bool = False,
    ) -> None:
        """Reset to previous commit.

        Args:
            repo_path: Path to the repository.
            soft: If True, keep changes staged.
        """
        def _reset_to_previous():
            repo = git.Repo(repo_path)
            mode = "--soft" if soft else "--mixed"
            repo.git.reset(mode, "HEAD~1")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _reset_to_previous)

    # ============================================================
    # Utility Methods
    # ============================================================

    async def get_current_branch(self, repo_path: Path) -> str:
        """Get the current branch name.

        Args:
            repo_path: Path to the repository.

        Returns:
            Current branch name.
        """
        def _get_current_branch():
            repo = git.Repo(repo_path)
            return repo.active_branch.name

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_current_branch)

    async def get_head_sha(self, repo_path: Path) -> str:
        """Get the current HEAD commit SHA.

        Args:
            repo_path: Path to the repository.

        Returns:
            HEAD commit SHA.
        """
        def _get_head_sha():
            repo = git.Repo(repo_path)
            return repo.head.commit.hexsha

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_head_sha)

    async def get_changed_files(self, worktree_path: Path) -> list[str]:
        """Get list of changed files in a worktree.

        Args:
            worktree_path: Path to the worktree.

        Returns:
            List of changed file paths.
        """
        def _get_changed_files():
            repo = git.Repo(worktree_path)
            changed_files = []

            # Untracked files
            changed_files.extend(repo.untracked_files)

            # Modified and deleted files
            for item in repo.index.diff(None):
                if item.a_path not in changed_files:
                    changed_files.append(item.a_path)

            # Staged files
            try:
                for item in repo.index.diff("HEAD"):
                    if item.a_path not in changed_files:
                        changed_files.append(item.a_path)
            except git.GitCommandError:
                pass

            return changed_files

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_changed_files)
