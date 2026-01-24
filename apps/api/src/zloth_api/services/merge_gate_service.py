"""Merge gate service for checking merge conditions."""

import logging
from typing import TYPE_CHECKING

from zloth_api.config import settings
from zloth_api.domain.models import (
    MergeCondition,
    MergeConditionsResult,
    MergeResult,
)
from zloth_api.services.settings_service import SettingsService

if TYPE_CHECKING:
    from zloth_api.services.github_service import GitHubService
    from zloth_api.storage.dao import ReviewDAO

logger = logging.getLogger(__name__)


# Fix strategies for different CI failures
FIX_STRATEGIES: dict[str, str] = {
    "backend_lint": "Run 'ruff check --fix' and 'ruff format'",
    "backend_typecheck": "Add type annotations, fix type errors",
    "backend_test": "Fix failing tests or update test expectations",
    "frontend_lint": "Run 'npm run lint -- --fix'",
    "frontend_build": "Fix TypeScript errors, missing imports",
    "frontend_test": "Fix failing E2E tests",
    "codex_review": "Address blocking issues from review feedback",
    "security_scan": "Remove hardcoded secrets, use environment variables",
    "coverage": "Add tests for uncovered code paths",
}


class MergeGateService:
    """Service for checking merge conditions and executing merges."""

    def __init__(
        self,
        github_service: "GitHubService",
        review_dao: "ReviewDAO",
        settings_service: SettingsService | None = None,
    ):
        """Initialize merge gate service.

        Args:
            github_service: GitHub service for API operations.
            review_dao: Review DAO for accessing review data.
        """
        self.github = github_service
        self.review_dao = review_dao
        self.settings_service = settings_service

    async def check_all_conditions(
        self,
        pr_number: int,
        repo_full_name: str,
        last_review_score: float | None = None,
    ) -> MergeConditionsResult:
        """Check all merge conditions for a PR.

        Args:
            pr_number: PR number to check.
            repo_full_name: Full repository name (owner/repo).
            last_review_score: Last review score if available.

        Returns:
            Result containing all condition checks.
        """
        conditions: list[MergeCondition] = []
        failed: list[str] = []

        # 1. Check CI status
        ci_condition = await self._check_ci_status(pr_number, repo_full_name)
        conditions.append(ci_condition)
        if not ci_condition.passed:
            failed.append(ci_condition.name)

        # 2. Check review score
        review_condition = await self._check_review_score(last_review_score)
        conditions.append(review_condition)
        if not review_condition.passed:
            failed.append(review_condition.name)

        # 3. Check for merge conflicts
        conflict_condition = await self._check_no_conflicts(pr_number, repo_full_name)
        conditions.append(conflict_condition)
        if not conflict_condition.passed:
            failed.append(conflict_condition.name)

        # 4. Check if PR is mergeable (GitHub's built-in check)
        mergeable_condition = await self._check_pr_mergeable(pr_number, repo_full_name)
        conditions.append(mergeable_condition)
        if not mergeable_condition.passed:
            failed.append(mergeable_condition.name)

        can_merge = len(failed) == 0

        return MergeConditionsResult(
            can_merge=can_merge,
            conditions=conditions,
            failed=failed,
        )

    async def _check_ci_status(
        self,
        pr_number: int,
        repo_full_name: str,
    ) -> MergeCondition:
        """Check if all CI checks have passed.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name.

        Returns:
            Condition check result.
        """
        try:
            # Get combined status from GitHub
            status = await self.github.get_pr_check_status(pr_number, repo_full_name)

            if status == "success":
                return MergeCondition(
                    name="CI Green",
                    passed=True,
                    message="All CI checks passed",
                )
            elif status == "pending":
                return MergeCondition(
                    name="CI Green",
                    passed=False,
                    message="CI checks still running",
                )
            else:
                return MergeCondition(
                    name="CI Green",
                    passed=False,
                    message=f"CI checks failed (status: {status})",
                )
        except Exception as e:
            logger.error(f"Error checking CI status: {e}")
            return MergeCondition(
                name="CI Green",
                passed=False,
                message=f"Failed to check CI status: {str(e)}",
            )

    async def _check_review_score(
        self,
        last_review_score: float | None,
    ) -> MergeCondition:
        """Check if review score meets minimum threshold.

        Args:
            last_review_score: Last review score.

        Returns:
            Condition check result.
        """
        # Allow DB override for min review score
        if self.settings_service is not None:
            min_score = await self.settings_service.get_review_min_score()
        else:
            min_score = settings.review_min_score

        if last_review_score is None:
            return MergeCondition(
                name="Review Score",
                passed=False,
                message="No review score available",
            )

        if last_review_score >= min_score:
            return MergeCondition(
                name="Review Score",
                passed=True,
                message=f"Review score {last_review_score:.2f} >= {min_score}",
            )
        else:
            return MergeCondition(
                name="Review Score",
                passed=False,
                message=f"Review score {last_review_score:.2f} < {min_score}",
            )

    async def _check_no_conflicts(
        self,
        pr_number: int,
        repo_full_name: str,
    ) -> MergeCondition:
        """Check if PR has no merge conflicts.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name.

        Returns:
            Condition check result.
        """
        try:
            has_conflicts = await self.github.check_pr_conflicts(pr_number, repo_full_name)

            if not has_conflicts:
                return MergeCondition(
                    name="No Conflicts",
                    passed=True,
                    message="No merge conflicts",
                )
            else:
                return MergeCondition(
                    name="No Conflicts",
                    passed=False,
                    message="PR has merge conflicts that need resolution",
                )
        except Exception as e:
            logger.error(f"Error checking conflicts: {e}")
            return MergeCondition(
                name="No Conflicts",
                passed=False,
                message=f"Failed to check conflicts: {str(e)}",
            )

    async def _check_pr_mergeable(
        self,
        pr_number: int,
        repo_full_name: str,
    ) -> MergeCondition:
        """Check if PR is mergeable according to GitHub.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name.

        Returns:
            Condition check result.
        """
        try:
            is_mergeable = await self.github.is_pr_mergeable(pr_number, repo_full_name)

            if is_mergeable:
                return MergeCondition(
                    name="PR Mergeable",
                    passed=True,
                    message="PR is mergeable",
                )
            else:
                return MergeCondition(
                    name="PR Mergeable",
                    passed=False,
                    message="PR is not mergeable (check GitHub for details)",
                )
        except Exception as e:
            logger.error(f"Error checking PR mergeable status: {e}")
            return MergeCondition(
                name="PR Mergeable",
                passed=False,
                message=f"Failed to check mergeable status: {str(e)}",
            )

    async def merge(
        self,
        pr_number: int,
        repo_full_name: str,
        method: str = "squash",
        delete_branch: bool = True,
    ) -> MergeResult:
        """Execute merge for a PR.

        Args:
            pr_number: PR number to merge.
            repo_full_name: Full repository name.
            method: Merge method (merge, squash, rebase).
            delete_branch: Whether to delete the branch after merge.

        Returns:
            Merge result.
        """
        try:
            # First check all conditions
            conditions = await self.check_all_conditions(pr_number, repo_full_name)

            if not conditions.can_merge:
                return MergeResult(
                    success=False,
                    error=f"Merge conditions not met: {', '.join(conditions.failed)}",
                )

            # Execute merge
            merge_sha = await self.github.merge_pr(
                pr_number,
                repo_full_name,
                method=method,
            )

            if not merge_sha:
                return MergeResult(
                    success=False,
                    error="Merge failed - no SHA returned",
                )

            # Delete branch if requested
            if delete_branch:
                try:
                    await self.github.delete_pr_branch(pr_number, repo_full_name)
                except Exception as e:
                    logger.warning(f"Failed to delete branch: {e}")
                    # Don't fail the merge if branch deletion fails

            return MergeResult(
                success=True,
                merge_sha=merge_sha,
            )

        except Exception as e:
            logger.error(f"Merge failed: {e}")
            return MergeResult(
                success=False,
                error=str(e),
            )

    def get_fix_strategy(self, job_name: str) -> str:
        """Get fix strategy for a failed CI job.

        Args:
            job_name: Name of the failed job.

        Returns:
            Fix strategy description.
        """
        return FIX_STRATEGIES.get(job_name, "Analyze the error and fix accordingly")
