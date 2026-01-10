"""Auto-merge service for agentic dursor."""

import logging
from typing import Literal

from dursor_api.config import settings
from dursor_api.domain.models import MergeConditions, MergeResult
from dursor_api.services.github_service import GitHubService

logger = logging.getLogger(__name__)


class AutoMergeService:
    """Service for automated PR merging.

    Handles merge condition checking and automated merge execution
    for the agentic workflow.
    """

    def __init__(
        self,
        github_service: GitHubService,
        owner: str,
        repo: str,
    ):
        """Initialize auto-merge service.

        Args:
            github_service: GitHub service for API calls.
            owner: Repository owner.
            repo: Repository name.
        """
        self.github = github_service
        self.owner = owner
        self.repo = repo

    async def check_all_conditions(self, pr_number: int) -> MergeConditions:
        """Check if all merge conditions are met.

        Args:
            pr_number: PR number to check.

        Returns:
            MergeConditions with status of each condition.
        """
        passed: list[str] = []
        failed: list[str] = []

        try:
            # Get PR status
            pr_status = await self.github.get_pull_request_status(self.owner, self.repo, pr_number)

            # Check if PR is still open
            if pr_status.get("state") == "open":
                passed.append("pr_open")
            else:
                failed.append("pr_not_open")
                return MergeConditions(can_merge=False, passed=passed, failed=failed)

            # Check if already merged
            if pr_status.get("merged"):
                failed.append("already_merged")
                return MergeConditions(can_merge=False, passed=passed, failed=failed)

            passed.append("not_merged")

            # Check CI status via commit status API
            ci_passed = await self._check_ci_status(pr_number)
            if ci_passed:
                passed.append("ci_passed")
            else:
                failed.append("ci_failed")

            # Check for merge conflicts
            mergeable = await self._check_mergeable(pr_number)
            if mergeable:
                passed.append("no_conflicts")
            else:
                failed.append("has_conflicts")

        except Exception as e:
            logger.error(f"Error checking merge conditions: {e}")
            failed.append(f"check_error: {e}")

        can_merge = len(failed) == 0
        return MergeConditions(can_merge=can_merge, passed=passed, failed=failed)

    async def _check_ci_status(self, pr_number: int) -> bool:
        """Check if CI has passed for the PR.

        Args:
            pr_number: PR number.

        Returns:
            True if CI passed, False otherwise.
        """
        try:
            # Get combined status for the PR head
            pr_data = await self.github._github_request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}",
            )
            head_sha = pr_data.get("head", {}).get("sha")
            if not head_sha:
                return False

            # Get combined commit status
            status_data = await self.github._github_request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/commits/{head_sha}/status",
            )

            state = status_data.get("state", "pending")
            return state == "success"
        except Exception as e:
            logger.warning(f"Error checking CI status: {e}")
            # If we can't check, assume not passed
            return False

    async def _check_mergeable(self, pr_number: int) -> bool:
        """Check if PR is mergeable (no conflicts).

        Args:
            pr_number: PR number.

        Returns:
            True if mergeable, False otherwise.
        """
        try:
            pr_data = await self.github._github_request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}",
            )
            # GitHub returns null if mergeable state is still being computed
            mergeable = pr_data.get("mergeable")
            return mergeable is True
        except Exception as e:
            logger.warning(f"Error checking mergeable status: {e}")
            return False

    async def merge(
        self,
        pr_number: int,
        method: Literal["merge", "squash", "rebase"] | None = None,
        delete_branch: bool | None = None,
    ) -> MergeResult:
        """Execute merge for a PR.

        Args:
            pr_number: PR number to merge.
            method: Merge method (merge, squash, rebase).
            delete_branch: Whether to delete the branch after merge.

        Returns:
            MergeResult with success status.
        """
        merge_method = method or settings.merge_method
        should_delete = delete_branch if delete_branch is not None else settings.merge_delete_branch

        try:
            # First check conditions
            conditions = await self.check_all_conditions(pr_number)
            if not conditions.can_merge:
                return MergeResult(
                    success=False,
                    error=f"Merge conditions not met: {', '.join(conditions.failed)}",
                )

            # Get PR info for branch name
            pr_data = await self.github._github_request(
                "GET",
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}",
            )
            head_branch = pr_data.get("head", {}).get("ref")

            # Execute merge
            merge_response = await self.github._github_request(
                "PUT",
                f"/repos/{self.owner}/{self.repo}/pulls/{pr_number}/merge",
                json={
                    "merge_method": merge_method,
                },
            )

            merge_sha = merge_response.get("sha")
            if not merge_sha:
                return MergeResult(
                    success=False,
                    error="Merge response did not contain SHA",
                )

            # Delete branch if requested
            if should_delete and head_branch:
                try:
                    await self._delete_branch(head_branch)
                    logger.info(f"Deleted branch: {head_branch}")
                except Exception as e:
                    # Branch deletion failure is not critical
                    logger.warning(f"Failed to delete branch {head_branch}: {e}")

            return MergeResult(success=True, merge_sha=merge_sha)

        except Exception as e:
            logger.error(f"Error merging PR #{pr_number}: {e}")
            return MergeResult(success=False, error=str(e))

    async def _delete_branch(self, branch: str) -> None:
        """Delete a branch.

        Args:
            branch: Branch name to delete.
        """
        await self.github._github_request(
            "DELETE",
            f"/repos/{self.owner}/{self.repo}/git/refs/heads/{branch}",
        )
