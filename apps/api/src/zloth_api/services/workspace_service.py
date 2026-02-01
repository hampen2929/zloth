"""Workspace management service for clone-based isolation.

This service implements the Clone method for workspace isolation, which provides:
- Full git clone with shallow depth for efficiency
- Better support for remote sync (pull/push)
- Easier conflict resolution with standard git merge
- Independent from parent repository's worktree state

For legacy worktree-based isolation, see git_service.py.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import git

from zloth_api.config import settings

logger = logging.getLogger(__name__)


@dataclass
class WorkspaceInfo:
    """Information about a cloned workspace."""

    path: Path
    branch_name: str
    base_branch: str
    created_at: datetime


@dataclass
class MergeResult:
    """Result of a merge operation."""

    success: bool
    has_conflicts: bool = False
    conflict_files: list[str] = field(default_factory=list)
    error: str | None = None


class WorkspaceService:
    """Service for clone-based workspace isolation.

    This service manages workspaces using full git clones (with shallow depth)
    instead of worktrees. This approach provides:

    1. Better remote sync support (git pull works without issues)
    2. Easier conflict resolution (standard git merge workflow)
    3. Independence from parent repository state
    4. Compatible with authenticated fetch/push for private repos

    The trade-off is slightly more disk space and clone time compared to worktrees,
    but the operational benefits outweigh these costs for most use cases.
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
        elif settings.workspaces_dir:
            self.workspaces_dir = settings.workspaces_dir
        else:
            raise ValueError("workspaces_dir must be provided or set in settings")

        self.workspaces_dir.mkdir(parents=True, exist_ok=True)

    def set_workspaces_dir(self, workspaces_dir: str | Path | None) -> None:
        """Update the workspaces directory.

        This allows dynamic configuration from UserPreferences.

        Args:
            workspaces_dir: New workspaces directory path. If None or empty, keeps current value.
        """
        if not workspaces_dir:
            return

        new_path = Path(workspaces_dir).expanduser()
        if new_path != self.workspaces_dir:
            self.workspaces_dir = new_path
            self.workspaces_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Updated workspaces_dir to: {self.workspaces_dir}")

    def _generate_branch_name(self, run_id: str, branch_prefix: str | None = None) -> str:
        """Generate a unique branch name for a run.

        Args:
            run_id: Run ID.
            branch_prefix: Optional branch prefix (defaults to 'zloth').

        Returns:
            Branch name in format: <prefix>/{short_id}
        """
        prefix = branch_prefix.strip().strip("/") if branch_prefix else "zloth"
        if not prefix:
            prefix = "zloth"
        short_id = run_id[:8]
        return f"{prefix}/{short_id}"

    async def create_workspace(
        self,
        repo_url: str,
        base_branch: str,
        run_id: str,
        branch_prefix: str | None = None,
        auth_url: str | None = None,
    ) -> WorkspaceInfo:
        """Create a new workspace using shallow clone.

        This creates an isolated workspace by:
        1. Shallow cloning the repository (depth=1)
        2. Creating a new branch from the base branch

        Args:
            repo_url: Repository URL to clone.
            base_branch: Base branch to clone from.
            run_id: Run ID for naming the workspace and branch.
            branch_prefix: Optional branch prefix for the new work branch.
            auth_url: Authenticated URL for private repos.

        Returns:
            WorkspaceInfo with path and branch information.

        Raises:
            git.GitCommandError: If clone or branch creation fails.
        """
        branch_name = self._generate_branch_name(run_id, branch_prefix=branch_prefix)
        workspace_path = self.workspaces_dir / f"run_{run_id}"

        # Use auth_url for clone if provided (required for private repos)
        clone_url = auth_url or repo_url

        def _create_workspace() -> WorkspaceInfo:
            # Remove existing workspace if it exists
            if workspace_path.exists():
                shutil.rmtree(workspace_path)

            # Shallow clone with single branch
            # git clone --depth 1 --single-branch -b <base_branch> <url> <path>
            logger.info(f"Cloning repository to {workspace_path}")
            repo = git.Repo.clone_from(
                clone_url,
                workspace_path,
                depth=1,
                single_branch=True,
                branch=base_branch,
            )

            # If we used auth_url for clone, set origin to the non-auth URL
            # to avoid storing credentials in git config
            if auth_url and repo_url != auth_url:
                repo.remotes.origin.set_url(repo_url)

            # Create new branch from base
            logger.info(f"Creating branch {branch_name}")
            repo.git.checkout("-b", branch_name)

            return WorkspaceInfo(
                path=workspace_path,
                branch_name=branch_name,
                base_branch=base_branch,
                created_at=datetime.utcnow(),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _create_workspace)

    async def get_workspace(self, run_id: str) -> WorkspaceInfo | None:
        """Get workspace info for a run.

        Args:
            run_id: Run ID.

        Returns:
            WorkspaceInfo if workspace exists, None otherwise.
        """
        workspace_path = self.workspaces_dir / f"run_{run_id}"

        def _get_workspace() -> WorkspaceInfo | None:
            if not workspace_path.exists():
                return None

            try:
                repo = git.Repo(workspace_path)
                branch_name = repo.active_branch.name

                # Try to determine base branch from tracking info
                tracking = repo.active_branch.tracking_branch()
                base_branch = tracking.remote_head if tracking else "main"

                return WorkspaceInfo(
                    path=workspace_path,
                    branch_name=branch_name,
                    base_branch=base_branch,
                    created_at=datetime.fromtimestamp(workspace_path.stat().st_mtime),
                )
            except (git.InvalidGitRepositoryError, git.GitCommandError):
                return None

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_workspace)

    async def is_valid_workspace(self, workspace_path: Path) -> bool:
        """Check if a path is a valid git workspace.

        Args:
            workspace_path: Path to check.

        Returns:
            True if valid git repository, False otherwise.
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

    async def sync_with_remote(
        self,
        workspace_path: Path,
        branch: str | None = None,
        auth_url: str | None = None,
    ) -> MergeResult:
        """Sync workspace with remote (fetch + pull).

        This method fetches the latest changes from remote and pulls them
        into the current branch. If conflicts occur, they are left for resolution.

        Args:
            workspace_path: Path to the workspace.
            branch: Branch to sync (defaults to current branch).
            auth_url: Authenticated URL for private repos.

        Returns:
            MergeResult with success status and conflict information.
        """

        def _sync() -> MergeResult:
            repo = git.Repo(workspace_path)

            # Save and restore original URL if using auth_url
            original_url: str | None = None
            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                    repo.remotes.origin.set_url(auth_url)
                except Exception:
                    pass

            try:
                # Fetch latest
                repo.remotes.origin.fetch()

                # Pull
                pull_branch = branch or repo.active_branch.name
                try:
                    repo.git.pull("origin", pull_branch)
                    return MergeResult(success=True)
                except git.GitCommandError as e:
                    error_str = str(e)

                    # Check for merge conflicts
                    if "CONFLICT" in error_str or "Automatic merge failed" in error_str:
                        conflict_files = self._get_conflict_files_sync(repo)
                        return MergeResult(
                            success=False,
                            has_conflicts=True,
                            conflict_files=conflict_files,
                            error="Merge conflicts detected",
                        )

                    return MergeResult(success=False, error=str(e))

            finally:
                # Restore original URL
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
        """Check if local branch is behind its remote tracking branch.

        Args:
            workspace_path: Path to the workspace.
            branch: Branch name to check.
            auth_url: Authenticated URL for private repos.

        Returns:
            True if remote has commits not in local HEAD.
        """

        def _is_behind() -> bool:
            repo = git.Repo(workspace_path)

            # Fetch with auth if needed
            original_url: str | None = None
            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                    repo.remotes.origin.set_url(auth_url)
                except Exception:
                    pass

            try:
                repo.remotes.origin.fetch()
            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

            remote_ref = f"origin/{branch}"

            # Check if remote ref exists
            try:
                repo.git.show_ref("--verify", f"refs/remotes/{remote_ref}")
            except git.GitCommandError:
                return False

            # Get local and remote SHAs
            try:
                local_sha = repo.git.rev_parse("HEAD").strip()
                remote_sha = repo.git.rev_parse(remote_ref).strip()
            except git.GitCommandError:
                return False

            if local_sha == remote_sha:
                return False

            # Check if remote is ahead of local
            try:
                repo.git.merge_base("--is-ancestor", remote_sha, local_sha)
                return False
            except git.GitCommandError:
                return True

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _is_behind)

    async def unshallow(
        self,
        workspace_path: Path,
        auth_url: str | None = None,
    ) -> None:
        """Convert shallow clone to full clone.

        This is required before merge operations that need full history,
        such as merge-base calculations for conflict resolution.

        Args:
            workspace_path: Path to the workspace.
            auth_url: Authenticated URL for private repos.
        """

        def _unshallow() -> None:
            repo = git.Repo(workspace_path)

            # Check if already unshallowed
            shallow_file = workspace_path / ".git" / "shallow"
            if not shallow_file.exists():
                logger.info("Repository is already unshallowed")
                return

            original_url: str | None = None
            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                    repo.remotes.origin.set_url(auth_url)
                except Exception:
                    pass

            try:
                logger.info("Unshallowing repository...")
                repo.git.fetch("--unshallow")
                logger.info("Repository unshallowed successfully")
            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _unshallow)

    async def merge_base_branch(
        self,
        workspace_path: Path,
        base_branch: str,
        auth_url: str | None = None,
    ) -> MergeResult:
        """Merge base branch into current branch.

        This is used for conflict resolution when the base branch has
        changes that conflict with the current work branch.

        Note: Call unshallow() first if the repository is shallow.

        Args:
            workspace_path: Path to the workspace.
            base_branch: Base branch to merge (e.g., 'main').
            auth_url: Authenticated URL for private repos.

        Returns:
            MergeResult with success status and conflict information.
        """

        def _merge() -> MergeResult:
            repo = git.Repo(workspace_path)

            # Fetch latest base branch
            original_url: str | None = None
            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                    repo.remotes.origin.set_url(auth_url)
                except Exception:
                    pass

            try:
                repo.remotes.origin.fetch()
            finally:
                if original_url:
                    repo.remotes.origin.set_url(original_url)

            # Merge origin/<base_branch>
            remote_ref = f"origin/{base_branch}"
            try:
                repo.git.merge(remote_ref)
                return MergeResult(success=True)
            except git.GitCommandError as e:
                error_str = str(e)

                # Check for merge conflicts
                if "CONFLICT" in error_str or "Automatic merge failed" in error_str:
                    conflict_files = self._get_conflict_files_sync(repo)
                    return MergeResult(
                        success=False,
                        has_conflicts=True,
                        conflict_files=conflict_files,
                        error="Merge conflicts detected",
                    )

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
            return self._get_conflict_files_sync(repo)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_conflicts)

    async def is_merge_in_progress(self, workspace_path: Path) -> bool:
        """Check whether a merge is in progress (MERGE_HEAD exists).

        Args:
            workspace_path: Path to the workspace.

        Returns:
            True if MERGE_HEAD exists, False otherwise.
        """

        def _check() -> bool:
            try:
                merge_head = workspace_path / ".git" / "MERGE_HEAD"
                return merge_head.exists()
            except Exception:
                return False

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _check)

    def _get_conflict_files_sync(self, repo: git.Repo) -> list[str]:
        """Synchronous helper to get conflict files.

        Args:
            repo: Git repository object.

        Returns:
            List of file paths with conflicts.
        """
        try:
            unmerged = repo.git.diff("--name-only", "--diff-filter=U")
            if unmerged:
                return unmerged.strip().split("\n")
        except Exception:
            pass
        return []

    async def complete_merge(
        self,
        workspace_path: Path,
        message: str | None = None,
    ) -> str:
        """Complete a merge after conflicts have been resolved.

        This stages all resolved files and creates the merge commit.

        Args:
            workspace_path: Path to the workspace.
            message: Optional commit message (defaults to auto-generated).

        Returns:
            Commit SHA of the merge commit.
        """

        def _complete() -> str:
            repo = git.Repo(workspace_path)

            # Stage all resolved files
            repo.git.add("-A")

            # Create merge commit
            if message:
                repo.git.commit("-m", message)
            else:
                # Use default merge commit message
                repo.git.commit("--no-edit")

            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _complete)

    async def abort_merge(self, workspace_path: Path) -> None:
        """Abort an in-progress merge.

        Args:
            workspace_path: Path to the workspace.
        """

        def _abort() -> None:
            repo = git.Repo(workspace_path)
            repo.git.merge("--abort")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _abort)

    async def stage_all(self, workspace_path: Path) -> None:
        """Stage all changes.

        Args:
            workspace_path: Path to the workspace.
        """

        def _stage() -> None:
            repo = git.Repo(workspace_path)
            repo.git.add("-A")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _stage)

    async def get_diff(self, workspace_path: Path, staged: bool = True) -> str:
        """Get diff.

        Args:
            workspace_path: Path to the workspace.
            staged: If True, get staged diff; otherwise get unstaged diff.

        Returns:
            Unified diff string.
        """

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

    async def commit(
        self,
        workspace_path: Path,
        message: str,
    ) -> str:
        """Create a commit.

        Args:
            workspace_path: Path to the workspace.
            message: Commit message.

        Returns:
            Commit SHA.
        """

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
        """Push to remote.

        Args:
            workspace_path: Path to the workspace.
            branch: Branch name to push.
            auth_url: Authenticated URL for push.
            force: If True, force push.
        """

        def _push() -> None:
            repo = git.Repo(workspace_path)

            original_url: str | None = None
            if auth_url:
                try:
                    original_url = repo.remotes.origin.url
                    repo.remotes.origin.set_url(auth_url)
                except Exception:
                    pass

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

    async def cleanup_workspace(
        self,
        workspace_path: Path,
    ) -> None:
        """Remove a workspace.

        Args:
            workspace_path: Path to the workspace to remove.
        """

        def _cleanup() -> None:
            if workspace_path.exists():
                shutil.rmtree(workspace_path, ignore_errors=True)
                logger.info(f"Cleaned up workspace: {workspace_path}")

        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, _cleanup)

    async def get_current_branch(self, workspace_path: Path) -> str:
        """Get the current branch name.

        Args:
            workspace_path: Path to the workspace.

        Returns:
            Current branch name.
        """

        def _get_branch() -> str:
            repo = git.Repo(workspace_path)
            return str(repo.active_branch.name)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_branch)

    async def get_head_sha(self, workspace_path: Path) -> str:
        """Get the current HEAD commit SHA.

        Args:
            workspace_path: Path to the workspace.

        Returns:
            HEAD commit SHA.
        """

        def _get_sha() -> str:
            repo = git.Repo(workspace_path)
            return str(repo.head.commit.hexsha)

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _get_sha)

    async def get_changed_files(self, workspace_path: Path) -> list[str]:
        """Get list of changed files.

        Args:
            workspace_path: Path to the workspace.

        Returns:
            List of changed file paths.
        """

        def _get_changed() -> list[str]:
            repo = git.Repo(workspace_path)
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
        return await loop.run_in_executor(None, _get_changed)

    async def restore_workspace(
        self,
        repo_url: str,
        branch_name: str,
        base_branch: str,
        run_id: str,
        auth_url: str | None = None,
        workspace_path: Path | None = None,
    ) -> WorkspaceInfo:
        """Restore workspace from an existing remote branch.

        This is used when a workspace is invalid/deleted but the branch still
        exists on the remote. We fetch the branch and check it out to restore
        the previous work.

        Args:
            repo_url: Repository URL to clone.
            branch_name: Existing branch name to restore from remote.
            base_branch: Base branch for reference.
            run_id: Run ID for naming the workspace.
            auth_url: Authenticated URL for private repos.

        Returns:
            WorkspaceInfo with path and branch information.

        Raises:
            git.GitCommandError: If clone or checkout fails.
            ValueError: If the branch does not exist on remote.
        """
        target_path = workspace_path or (self.workspaces_dir / f"run_{run_id}")

        # Use auth_url for clone if provided (required for private repos)
        clone_url = auth_url or repo_url

        def _restore_workspace() -> WorkspaceInfo:
            # Remove existing workspace if it exists
            if target_path.exists():
                shutil.rmtree(target_path)

            # Clone the repository with base branch first
            logger.info(f"Cloning repository to {target_path} for restoration")
            repo = git.Repo.clone_from(
                clone_url,
                target_path,
                depth=1,
                single_branch=False,  # Need to fetch the working branch
                branch=base_branch,
            )

            # If we used auth_url for clone, set origin to the non-auth URL
            # to avoid storing credentials in git config
            if auth_url and repo_url != auth_url:
                repo.remotes.origin.set_url(repo_url)

            # Temporarily set auth URL for fetch if needed
            original_url: str | None = None
            if auth_url:
                original_url = repo.remotes.origin.url
                repo.remotes.origin.set_url(auth_url)

            try:
                # Fetch the specific branch from remote
                logger.info(f"Fetching branch {branch_name} from remote")
                try:
                    repo.git.fetch("origin", branch_name)
                except git.GitCommandError as e:
                    raise ValueError(f"Branch '{branch_name}' does not exist on remote: {e}")

                # Checkout the existing remote branch
                logger.info(f"Checking out branch {branch_name}")
                repo.git.checkout("-b", branch_name, f"origin/{branch_name}")

            finally:
                # Restore original URL
                if original_url:
                    repo.remotes.origin.set_url(original_url)

            return WorkspaceInfo(
                path=target_path,
                branch_name=branch_name,
                base_branch=base_branch,
                created_at=datetime.utcnow(),
            )

        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, _restore_workspace)
