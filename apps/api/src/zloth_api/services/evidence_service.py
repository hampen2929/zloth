"""Evidence collection service for Decision Visibility (P0).

This service automatically collects machine-verifiable evidence for decisions.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from zloth_api.domain.models import (
    CIEvidence,
    Evidence,
    MetricsEvidence,
    RefsEvidence,
    ReviewEvidence,
    Run,
)

if TYPE_CHECKING:
    from zloth_api.storage.dao import CICheckDAO, ReviewDAO, RunDAO

logger = logging.getLogger(__name__)


class EvidenceService:
    """Service for collecting evidence for decisions."""

    def __init__(
        self,
        run_dao: RunDAO,
        ci_check_dao: CICheckDAO | None = None,
        review_dao: ReviewDAO | None = None,
    ):
        self.run_dao = run_dao
        self.ci_check_dao = ci_check_dao
        self.review_dao = review_dao

    async def collect_ci_evidence(
        self, task_id: str, pr_id: str | None = None
    ) -> CIEvidence | None:
        """Collect CI result evidence.

        Args:
            task_id: Task ID.
            pr_id: Optional PR ID for specific CI check.

        Returns:
            CIEvidence or None if no CI data available.
        """
        if not self.ci_check_dao or not pr_id:
            return None

        try:
            ci_check = await self.ci_check_dao.get_latest_by_pr_id(pr_id)
            if not ci_check:
                return None

            # Determine overall status
            status = "pending"
            if ci_check.status == "success":
                status = "passed"
            elif ci_check.status in ("failure", "error"):
                status = "failed"

            # Extract failed checks
            failed_checks = []
            for job in ci_check.failed_jobs:
                failed_checks.append(
                    {
                        "name": job.job_name,
                        "reason": job.error_log or "Unknown failure",
                    }
                )

            # Get all check names
            check_names = list(ci_check.jobs.keys()) if ci_check.jobs else []

            return CIEvidence(
                status=status,
                failed_checks=failed_checks,
                check_names=check_names,
            )
        except Exception as e:
            logger.warning(f"Failed to collect CI evidence: {e}")
            return None

    def collect_metrics_evidence(self, run: Run) -> MetricsEvidence:
        """Collect metrics evidence from a run.

        Args:
            run: Run object.

        Returns:
            MetricsEvidence with lines and files changed.
        """
        lines_changed = 0
        files_changed = len(run.files_changed)

        for file_diff in run.files_changed:
            lines_changed += file_diff.added_lines + file_diff.removed_lines

        return MetricsEvidence(
            lines_changed=lines_changed,
            files_changed=files_changed,
        )

    async def collect_review_evidence(self, task_id: str, run_id: str) -> ReviewEvidence | None:
        """Collect review evidence for a run.

        Args:
            task_id: Task ID.
            run_id: Run ID.

        Returns:
            ReviewEvidence or None if no review data available.
        """
        if not self.review_dao:
            return None

        try:
            # Get review summaries for the task
            summaries = await self.review_dao.list_by_task(task_id)
            if not summaries:
                return None

            # Fetch full reviews to check target_run_ids
            approvals = 0
            change_requests = 0

            for summary in summaries:
                # Get full review to check if it targets this run
                review = await self.review_dao.get(summary.id)
                if not review:
                    continue

                # Check if this review targets the run
                if run_id not in review.target_run_ids:
                    continue

                # Count based on overall_score
                if review.overall_score is not None:
                    if review.overall_score >= 0.75:
                        approvals += 1
                    elif review.overall_score < 0.5:
                        change_requests += 1

            if approvals == 0 and change_requests == 0:
                return None

            return ReviewEvidence(
                approvals=approvals,
                change_requests=change_requests,
            )
        except Exception as e:
            logger.warning(f"Failed to collect review evidence: {e}")
            return None

    def collect_refs_evidence(
        self, pr_url: str | None = None, ci_url: str | None = None
    ) -> RefsEvidence | None:
        """Collect reference URL evidence.

        Args:
            pr_url: Pull request URL.
            ci_url: CI workflow URL.

        Returns:
            RefsEvidence or None if no refs available.
        """
        if not pr_url and not ci_url:
            return None

        return RefsEvidence(
            pr_url=pr_url,
            ci_url=ci_url,
        )

    async def build_evidence(
        self,
        run: Run,
        task_id: str,
        pr_id: str | None = None,
        pr_url: str | None = None,
        ci_url: str | None = None,
    ) -> Evidence:
        """Build complete evidence structure for a run.

        Args:
            run: Run object.
            task_id: Task ID.
            pr_id: Optional PR ID.
            pr_url: Optional PR URL.
            ci_url: Optional CI URL.

        Returns:
            Complete Evidence object.
        """
        # Collect all evidence types
        ci_evidence = await self.collect_ci_evidence(task_id, pr_id)
        metrics_evidence = self.collect_metrics_evidence(run)
        review_evidence = await self.collect_review_evidence(task_id, run.id)
        refs_evidence = self.collect_refs_evidence(pr_url, ci_url)

        return Evidence(
            ci_results=ci_evidence,
            metrics=metrics_evidence,
            review_summary=review_evidence,
            refs=refs_evidence,
        )

    async def build_evidence_for_runs(
        self,
        runs: list[Run],
        task_id: str,
    ) -> dict[str, Evidence]:
        """Build evidence for multiple runs.

        Args:
            runs: List of Run objects.
            task_id: Task ID.

        Returns:
            Dictionary mapping run_id to Evidence.
        """
        evidence_map: dict[str, Evidence] = {}

        for run in runs:
            evidence = await self.build_evidence(run, task_id)
            evidence_map[run.id] = evidence

        return evidence_map
