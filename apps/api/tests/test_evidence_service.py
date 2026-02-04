"""Tests for EvidenceService."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from zloth_api.domain.enums import ExecutorType, ReviewStatus, RunStatus
from zloth_api.domain.models import (
    CICheck,
    CIJobResult,
    FileDiff,
    Review,
    ReviewSummary,
    Run,
)
from zloth_api.services.evidence_service import EvidenceService


def create_mock_run(
    run_id: str = "run-1",
    files_changed: list[FileDiff] | None = None,
) -> Run:
    """Create a mock Run object."""
    if files_changed is None:
        files_changed = [
            FileDiff(path="src/main.py", added_lines=10, removed_lines=5, patch=""),
            FileDiff(path="src/utils.py", added_lines=20, removed_lines=0, patch=""),
        ]

    return Run(
        id=run_id,
        task_id="task-1",
        message_id=None,
        model_id=None,
        model_name="claude-code",
        provider=None,
        executor_type=ExecutorType.CLAUDE_CODE,
        working_branch="feature/test",
        worktree_path="/tmp/test",
        instruction="Test instruction",
        base_ref="main",
        commit_sha="abc123",
        status=RunStatus.SUCCEEDED,
        summary="Test summary",
        patch="",
        files_changed=files_changed,
        logs=[],
        warnings=[],
        error=None,
        created_at=datetime.utcnow(),
        started_at=datetime.utcnow(),
        completed_at=datetime.utcnow(),
    )


@pytest.fixture
def mock_run_dao() -> AsyncMock:
    """Create a mock RunDAO."""
    return AsyncMock()


@pytest.fixture
def mock_ci_check_dao() -> AsyncMock:
    """Create a mock CICheckDAO."""
    return AsyncMock()


@pytest.fixture
def mock_review_dao() -> AsyncMock:
    """Create a mock ReviewDAO."""
    return AsyncMock()


@pytest.fixture
def evidence_service(
    mock_run_dao: AsyncMock,
    mock_ci_check_dao: AsyncMock,
    mock_review_dao: AsyncMock,
) -> EvidenceService:
    """Create an EvidenceService instance."""
    return EvidenceService(mock_run_dao, mock_ci_check_dao, mock_review_dao)


class TestMetricsEvidence:
    """Tests for metrics evidence collection."""

    def test_collect_metrics_evidence(self, evidence_service: EvidenceService) -> None:
        """Test collecting metrics from a run."""
        run = create_mock_run()
        metrics = evidence_service.collect_metrics_evidence(run)

        assert metrics.lines_changed == 35  # 10 + 5 + 20 + 0
        assert metrics.files_changed == 2

    def test_collect_metrics_empty_run(self, evidence_service: EvidenceService) -> None:
        """Test metrics for run with no file changes."""
        run = create_mock_run(files_changed=[])
        metrics = evidence_service.collect_metrics_evidence(run)

        assert metrics.lines_changed == 0
        assert metrics.files_changed == 0


class TestCIEvidence:
    """Tests for CI evidence collection."""

    @pytest.mark.asyncio
    async def test_collect_ci_evidence_passed(
        self,
        evidence_service: EvidenceService,
        mock_ci_check_dao: AsyncMock,
    ) -> None:
        """Test CI evidence collection for passed checks."""
        mock_ci_check_dao.get_latest_by_pr_id.return_value = CICheck(
            id="ci-1",
            task_id="task-1",
            pr_id="pr-1",
            status="success",
            workflow_run_id=123,
            sha="abc123",
            jobs={"build": "success", "test": "success"},
            failed_jobs=[],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        ci = await evidence_service.collect_ci_evidence("task-1", "pr-1")

        assert ci is not None
        assert ci.status == "passed"
        assert len(ci.check_names) == 2
        assert "build" in ci.check_names
        assert "test" in ci.check_names

    @pytest.mark.asyncio
    async def test_collect_ci_evidence_failed(
        self,
        evidence_service: EvidenceService,
        mock_ci_check_dao: AsyncMock,
    ) -> None:
        """Test CI evidence collection for failed checks."""
        mock_ci_check_dao.get_latest_by_pr_id.return_value = CICheck(
            id="ci-1",
            task_id="task-1",
            pr_id="pr-1",
            status="failure",
            workflow_run_id=123,
            sha="abc123",
            jobs={"build": "success", "test": "failure"},
            failed_jobs=[CIJobResult(job_name="test", result="failure", error_log="Test failed")],
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        ci = await evidence_service.collect_ci_evidence("task-1", "pr-1")

        assert ci is not None
        assert ci.status == "failed"
        assert len(ci.failed_checks) == 1
        assert ci.failed_checks[0]["name"] == "test"

    @pytest.mark.asyncio
    async def test_collect_ci_evidence_no_pr(self, evidence_service: EvidenceService) -> None:
        """Test CI evidence collection without PR ID."""
        ci = await evidence_service.collect_ci_evidence("task-1", None)
        assert ci is None


class TestReviewEvidence:
    """Tests for review evidence collection."""

    @pytest.mark.asyncio
    async def test_collect_review_evidence(
        self,
        evidence_service: EvidenceService,
        mock_review_dao: AsyncMock,
    ) -> None:
        """Test review evidence collection."""
        # Return ReviewSummary objects from list_by_task
        mock_review_dao.list_by_task.return_value = [
            ReviewSummary(
                id="review-1",
                task_id="task-1",
                status=ReviewStatus.SUCCEEDED,
                executor_type=ExecutorType.CODEX_CLI,
                feedback_count=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                created_at=datetime.utcnow(),
            ),
            ReviewSummary(
                id="review-2",
                task_id="task-1",
                status=ReviewStatus.SUCCEEDED,
                executor_type=ExecutorType.CODEX_CLI,
                feedback_count=0,
                critical_count=0,
                high_count=0,
                medium_count=0,
                low_count=0,
                created_at=datetime.utcnow(),
            ),
        ]

        # Return full Review objects from get()
        review_1 = Review(
            id="review-1",
            task_id="task-1",
            target_run_ids=["run-1"],
            executor_type=ExecutorType.CODEX_CLI,
            model_id=None,
            model_name=None,
            status=ReviewStatus.SUCCEEDED,
            overall_summary="Good code",
            overall_score=0.85,
            logs=[],
            error=None,
            feedbacks=[],
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )
        review_2 = Review(
            id="review-2",
            task_id="task-1",
            target_run_ids=["run-1"],
            executor_type=ExecutorType.CODEX_CLI,
            model_id=None,
            model_name=None,
            status=ReviewStatus.SUCCEEDED,
            overall_summary="Needs work",
            overall_score=0.4,
            logs=[],
            error=None,
            feedbacks=[],
            created_at=datetime.utcnow(),
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
        )

        def get_review(review_id: str) -> Review | None:
            return {"review-1": review_1, "review-2": review_2}.get(review_id)

        mock_review_dao.get.side_effect = get_review

        review = await evidence_service.collect_review_evidence("task-1", "run-1")

        assert review is not None
        assert review.approvals == 1  # Score >= 0.75
        assert review.change_requests == 1  # Score < 0.5

    @pytest.mark.asyncio
    async def test_collect_review_evidence_no_reviews(
        self,
        evidence_service: EvidenceService,
        mock_review_dao: AsyncMock,
    ) -> None:
        """Test review evidence when no reviews exist."""
        mock_review_dao.list_by_task.return_value = []

        review = await evidence_service.collect_review_evidence("task-1", "run-1")
        assert review is None


class TestRefsEvidence:
    """Tests for reference URL evidence collection."""

    def test_collect_refs_evidence(self, evidence_service: EvidenceService) -> None:
        """Test refs evidence collection."""
        refs = evidence_service.collect_refs_evidence(
            pr_url="https://github.com/org/repo/pull/123",
            ci_url="https://github.com/org/repo/actions/runs/456",
        )

        assert refs is not None
        assert refs.pr_url == "https://github.com/org/repo/pull/123"
        assert refs.ci_url == "https://github.com/org/repo/actions/runs/456"

    def test_collect_refs_evidence_empty(self, evidence_service: EvidenceService) -> None:
        """Test refs evidence with no URLs."""
        refs = evidence_service.collect_refs_evidence(None, None)
        assert refs is None


class TestBuildEvidence:
    """Tests for building complete evidence."""

    @pytest.mark.asyncio
    async def test_build_evidence(
        self,
        evidence_service: EvidenceService,
        mock_ci_check_dao: AsyncMock,
        mock_review_dao: AsyncMock,
    ) -> None:
        """Test building complete evidence structure."""
        mock_ci_check_dao.get_latest_by_pr_id.return_value = None
        mock_review_dao.list_by_task.return_value = []

        run = create_mock_run()
        evidence = await evidence_service.build_evidence(
            run, "task-1", pr_url="https://github.com/org/repo/pull/123"
        )

        assert evidence.metrics is not None
        assert evidence.metrics.files_changed == 2
        assert evidence.refs is not None
        assert evidence.refs.pr_url == "https://github.com/org/repo/pull/123"
