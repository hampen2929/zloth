"""Tests for DecisionDAO."""

from __future__ import annotations

import pytest
import pytest_asyncio

from zloth_api.domain.enums import (
    DeciderType,
    DecisionType,
    OutcomeStatus,
    RiskLevel,
)
from zloth_api.storage.dao import DecisionDAO, RepoDAO, TaskDAO
from zloth_api.storage.db import Database


@pytest_asyncio.fixture
async def decision_dao(test_db: Database) -> DecisionDAO:
    """Create a DecisionDAO instance."""
    return DecisionDAO(test_db)


@pytest_asyncio.fixture
async def task_id(test_db: Database) -> str:
    """Create a task and return its ID."""
    repo_dao = RepoDAO(test_db)
    task_dao = TaskDAO(test_db)

    repo = await repo_dao.create(
        repo_url="https://github.com/test/repo",
        default_branch="main",
        latest_commit="abc123",
        workspace_path="/tmp/test",
    )
    task = await task_dao.create(repo_id=repo.id, title="Test Task")
    return task.id


@pytest.mark.asyncio
async def test_create_selection_decision(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test creating a selection decision."""
    decision = await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.SELECTION,
        decider_type=DeciderType.HUMAN,
        reason="Selected run A for better implementation",
        evidence={"metrics": {"lines_changed": 100, "files_changed": 5}},
        alternatives={
            "rejected_runs": [{"run_id": "run-b", "reason": "Lower quality"}],
            "comparison_axes": ["metrics", "ci_status"],
        },
        # Note: not setting selected_run_id as it requires existing run in DB
        risk_level=RiskLevel.MEDIUM,
        risk_level_reason="Standard code changes",
    )

    assert decision.id is not None
    assert decision.task_id == task_id
    assert decision.decision_type == DecisionType.SELECTION
    assert decision.decider_type == DeciderType.HUMAN
    assert decision.reason == "Selected run A for better implementation"
    assert decision.risk_level == RiskLevel.MEDIUM
    assert decision.outcome is None


@pytest.mark.asyncio
async def test_create_promotion_decision(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test creating a promotion decision."""
    decision = await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.PROMOTION,
        decider_type=DeciderType.HUMAN,
        reason="Ready for review",
        evidence={"metrics": {"lines_changed": 50, "files_changed": 3}},
        scope={
            "included_paths": ["src/main.py", "src/utils.py"],
            "excluded_paths": ["test_data.json"],
            "excluded_reasons": [{"path": "test_data.json", "reason": "Test fixture"}],
        },
        # Note: not setting selected_run_id/pr_id as they require existing records
        risk_level=RiskLevel.LOW,
        risk_level_reason="Documentation only",
    )

    assert decision.decision_type == DecisionType.PROMOTION
    assert decision.scope is not None
    assert "included_paths" in decision.scope


@pytest.mark.asyncio
async def test_create_merge_decision(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test creating a merge decision."""
    decision = await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.MERGE,
        decider_type=DeciderType.HUMAN,
        reason="All checks passed, reviewed and approved",
        evidence={
            "ci_results": {"status": "passed", "check_names": ["build", "test"]},
            "review_summary": {"approvals": 2, "change_requests": 0},
        },
        # Note: not setting pr_id as it requires existing PR record
        risk_level=RiskLevel.MEDIUM,
        risk_level_reason="Standard code changes",
    )

    assert decision.decision_type == DecisionType.MERGE


@pytest.mark.asyncio
async def test_get_decision(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test getting a decision by ID."""
    created = await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.SELECTION,
        decider_type=DeciderType.HUMAN,
        reason="Test reason",
        evidence={},
    )

    fetched = await decision_dao.get(created.id)
    assert fetched is not None
    assert fetched.id == created.id
    assert fetched.reason == "Test reason"


@pytest.mark.asyncio
async def test_get_nonexistent_decision(decision_dao: DecisionDAO) -> None:
    """Test getting a nonexistent decision."""
    result = await decision_dao.get("nonexistent-id")
    assert result is None


@pytest.mark.asyncio
async def test_list_decisions_by_task(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test listing decisions for a task."""
    # Create multiple decisions
    await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.SELECTION,
        decider_type=DeciderType.HUMAN,
        reason="First decision",
        evidence={},
    )
    await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.PROMOTION,
        decider_type=DeciderType.HUMAN,
        reason="Second decision",
        evidence={},
    )

    decisions = await decision_dao.list(task_id)
    assert len(decisions) == 2
    # Should be ordered by created_at ASC
    assert decisions[0].reason == "First decision"
    assert decisions[1].reason == "Second decision"


@pytest.mark.asyncio
async def test_list_decisions_by_type(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test filtering decisions by type."""
    await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.SELECTION,
        decider_type=DeciderType.HUMAN,
        reason="Selection",
        evidence={},
    )
    await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.PROMOTION,
        decider_type=DeciderType.HUMAN,
        reason="Promotion",
        evidence={},
    )

    selections = await decision_dao.list_by_type(task_id, DecisionType.SELECTION)
    assert len(selections) == 1
    assert selections[0].decision_type == DecisionType.SELECTION


@pytest.mark.asyncio
async def test_update_outcome(decision_dao: DecisionDAO, task_id: str) -> None:
    """Test updating decision outcome."""
    created = await decision_dao.create(
        task_id=task_id,
        decision_type=DecisionType.SELECTION,
        decider_type=DeciderType.HUMAN,
        reason="Test",
        evidence={},
    )

    updated = await decision_dao.update_outcome(
        decision_id=created.id,
        outcome=OutcomeStatus.GOOD,
        reason="The decision led to successful merge",
        refs=["https://github.com/org/repo/pull/123"],
    )

    assert updated is not None
    assert updated.outcome == OutcomeStatus.GOOD
    assert updated.outcome_reason == "The decision led to successful merge"
    assert updated.outcome_refs == ["https://github.com/org/repo/pull/123"]


@pytest.mark.asyncio
async def test_update_outcome_nonexistent(decision_dao: DecisionDAO) -> None:
    """Test updating outcome for nonexistent decision."""
    result = await decision_dao.update_outcome(
        decision_id="nonexistent",
        outcome=OutcomeStatus.BAD,
        reason="Test",
        refs=[],
    )
    assert result is None
