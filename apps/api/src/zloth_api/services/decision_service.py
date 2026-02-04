"""Decision service for Decision Visibility (P0).

This service manages the recording and retrieval of decisions.
"""

from __future__ import annotations

import builtins
import logging
from typing import TYPE_CHECKING, Any

from zloth_api.domain.enums import (
    DeciderType,
    DecisionType,
    OutcomeStatus,
    RiskLevel,
)
from zloth_api.domain.models import (
    Alternative,
    Decision,
    DecisionCreate,
    ExcludedPathReason,
    PromotionScope,
    RejectedRun,
)
from zloth_api.errors import NotFoundError, ValidationError

if TYPE_CHECKING:
    from zloth_api.services.evidence_service import EvidenceService
    from zloth_api.services.risk_service import RiskService
    from zloth_api.storage.dao import PRDAO, DecisionDAO, RunDAO

logger = logging.getLogger(__name__)


class DecisionService:
    """Service for managing decisions."""

    def __init__(
        self,
        decision_dao: DecisionDAO,
        run_dao: RunDAO,
        pr_dao: PRDAO,
        evidence_service: EvidenceService,
        risk_service: RiskService,
    ):
        self.decision_dao = decision_dao
        self.run_dao = run_dao
        self.pr_dao = pr_dao
        self.evidence_service = evidence_service
        self.risk_service = risk_service

    async def record_selection(
        self,
        task_id: str,
        selected_run_id: str,
        rejected_run_ids: list[str],
        reason: str,
        rejection_reasons: dict[str, str],
        comparison_axes: list[str],
        decider_type: DeciderType = DeciderType.HUMAN,
    ) -> Decision:
        """Record a run selection decision.

        Args:
            task_id: Task ID.
            selected_run_id: Selected run ID.
            rejected_run_ids: List of rejected run IDs.
            reason: Reason for selection.
            rejection_reasons: Map of run_id to rejection reason.
            comparison_axes: Comparison criteria used.
            decider_type: Who made the decision.

        Returns:
            Created Decision record.
        """
        # Get selected run
        selected_run = await self.run_dao.get(selected_run_id)
        if not selected_run:
            raise NotFoundError("Selected run not found", details={"run_id": selected_run_id})

        # Build evidence for selected run
        evidence = await self.evidence_service.build_evidence(selected_run, task_id)

        # Build alternatives
        rejected_runs: list[RejectedRun] = []
        for run_id in rejected_run_ids:
            run = await self.run_dao.get(run_id)
            if run:
                run_evidence = await self.evidence_service.build_evidence(run, task_id)
                rejected_runs.append(
                    RejectedRun(
                        run_id=run_id,
                        reason=rejection_reasons.get(run_id, "Not selected"),
                        evidence=run_evidence,
                    )
                )

        alternatives = Alternative(
            rejected_runs=rejected_runs,
            comparison_axes=comparison_axes,
        )

        # Calculate risk level from selected run's changed files
        files_changed = [f.path for f in selected_run.files_changed]
        risk_level, risk_level_reason = self.risk_service.calculate_risk_level(files_changed)

        # Create decision
        return await self.decision_dao.create(
            task_id=task_id,
            decision_type=DecisionType.SELECTION,
            decider_type=decider_type,
            reason=reason,
            evidence=evidence.model_dump(),
            alternatives=alternatives.model_dump(),
            scope=None,
            selected_run_id=selected_run_id,
            pr_id=None,
            risk_level=risk_level,
            risk_level_reason=risk_level_reason,
        )

    async def record_promotion(
        self,
        task_id: str,
        run_id: str,
        pr_id: str | None,
        reason: str,
        included_paths: list[str] | None = None,
        excluded_paths: list[str] | None = None,
        excluded_reasons: list[ExcludedPathReason] | None = None,
        decider_type: DeciderType = DeciderType.HUMAN,
        pr_url: str | None = None,
    ) -> Decision:
        """Record a PR promotion decision.

        Args:
            task_id: Task ID.
            run_id: Run ID being promoted.
            pr_id: Created PR ID.
            reason: Reason for promotion.
            included_paths: Paths included in PR.
            excluded_paths: Paths excluded from PR.
            excluded_reasons: Reasons for exclusions.
            decider_type: Who made the decision.
            pr_url: PR URL for evidence.

        Returns:
            Created Decision record.
        """
        # Get run
        run = await self.run_dao.get(run_id)
        if not run:
            raise NotFoundError("Run not found", details={"run_id": run_id})

        # Build evidence
        evidence = await self.evidence_service.build_evidence(
            run, task_id, pr_id=pr_id, pr_url=pr_url
        )

        # Build scope
        if included_paths is None:
            # Default to all changed files
            included_paths = [f.path for f in run.files_changed]

        scope = PromotionScope(
            included_paths=included_paths or [],
            excluded_paths=excluded_paths or [],
            excluded_reasons=excluded_reasons or [],
        )

        # Calculate risk level
        files_changed = [f.path for f in run.files_changed]
        risk_level, risk_level_reason = self.risk_service.calculate_risk_level(files_changed)

        # Create decision
        return await self.decision_dao.create(
            task_id=task_id,
            decision_type=DecisionType.PROMOTION,
            decider_type=decider_type,
            reason=reason,
            evidence=evidence.model_dump(),
            alternatives=None,
            scope=scope.model_dump(),
            selected_run_id=run_id,
            pr_id=pr_id,
            risk_level=risk_level,
            risk_level_reason=risk_level_reason,
        )

    async def record_merge(
        self,
        task_id: str,
        pr_id: str,
        reason: str,
        decider_type: DeciderType = DeciderType.HUMAN,
    ) -> Decision:
        """Record a merge decision.

        Args:
            task_id: Task ID.
            pr_id: PR ID being merged.
            reason: Reason for merge.
            decider_type: Who made the decision.

        Returns:
            Created Decision record.
        """
        # Get PR
        pr = await self.pr_dao.get(pr_id)
        if not pr:
            raise NotFoundError("PR not found", details={"pr_id": pr_id})

        # Find the run associated with this PR's branch
        runs = await self.run_dao.list(task_id)
        run = next(
            (r for r in runs if r.working_branch == pr.branch),
            None,
        )

        # Build evidence
        evidence_dict: dict[str, Any] = {}
        risk_level = RiskLevel.MEDIUM
        risk_level_reason = "Standard merge"

        if run:
            evidence = await self.evidence_service.build_evidence(
                run, task_id, pr_id=pr_id, pr_url=pr.url
            )
            evidence_dict = evidence.model_dump()

            # Calculate risk level
            files_changed = [f.path for f in run.files_changed]
            risk_level, risk_level_reason = self.risk_service.calculate_risk_level(files_changed)
        else:
            # Minimal evidence without run
            evidence_dict = {
                "refs": {"pr_url": pr.url},
            }

        # Create decision
        return await self.decision_dao.create(
            task_id=task_id,
            decision_type=DecisionType.MERGE,
            decider_type=decider_type,
            reason=reason,
            evidence=evidence_dict,
            alternatives=None,
            scope=None,
            selected_run_id=run.id if run else None,
            pr_id=pr_id,
            risk_level=risk_level,
            risk_level_reason=risk_level_reason,
        )

    async def create_from_request(self, task_id: str, data: DecisionCreate) -> Decision:
        """Create a decision from an API request.

        Args:
            task_id: Task ID.
            data: DecisionCreate request.

        Returns:
            Created Decision record.
        """
        if data.decision_type == DecisionType.SELECTION:
            if not data.selected_run_id:
                raise ValidationError("selected_run_id is required for selection decisions")
            return await self.record_selection(
                task_id=task_id,
                selected_run_id=data.selected_run_id,
                rejected_run_ids=data.rejected_run_ids or [],
                reason=data.reason,
                rejection_reasons=data.rejection_reasons or {},
                comparison_axes=data.comparison_axes or [],
                decider_type=data.decider_type,
            )

        elif data.decision_type == DecisionType.PROMOTION:
            run_id = data.run_id or data.selected_run_id
            if not run_id:
                raise ValidationError(
                    "run_id or selected_run_id is required for promotion decisions"
                )
            return await self.record_promotion(
                task_id=task_id,
                run_id=run_id,
                pr_id=data.pr_id,
                reason=data.reason,
                included_paths=data.included_paths,
                excluded_paths=data.excluded_paths,
                excluded_reasons=data.excluded_reasons,
                decider_type=data.decider_type,
            )

        elif data.decision_type == DecisionType.MERGE:
            if not data.pr_id:
                raise ValidationError("pr_id is required for merge decisions")
            return await self.record_merge(
                task_id=task_id,
                pr_id=data.pr_id,
                reason=data.reason,
                decider_type=data.decider_type,
            )

        else:
            raise ValidationError(f"Unknown decision type: {data.decision_type}")

    async def get(self, decision_id: str) -> Decision | None:
        """Get a decision by ID.

        Args:
            decision_id: Decision ID.

        Returns:
            Decision or None if not found.
        """
        return await self.decision_dao.get(decision_id)

    async def list(self, task_id: str) -> list[Decision]:
        """List decisions for a task.

        Args:
            task_id: Task ID.

        Returns:
            List of decisions ordered by created_at.
        """
        return await self.decision_dao.list(task_id)

    async def update_outcome(
        self,
        decision_id: str,
        outcome: OutcomeStatus,
        reason: str,
        refs: builtins.list[str],
    ) -> Decision:
        """Update the outcome of a decision.

        Args:
            decision_id: Decision ID.
            outcome: Outcome status.
            reason: Reason for outcome.
            refs: Reference URLs.

        Returns:
            Updated Decision.
        """
        decision = await self.decision_dao.update_outcome(decision_id, outcome, reason, refs)
        if not decision:
            raise NotFoundError("Decision not found", details={"decision_id": decision_id})
        return decision
