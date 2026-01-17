"""Git operations service for centralized git management.

This service consolidates all git operations that were previously scattered
across WorktreeService and PRService, following the orchestrator management
pattern defined in docs/git_operation_design.md.
"""

from __future__ import annotations

import asyncio
import logging
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import git

from tazuna_api.config import settings
from tazuna_api.domain.models import Repo

logger = logging.getLogger(__name__)


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


@dataclass
class PullResult:
    """Result of a git pull operation."""

    success: bool
    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class PushResult:
    """Result of a git push operation."""

    success: bool
    error: str | None = None
    required_pull: bool = False  # True if we had to pull before push succeeded


class GitService:
    """Service for centralized git operation management.

    This service handles all git operations in dursor, ensuring consistent
    behavior across different execution flows. AI Agents should only edit
    files, while dursor manages all git operations through this service.
    """

    def __init__(
        self,
        workspaces_dir: Path | None = None,
        worktrees_dir: Path | None = None,
    ):
        """Initialize GitService.

        Args:
            workspaces_dir: Base directory for workspaces. Defaults to settings.
            worktrees_dir: Base directory for worktrees. Defaults to settings.
                           Separate from workspaces_dir to avoid inheriting
                           parent directory's CLAUDE.md when CLI agents run.
        """
        if workspaces_dir:
            self.workspaces_dir = workspaces_dir
        elif settings.workspaces_dir:
            self.workspaces_dir = settings.workspaces_dir
        else:
            raise ValueError("workspaces_dir must be provided or set in settings")

        if worktrees_dir:
            self.worktrees_dir = worktrees_dir
        elif settings.worktrees_dir:
            self.worktrees_dir = settings.worktrees_dir
        else:
            # Fallback to old behavior if not configured
            self.worktrees_dir = self.workspaces_dir / "worktrees"
        self.worktrees_dir.mkdir(parents=True, exist_ok=True)

    def set_worktrees_dir(self, worktrees_dir: str | Path | None) -> None:
        """Update the worktrees directory.

        This allows dynamic configuration from UserPreferences.

        Args:
            worktrees_dir: New worktrees directory path. If None or empty, keeps current value.
        """
        if not worktrees_dir:
            return

        new_path = Path(worktrees_dir).expanduser()
        if new_path != self.worktrees_dir:
            self.worktrees_dir = new_path
            self.worktrees_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Updated worktrees_dir to: {self.worktrees_dir}")

    # ============================================================
    # Worktree Management
    # ============================================================

    def _normalize_branch_prefix(self, prefix: str | None) -> str:
        """Normalize a user-provided branch prefix.

        Rules:
        - If empty/None after trimming -> 'dursor'
        - Trim whitespace
        - Strip leading/trailing slashes
        - Collapse whitespace runs into '-'
        """
        if prefix is None:
            return "dursor"
        cleaned = prefix.strip()
        if not cleaned:
            return "dursor"
        cleaned = re.sub(r"\s+", "-", cleaned)
        cleaned = cleaned.strip("/")
        return cleaned or "dursor"

    def _generate_branch_name(self, run_id: str, branch_prefix: str | None = None) -> str:
        """Generate a unique branch name for a run.

        Args:
            run_id: Run ID.
            branch_prefix: Optional branch prefix (defaults to 'dursor').

        Returns:
            Branch name in format: <prefix>/{short_id}
        """
        prefix = self._normalize_branch_prefix(branch_prefix)
        short_id = run_id[:8]
        return f"{prefix}/{short_id}"

    async def create_worktree(
        self,
        repo: Repo,
        base_branch: str,
        run_id: str,
        branch_prefix: str | None = None,
    ) -> WorktreeInfo:
        """Create a new git worktree for the run.

        Args:
            repo: Repository object with workspace_path.
            base_branch: Base branch to create worktree from.
            run_id: Run ID for naming.
            branch_prefix: Optional branch prefix for the new work branch.

        Returns:
            WorktreeInfo with path and branch information.

        Raises:
            git.GitCommandError: If git worktree creation fails.
        """
        branch_name = self._generate_branch_name(run_id, branch_prefix=branch_prefix)
        worktree_path = self.worktrees_dir / f"run_{run_id}"

        def _create_worktree() -> WorktreeInfo:
            source_repo = git.Repo(repo.workspace_path)

            default_branch = repo.default_branch or "main"

            # Fetch to ensure we have latest refs (best-effort)
            try:
                source_repo.git.fetch("origin", "--prune")
            except Exception:
                # Ignore fetch errors (might be offline)
                pass

            # Ensure the *source* repo is at the latest state of the default branch
            # before creating a worktree.
            try:
                # Verify the remote default branch exists
                source_repo.git.show_ref("--verify", f"refs/remotes/origin/{default_branch}")
                # Force local default branch to match origin/default (latest)
                source_repo.git.checkout("-B", default_branch, f"origin/{default_branch}")
            except git.GitCommandError:
                # Fallback: try best-effort checkout without forcing reset
                try:
                    source_repo.git.checkout(default_branch)
                except git.GitCommandError:
                    pass

            # Choose a base ref for the worktree.
            # Prefer remote refs to ensure we branch from the latest remote state.
            base_ref = base_branch
            try:
                source_repo.git.show_ref("--verify", f"refs/remotes/origin/{base_branch}")
                base_ref = f"origin/{base_branch}"
            except git.GitCommandError:
                # If base_branch isn't a remote branch, keep it as-is (could be SHA/tag).
                base_ref = base_branch

            # Create worktree with new branch
            source_repo.git.worktree(
                "add",
                "-b",
                branch_name,
                str(worktree_path),
                base_ref,
            )

            return WorktreeInfo(
                path=worktree_path,
                branch_name=branch_name,
                base_branch=base_branch,
                created_at=datetime.utcnow(),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create_worktree)

    async def is_ancestor(self, repo_path: Path, ancestor: str, descendant: str = "HEAD") -> bool:
        """Check whether `ancestor` is an ancestor of `descendant`.

        This is a thin wrapper around `git merge-base --is-ancestor`.

        Args:
            repo_path: Path to a git repo (workspace or worktree).
            ancestor: Git ref expected to be an ancestor (e.g., 'origin/main').
            descendant: Git ref expected to include the ancestor (default: 'HEAD').

        Returns:
            True if ancestor is an ancestor of descendant, False otherwise.
        """

        def _is_ancestor() -> bool:
            repo = git.Repo(repo_path)

            # Best-effort fetch to update origin refs (works for worktrees too).
            try:
                repo.git.fetch("origin", "--prune")
            except Exception:
                pass

            # If the ancestor ref doesn't exist, we cannot reliably decide.
            try:
                repo.git.show_ref("--verify", f"refs/{ancestor}")
            except git.GitCommandError:
                try:
                    repo.git.show_ref("--verify", f"refs/remotes/{ancestor}")
                except git.GitCommandError:
                    return True

            try:
                repo.git.merge_base("--is-ancestor", ancestor, descendant)
                return True
            except git.GitCommandError:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _is_ancestor)

    async def get_ref_sha(self, repo_path: Path, ref: str) -> str | None:
        """Resolve a git ref to a SHA (best-effort).

        Args:
            repo_path: Path to a git repo (workspace or worktree).
            ref: Git ref to resolve (e.g., 'origin/main', 'HEAD', 'refs/remotes/origin/main').

        Returns:
            SHA string if resolvable, otherwise None.
        """

        def _get_ref_sha() -> str | None:
            repo = git.Repo(repo_path)
            try:
                # Best-effort fetch to keep origin refs fresh.
                repo.git.fetch("origin", "--prune")
            except Exception as e:
                logger.debug(f"git fetch failed while resolving ref: {e}")

            try:
                return repo.git.rev_parse(ref).strip()
            except git.GitCommandError:
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_ref_sha)

    async def get_merge_base(self, repo_path: Path, ref1: str, ref2: str) -> str | None:
        """Get merge-base SHA between two refs (best-effort).

        Args:
            repo_path: Path to a git repo (workspace or worktree).
            ref1: First ref (e.g., 'origin/main').
            ref2: Second ref (e.g., 'origin/feature' or 'HEAD').

        Returns:
            Merge-base SHA if computable, otherwise None.
        """

        def _get_merge_base() -> str | None:
            repo = git.Repo(repo_path)
            try:
                repo.git.fetch("origin", "--prune")
            except Exception as e:
                logger.debug(f"git fetch failed while computing merge-base: {e}")

            try:
                mb = repo.git.merge_base(ref1, ref2).strip()
                return mb.splitlines()[0].strip() if mb else None
            except git.GitCommandError:
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_merge_base)

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

        def _cleanup() -> None:
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

        def _list() -> list[WorktreeInfo]:
            source_repo = git.Repo(repo.workspace_path)
            worktrees: list[WorktreeInfo] = []

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
                            worktrees.append(
                                WorktreeInfo(
                                    path=current_path,
                                    branch_name=current_branch,
                                    base_branch="",
                                    created_at=datetime.utcnow(),
                                )
                            )
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

        def _check() -> bool:
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

        def _get_status() -> GitStatus:
            repo = git.Repo(worktree_path)
            status = GitStatus()

            # Untracked files
            status.untracked = list(repo.untracked_files)

            # Modified and deleted (unstaged)
            for item in repo.index.diff(None):
                if item.a_path:
                    if item.deleted_file:
                        status.deleted.append(item.a_path)
                    else:
                        status.modified.append(item.a_path)

            # Staged files
            try:
                for item in repo.index.diff("HEAD"):
                    if item.a_path:
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

        def _stage_all() -> None:
            repo = git.Repo(worktree_path)
            repo.git.add("-A")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stage_all)

    async def unstage_all(self, worktree_path: Path) -> None:
        """Unstage all changes.

        Args:
            worktree_path: Path to the worktree.
        """

        def _unstage_all() -> None:
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

        def _get_diff() -> str:
            repo = git.Repo(worktree_path)
            try:
                if staged:
                    return str(repo.git.diff("HEAD", "--cached"))
                else:
                    return str(repo.git.diff())
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

        def _get_diff_from_base() -> str:
            repo = git.Repo(worktree_path)
            try:
                # Get diff from merge-base to HEAD
                merge_base = repo.git.merge_base(base_ref, "HEAD")
                return str(repo.git.diff(merge_base, "HEAD"))
            except git.GitCommandError:
                # Fallback to simple diff
                try:
                    return str(repo.git.diff(base_ref, "HEAD"))
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

        def _reset() -> None:
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

        def _commit() -> str:
            repo = git.Repo(worktree_path)
            repo.index.commit(message)
            return str(repo.head.commit.hexsha)

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

        def _amend() -> str:
            repo = git.Repo(worktree_path)
            if message:
                repo.git.commit("--amend", "-m", message)
            else:
                repo.git.commit("--amend", "--no-edit")
            return str(repo.head.commit.hexsha)

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

        def _create_branch() -> None:
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

        def _checkout() -> None:
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

        def _delete_branch() -> None:
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

        def _push() -> None:
            repo = git.Repo(repo_path)

            if auth_url:
                # Use authenticated URL temporarily
                with repo.config_writer():
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

    async def push_with_retry(
        self,
        repo_path: Path,
        branch: str,
        auth_url: str | None = None,
        max_retries: int = 2,
    ) -> PushResult:
        """Push to remote with automatic retry on non-fast-forward errors.

        If push fails because remote has new commits (non-fast-forward),
        this method will fetch, pull, and retry the push.

        Args:
            repo_path: Path to the repository.
            branch: Branch name to push.
            auth_url: Authenticated URL for push.
            max_retries: Maximum number of retry attempts.

        Returns:
            PushResult with success status and details.
        """
        required_pull = False

        for attempt in range(max_retries + 1):
            try:
                await self.push(repo_path, branch=branch, auth_url=auth_url)
                return PushResult(success=True, required_pull=required_pull)
            except Exception as e:
                error_str = str(e).lower()

                # Check if this is a non-fast-forward error
                is_non_ff = any(
                    pattern in error_str
                    for pattern in [
                        "non-fast-forward",
                        "[rejected]",
                        "failed to push some refs",
                        "updates were rejected",
                        "fetch first",
                    ]
                )

                if not is_non_ff or attempt >= max_retries:
                    return PushResult(success=False, error=str(e), required_pull=required_pull)

                # Try to pull and retry
                logger.info(
                    f"Push rejected (non-fast-forward), pulling and retrying "
                    f"(attempt {attempt + 1}/{max_retries})"
                )

                pull_result = await self.pull(repo_path, branch=branch, auth_url=auth_url)
                required_pull = True

                if not pull_result.success:
                    if pull_result.has_conflicts:
                        return PushResult(
                            success=False,
                            error=f"Merge conflicts in: {', '.join(pull_result.conflict_files)}",
                            required_pull=True,
                        )
                    return PushResult(
                        success=False,
                        error=f"Pull failed: {pull_result.error}",
                        required_pull=True,
                    )

        return PushResult(success=False, error="Max retries exceeded", required_pull=required_pull)

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

        def _fetch() -> None:
            repo = git.Repo(repo_path)
            repo.remotes[remote].fetch()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _fetch)

    async def fetch_with_auth(
        self,
        repo_path: Path,
        auth_url: str | None = None,
        remote: str = "origin",
    ) -> None:
        """Fetch from remote with authentication support.

        Args:
            repo_path: Path to the repository.
            auth_url: Authenticated URL for private repos.
            remote: Remote name.
        """

        def _fetch_with_auth() -> None:
            repo = git.Repo(repo_path)

            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                except Exception:
                    original_url = None

                try:
                    repo.remotes.origin.set_url(auth_url)
                    repo.remotes[remote].fetch()
                finally:
                    if original_url:
                        repo.remotes.origin.set_url(original_url)
            else:
                repo.remotes[remote].fetch()

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _fetch_with_auth)

    async def is_behind_remote(
        self,
        repo_path: Path,
        branch: str,
        auth_url: str | None = None,
    ) -> bool:
        """Check if local branch is behind its remote tracking branch.

        This fetches the latest state from remote and checks if there are
        commits on origin/<branch> that are not in the local HEAD.

        Args:
            repo_path: Path to the repository (workspace or worktree).
            branch: Branch name to check.
            auth_url: Authenticated URL for private repos.

        Returns:
            True if origin/<branch> has commits not in local HEAD.
        """
        # Fetch latest state from remote
        await self.fetch_with_auth(repo_path, auth_url=auth_url)

        def _is_behind() -> bool:
            repo = git.Repo(repo_path)
            remote_ref = f"origin/{branch}"

            # Check if remote ref exists
            try:
                repo.git.show_ref("--verify", f"refs/remotes/{remote_ref}")
            except git.GitCommandError:
                # Remote ref doesn't exist, not behind
                return False

            # Get local HEAD SHA and remote ref SHA
            try:
                local_sha = repo.git.rev_parse("HEAD").strip()
                remote_sha = repo.git.rev_parse(remote_ref).strip()
            except git.GitCommandError:
                return False

            if local_sha == remote_sha:
                return False

            # Check if remote is ahead of local (local is behind)
            # If remote_sha is NOT an ancestor of local_sha, then local is behind
            try:
                repo.git.merge_base("--is-ancestor", remote_sha, local_sha)
                # remote_sha IS an ancestor of local_sha, so local is NOT behind
                return False
            except git.GitCommandError:
                # remote_sha is NOT an ancestor, so local is behind (or diverged)
                return True

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _is_behind)

    async def pull(
        self,
        repo_path: Path,
        branch: str | None = None,
        auth_url: str | None = None,
    ) -> PullResult:
        """Pull from remote with conflict detection.

        This method pulls the latest changes from the remote tracking branch.
        If conflicts occur, they are left in the working directory for resolution.

        Args:
            repo_path: Path to the repository.
            branch: Branch to pull (defaults to current branch's upstream).
            auth_url: Authenticated URL for private repos.

        Returns:
            PullResult with success status and conflict information.
        """

        def _pull() -> PullResult:
            repo = git.Repo(repo_path)

            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                except Exception:
                    original_url = None
            else:
                original_url = None

            try:
                if auth_url:
                    repo.remotes.origin.set_url(auth_url)

                # Determine the branch to pull
                pull_branch = branch or repo.active_branch.name

                try:
                    # Try to pull
                    repo.git.pull("origin", pull_branch)
                    return PullResult(success=True)
                except git.GitCommandError as e:
                    error_str = str(e)

                    # Check for merge conflicts
                    if "CONFLICT" in error_str or "Automatic merge failed" in error_str:
                        # Get list of conflicted files
                        conflict_files: list[str] = []
                        try:
                            # Get unmerged files
                            unmerged = repo.git.diff("--name-only", "--diff-filter=U")
                            if unmerged:
                                conflict_files = unmerged.strip().split("\n")
                        except Exception:
                            pass

                        return PullResult(
                            success=False,
                            has_conflicts=True,
                            conflict_files=conflict_files,
                            error="Merge conflicts detected",
                        )

                    return PullResult(success=False, error=str(e))

            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _pull)

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

        def _delete_remote_branch() -> None:
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

        def _reset_to_previous() -> None:
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

        def _get_current_branch() -> str:
            repo = git.Repo(repo_path)
            return str(repo.active_branch.name)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_current_branch)

    async def get_head_sha(self, repo_path: Path) -> str:
        """Get the current HEAD commit SHA.

        Args:
            repo_path: Path to the repository.

        Returns:
            HEAD commit SHA.
        """

        def _get_head_sha() -> str:
            repo = git.Repo(repo_path)
            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_head_sha)

    async def get_changed_files(self, worktree_path: Path) -> list[str]:
        """Get list of changed files in a worktree.

        Args:
            worktree_path: Path to the worktree.

        Returns:
            List of changed file paths.
        """

        def _get_changed_files() -> list[str]:
            repo = git.Repo(worktree_path)
            changed_files: list[str] = []

            # Untracked files
            changed_files.extend(repo.untracked_files)

            # Modified and deleted files
            for item in repo.index.diff(None):
                if item.a_path and item.a_path not in changed_files:
                    changed_files.append(item.a_path)

            # Staged files
            try:
                for item in repo.index.diff("HEAD"):
                    if item.a_path and item.a_path not in changed_files:
                        changed_files.append(item.a_path)
            except git.GitCommandError:
                pass

            return changed_files

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_changed_files)
