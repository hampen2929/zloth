"""Workspace management service using git clone for isolation.

This service provides workspace isolation via shallow git clones, which offers
better support for remote synchronization and conflict resolution compared to
git worktrees.

Key features:
- Shallow clone for fast initial setup
- Unshallow on demand for conflict resolution
- Full git operation support (fetch, pull, merge, rebase)
- Workspace reuse for conversation continuity
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
class WorkspaceInfo:
    """Information about a workspace (cloned repository)."""

    path: Path
    branch_name: str
    base_branch: str
    created_at: datetime
    is_shallow: bool = True


@dataclass
class SyncResult:
    """Result of syncing workspace with remote."""

    success: bool
    was_behind: bool = False
    commits_pulled: int = 0
    error: str | None = None


@dataclass
class ConflictInfo:
    """Information about merge conflicts."""

    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)
    base_branch: str = ""
    merge_head: str = ""


@dataclass
class MergeResult:
    """Result of merging base branch into workspace."""

    success: bool
    conflict_info: ConflictInfo | None = None
    error: str | None = None


class WorkspaceService:
    """Service for managing isolated workspaces via git clone.

    This service provides workspace isolation that supports full git operations,
    enabling remote sync and conflict resolution that are difficult with worktrees.
    """

    def __init__(
        self,
        workspaces_dir: Path | None = None,
    ):
        """Initialize WorkspaceService.

        Args:
            workspaces_dir: Base directory for workspaces. Defaults to settings.
        """
        if workspaces_dir:
            self.workspaces_dir = workspaces_dir
        elif settings.worktrees_dir:
            # Reuse worktrees_dir setting for backward compatibility
            self.workspaces_dir = settings.worktrees_dir
        else:
            self.workspaces_dir = Path.home() / ".tazuna" / "workspaces"
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    def set_workspaces_dir(self, workspaces_dir: str | Path | None) -> None:
        """Update the workspaces directory.

        Args:
            workspaces_dir: New workspaces directory path.
        """
        if not workspaces_dir:
            return

        new_path = Path(workspaces_dir).expanduser()
        if new_path != self.workspaces_dir:
            self.workspaces_dir = new_path
            self.workspaces_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Updated workspaces_dir to: {self.workspaces_dir}")

    def _normalize_branch_prefix(self, prefix: str | None) -> str:
        """Normalize a user-provided branch prefix."""
        if prefix is None:
            return "tazuna"
        cleaned = prefix.strip()
        if not cleaned:
            return "tazuna"
        cleaned = re.sub(r"\s+", "-", cleaned)
        cleaned = cleaned.strip("/")
        return cleaned or "tazuna"

    def _generate_branch_name(self, run_id: str, branch_prefix: str | None = None) -> str:
        """Generate a unique branch name for a run."""
        prefix = self._normalize_branch_prefix(branch_prefix)
        short_id = run_id[:8]
        return f"{prefix}/{short_id}"

    # ============================================================
    # Workspace Creation
    # ============================================================

    async def create_workspace(
        self,
        repo: Repo,
        base_branch: str,
        run_id: str,
        branch_prefix: str | None = None,
        auth_url: str | None = None,
        shallow: bool = True,
    ) -> WorkspaceInfo:
        """Create a new isolated workspace via git clone.

        Args:
            repo: Repository object with repo_url.
            base_branch: Base branch to clone and branch from.
            run_id: Run ID for naming.
            branch_prefix: Optional branch prefix for the new work branch.
            auth_url: Authenticated URL for private repos.
            shallow: If True, create a shallow clone (faster, less disk space).

        Returns:
            WorkspaceInfo with path and branch information.
        """
        branch_name = self._generate_branch_name(run_id, branch_prefix=branch_prefix)
        workspace_path = self.workspaces_dir / f"run_{run_id}"

        def _create_workspace() -> WorkspaceInfo:
            # Remove existing directory if any
            if workspace_path.exists():
                shutil.rmtree(workspace_path)

            clone_url = auth_url or repo.repo_url

            # Clone with shallow option
            clone_args = ["--single-branch", "-b", base_branch]
            if shallow:
                clone_args.extend(["--depth", "1"])

            logger.info(f"Cloning repository to {workspace_path} (shallow={shallow})")
            cloned_repo = git.Repo.clone_from(
                clone_url,
                workspace_path,
                multi_options=clone_args,
            )

            # If auth_url was used, reset remote URL to the original (non-auth) URL
            # This prevents credentials from being stored in the clone
            if auth_url and repo.repo_url:
                cloned_repo.remotes.origin.set_url(repo.repo_url)

            # Create new branch for work
            cloned_repo.git.checkout("-b", branch_name)

            logger.info(f"Created workspace at {workspace_path} on branch {branch_name}")

            return WorkspaceInfo(
                path=workspace_path,
                branch_name=branch_name,
                base_branch=base_branch,
                created_at=datetime.utcnow(),
                is_shallow=shallow,
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create_workspace)

    async def is_valid_workspace(self, workspace_path: Path) -> bool:
        """Check if a path is a valid git workspace.

        Args:
            workspace_path: Path to check.

        Returns:
            True if valid, False otherwise.
        """

        def _check() -> bool:
            if not workspace_path.exists():
                return False

            try:
                repo = git.Repo(workspace_path)
                repo.git.status()
                return True
            except (git.InvalidGitRepositoryError, git.GitCommandError):
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    async def cleanup_workspace(
        self,
        workspace_path: Path,
        delete_remote_branch: bool = False,
        auth_url: str | None = None,
    ) -> None:
        """Remove a workspace.

        Args:
            workspace_path: Path to the workspace to remove.
            delete_remote_branch: Whether to also delete the remote branch.
            auth_url: Authenticated URL for deleting remote branch.
        """

        def _cleanup() -> None:
            if not workspace_path.exists():
                return

            if delete_remote_branch:
                try:
                    repo = git.Repo(workspace_path)
                    branch_name = repo.active_branch.name

                    if auth_url:
                        repo.remotes.origin.set_url(auth_url)

                    try:
                        repo.git.push("origin", "--delete", branch_name)
                        logger.info(f"Deleted remote branch: {branch_name}")
                    except git.GitCommandError as e:
                        logger.warning(f"Failed to delete remote branch: {e}")
                except Exception as e:
                    logger.warning(f"Error during remote branch deletion: {e}")

            shutil.rmtree(workspace_path, ignore_errors=True)
            logger.info(f"Removed workspace: {workspace_path}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _cleanup)

    # ============================================================
    # Remote Synchronization
    # ============================================================

    async def sync_with_remote(
        self,
        workspace_path: Path,
        branch: str,
        auth_url: str | None = None,
    ) -> SyncResult:
        """Sync workspace with remote branch (fetch + pull).

        This handles the case where the PR branch was updated on GitHub
        (e.g., via "Update Branch" button) and we need to incorporate those changes.

        Args:
            workspace_path: Path to the workspace.
            branch: Branch name to sync.
            auth_url: Authenticated URL for private repos.

        Returns:
            SyncResult with sync status.
        """

        def _sync() -> SyncResult:
            repo = git.Repo(workspace_path)

            # Temporarily set auth URL if provided
            original_url = None
            if auth_url:
                original_url = repo.remotes.origin.url
                repo.remotes.origin.set_url(auth_url)

            try:
                # Fetch latest
                repo.git.fetch("origin", branch)

                # Check if we're behind
                local_sha = repo.git.rev_parse("HEAD").strip()
                try:
                    remote_sha = repo.git.rev_parse(f"origin/{branch}").strip()
                except git.GitCommandError:
                    # Remote branch doesn't exist yet
                    return SyncResult(success=True, was_behind=False)

                if local_sha == remote_sha:
                    return SyncResult(success=True, was_behind=False)

                # Check how many commits behind
                try:
                    behind_count = int(
                        repo.git.rev_list("--count", f"HEAD..origin/{branch}").strip()
                    )
                except git.GitCommandError:
                    behind_count = 0

                if behind_count == 0:
                    return SyncResult(success=True, was_behind=False)

                # Pull changes
                logger.info(f"Pulling {behind_count} commits from origin/{branch}")
                repo.git.pull("origin", branch)

                return SyncResult(
                    success=True,
                    was_behind=True,
                    commits_pulled=behind_count,
                )

            except git.GitCommandError as e:
                return SyncResult(success=False, error=str(e))

            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _sync)

    async def is_behind_remote(
        self,
        workspace_path: Path,
        branch: str,
        auth_url: str | None = None,
    ) -> bool:
        """Check if local branch is behind remote.

        Args:
            workspace_path: Path to the workspace.
            branch: Branch name to check.
            auth_url: Authenticated URL for private repos.

        Returns:
            True if remote has commits not in local HEAD.
        """

        def _is_behind() -> bool:
            repo = git.Repo(workspace_path)

            original_url = None
            if auth_url:
                original_url = repo.remotes.origin.url
                repo.remotes.origin.set_url(auth_url)

            try:
                repo.git.fetch("origin", branch)

                try:
                    repo.git.show_ref("--verify", f"refs/remotes/origin/{branch}")
                except git.GitCommandError:
                    return False

                local_sha = repo.git.rev_parse("HEAD").strip()
                remote_sha = repo.git.rev_parse(f"origin/{branch}").strip()

                if local_sha == remote_sha:
                    return False

                try:
                    repo.git.merge_base("--is-ancestor", remote_sha, local_sha)
                    return False
                except git.GitCommandError:
                    return True

            except git.GitCommandError:
                return False

            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _is_behind)

    # ============================================================
    # Conflict Resolution
    # ============================================================

    async def unshallow(
        self,
        workspace_path: Path,
        auth_url: str | None = None,
    ) -> bool:
        """Convert shallow clone to full clone.

        Required before merge/rebase operations that need full history.

        Args:
            workspace_path: Path to the workspace.
            auth_url: Authenticated URL for private repos.

        Returns:
            True if successful.
        """

        def _unshallow() -> bool:
            repo = git.Repo(workspace_path)

            # Check if already unshallowed
            shallow_file = Path(repo.git_dir) / "shallow"
            if not shallow_file.exists():
                logger.info("Workspace is already unshallowed")
                return True

            original_url = None
            if auth_url:
                original_url = repo.remotes.origin.url
                repo.remotes.origin.set_url(auth_url)

            try:
                logger.info(f"Unshallowing workspace at {workspace_path}")
                repo.git.fetch("--unshallow")
                return True
            except git.GitCommandError as e:
                logger.warning(f"Failed to unshallow: {e}")
                return False
            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _unshallow)

    async def merge_base_branch(
        self,
        workspace_path: Path,
        base_branch: str,
        auth_url: str | None = None,
    ) -> MergeResult:
        """Merge base branch into workspace to resolve conflicts.

        This fetches the latest base branch and attempts to merge it.
        If conflicts occur, the workspace is left in a conflicted state
        for AI to resolve.

        Args:
            workspace_path: Path to the workspace.
            base_branch: Base branch to merge (e.g., "main").
            auth_url: Authenticated URL for private repos.

        Returns:
            MergeResult with conflict information if any.
        """

        def _merge() -> MergeResult:
            repo = git.Repo(workspace_path)

            # Unshallow if needed (required for merge)
            shallow_file = Path(repo.git_dir) / "shallow"
            if shallow_file.exists():
                logger.info("Unshallowing before merge...")
                original_url = None
                if auth_url:
                    original_url = repo.remotes.origin.url
                    repo.remotes.origin.set_url(auth_url)

                try:
                    repo.git.fetch("--unshallow")
                except git.GitCommandError as e:
                    logger.warning(f"Unshallow failed: {e}")

                if original_url:
                    repo.remotes.origin.set_url(original_url)

            # Fetch latest base branch
            original_url = None
            if auth_url:
                original_url = repo.remotes.origin.url
                repo.remotes.origin.set_url(auth_url)

            try:
                logger.info(f"Fetching origin/{base_branch}")
                repo.git.fetch("origin", base_branch)
            except git.GitCommandError as e:
                return MergeResult(success=False, error=f"Fetch failed: {e}")
            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

            # Attempt merge
            try:
                logger.info(f"Merging origin/{base_branch}")
                repo.git.merge(f"origin/{base_branch}", "--no-edit")
                return MergeResult(success=True)

            except git.GitCommandError as e:
                error_str = str(e)

                # Check if this is a conflict
                if "CONFLICT" in error_str or "Automatic merge failed" in error_str:
                    # Get conflicted files
                    conflict_files: list[str] = []
                    try:
                        unmerged = repo.git.diff("--name-only", "--diff-filter=U")
                        if unmerged:
                            conflict_files = [f for f in unmerged.strip().split("\n") if f]
                    except Exception:
                        pass

                    # Get merge head for reference
                    try:
                        merge_head = repo.git.rev_parse(f"origin/{base_branch}").strip()[:8]
                    except Exception:
                        merge_head = ""

                    conflict_info = ConflictInfo(
                        has_conflicts=True,
                        conflict_files=conflict_files,
                        base_branch=base_branch,
                        merge_head=merge_head,
                    )

                    logger.warning(f"Merge conflicts detected in: {conflict_files}")
                    return MergeResult(success=False, conflict_info=conflict_info)

                return MergeResult(success=False, error=str(e))

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _merge)

    async def get_conflict_files(self, workspace_path: Path) -> list[str]:
        """Get list of files with merge conflicts.

        Args:
            workspace_path: Path to the workspace.

        Returns:
            List of file paths with conflicts.
        """

        def _get_conflicts() -> list[str]:
            repo = git.Repo(workspace_path)
            try:
                unmerged = repo.git.diff("--name-only", "--diff-filter=U")
                if unmerged:
                    return [f for f in unmerged.strip().split("\n") if f]
                return []
            except git.GitCommandError:
                return []

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_conflicts)

    async def complete_merge(
        self,
        workspace_path: Path,
        message: str | None = None,
    ) -> str:
        """Complete a merge after conflicts have been resolved.

        Args:
            workspace_path: Path to the workspace.
            message: Optional commit message.

        Returns:
            Commit SHA of the merge commit.
        """

        def _complete_merge() -> str:
            repo = git.Repo(workspace_path)

            # Stage all changes (including conflict resolutions)
            repo.git.add("-A")

            # Complete the merge
            if message:
                repo.git.commit("-m", message)
            else:
                repo.git.commit("--no-edit")

            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _complete_merge)

    async def abort_merge(self, workspace_path: Path) -> None:
        """Abort an in-progress merge.

        Args:
            workspace_path: Path to the workspace.
        """

        def _abort() -> None:
            repo = git.Repo(workspace_path)
            try:
                repo.git.merge("--abort")
            except git.GitCommandError:
                # May not be in merge state
                pass

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _abort)

    # ============================================================
    # Git Operations (delegated to workspace)
    # ============================================================

    async def stage_all(self, workspace_path: Path) -> None:
        """Stage all changes."""

        def _stage() -> None:
            repo = git.Repo(workspace_path)
            repo.git.add("-A")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stage)

    async def get_diff(self, workspace_path: Path, staged: bool = True) -> str:
        """Get diff."""

        def _get_diff() -> str:
            repo = git.Repo(workspace_path)
            try:
                if staged:
                    return str(repo.git.diff("HEAD", "--cached"))
                else:
                    return str(repo.git.diff())
            except git.GitCommandError:
                return ""

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_diff)

    async def commit(self, workspace_path: Path, message: str) -> str:
        """Create a commit."""

        def _commit() -> str:
            repo = git.Repo(workspace_path)
            repo.index.commit(message)
            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _commit)

    async def push(
        self,
        workspace_path: Path,
        branch: str,
        auth_url: str | None = None,
        force: bool = False,
    ) -> None:
        """Push to remote."""

        def _push() -> None:
            repo = git.Repo(workspace_path)

            original_url = None
            if auth_url:
                original_url = repo.remotes.origin.url
                repo.remotes.origin.set_url(auth_url)

            try:
                push_args = ["-u", "origin", branch]
                if force:
                    push_args.insert(0, "--force")
                repo.git.push(*push_args)
            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _push)

    async def get_current_branch(self, workspace_path: Path) -> str:
        """Get current branch name."""

        def _get_branch() -> str:
            repo = git.Repo(workspace_path)
            return str(repo.active_branch.name)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_branch)

    async def get_head_sha(self, workspace_path: Path) -> str:
        """Get HEAD commit SHA."""

        def _get_sha() -> str:
            repo = git.Repo(workspace_path)
            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_sha)

    # ============================================================
    # Workspace Lookup
    # ============================================================

    async def find_existing_workspace(
        self,
        run_id: str,
    ) -> WorkspaceInfo | None:
        """Find an existing workspace for a run.

        Args:
            run_id: Run ID to look for.

        Returns:
            WorkspaceInfo if found and valid, None otherwise.
        """
        workspace_path = self.workspaces_dir / f"run_{run_id}"

        if not await self.is_valid_workspace(workspace_path):
            return None

        def _get_info() -> WorkspaceInfo | None:
            try:
                repo = git.Repo(workspace_path)
                branch_name = repo.active_branch.name

                # Check if shallow
                shallow_file = Path(repo.git_dir) / "shallow"
                is_shallow = shallow_file.exists()

                # Try to determine base branch from tracking
                base_branch = "main"  # Default
                try:
                    tracking = repo.active_branch.tracking_branch()
                    if tracking:
                        base_branch = tracking.remote_head
                except Exception:
                    pass

                return WorkspaceInfo(
                    path=workspace_path,
                    branch_name=branch_name,
                    base_branch=base_branch,
                    created_at=datetime.utcnow(),  # Approximate
                    is_shallow=is_shallow,
                )
            except Exception:
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_info)

    async def list_workspaces(self) -> list[WorkspaceInfo]:
        """List all workspaces.

        Returns:
            List of WorkspaceInfo for all valid workspaces.
        """

        def _list() -> list[WorkspaceInfo]:
            workspaces: list[WorkspaceInfo] = []

            if not self.workspaces_dir.exists():
                return workspaces

            for item in self.workspaces_dir.iterdir():
                if not item.is_dir() or not item.name.startswith("run_"):
                    continue

                try:
                    repo = git.Repo(item)
                    branch_name = repo.active_branch.name

                    shallow_file = Path(repo.git_dir) / "shallow"
                    is_shallow = shallow_file.exists()

                    workspaces.append(
                        WorkspaceInfo(
                            path=item,
                            branch_name=branch_name,
                            base_branch="",
                            created_at=datetime.utcnow(),
                            is_shallow=is_shallow,
                        )
                    )
                except Exception:
                    continue

            return workspaces

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _list)
