"""Tests for CI check functionality improvements."""

from datetime import datetime, timedelta

import pytest
import pytest_asyncio

from zloth_api.domain.enums import CodingMode
from zloth_api.storage.dao import PRDAO, CICheckDAO, RepoDAO, TaskDAO
from zloth_api.storage.db import Database


@pytest_asyncio.fixture
async def ci_check_dao(test_db: Database) -> CICheckDAO:
    """Create a CICheckDAO instance for testing."""
    return CICheckDAO(test_db)


@pytest_asyncio.fixture
async def task_dao(test_db: Database) -> TaskDAO:
    """Create a TaskDAO instance for testing."""
    return TaskDAO(test_db)


@pytest_asyncio.fixture
async def pr_dao(test_db: Database) -> PRDAO:
    """Create a PRDAO instance for testing."""
    return PRDAO(test_db)


@pytest_asyncio.fixture
async def repo_dao(test_db: Database) -> RepoDAO:
    """Create a RepoDAO instance for testing."""
    return RepoDAO(test_db)


@pytest_asyncio.fixture
async def test_task(task_dao: TaskDAO, repo_dao: RepoDAO) -> str:
    """Create a test task and return its ID."""
    # Create a repo first
    repo = await repo_dao.create(
        repo_url="https://github.com/test/repo",
        default_branch="main",
        latest_commit="abc123",
        workspace_path="/tmp/test",
    )

    # Create a task
    task = await task_dao.create(
        repo_id=repo.id,
        title="Test Task",
        coding_mode=CodingMode.INTERACTIVE,
    )
    return task.id


@pytest_asyncio.fixture
async def test_pr(pr_dao: PRDAO, test_task: str) -> str:
    """Create a test PR and return its ID."""
    pr = await pr_dao.create(
        task_id=test_task,
        number=1,
        url="https://github.com/test/repo/pull/1",
        branch="test-branch",
        title="Test PR",
        body="Test body",
        latest_commit="abc123",
    )
    return pr.id


class TestCICheckDAO:
    """Tests for CICheckDAO."""

    @pytest.mark.asyncio
    async def test_create_ci_check(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test creating a CI check."""
        ci_check = await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="abc123def456",
        )

        assert ci_check.id
        assert ci_check.task_id == test_task
        assert ci_check.pr_id == test_pr
        assert ci_check.status == "pending"
        assert ci_check.sha == "abc123def456"
        assert ci_check.check_count == 0
        assert ci_check.next_check_at is None

    @pytest.mark.asyncio
    async def test_upsert_creates_new(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test that upsert_for_sha creates a new record when none exists."""
        ci_check = await ci_check_dao.upsert_for_sha(
            task_id=test_task,
            pr_id=test_pr,
            sha="sha123",
            status="pending",
            jobs={"job1": "in_progress"},
        )

        assert ci_check.id
        assert ci_check.sha == "sha123"
        assert ci_check.status == "pending"
        assert ci_check.jobs == {"job1": "in_progress"}

    @pytest.mark.asyncio
    async def test_upsert_updates_existing(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test that upsert_for_sha updates existing record with same SHA."""
        # Create initial record
        ci_check1 = await ci_check_dao.upsert_for_sha(
            task_id=test_task,
            pr_id=test_pr,
            sha="sha456",
            status="pending",
            jobs={"job1": "in_progress"},
        )

        # Upsert same SHA with different status
        ci_check2 = await ci_check_dao.upsert_for_sha(
            task_id=test_task,
            pr_id=test_pr,
            sha="sha456",
            status="success",
            jobs={"job1": "success"},
        )

        # Should be same record, updated
        assert ci_check2.id == ci_check1.id
        assert ci_check2.status == "success"
        assert ci_check2.jobs == {"job1": "success"}

    @pytest.mark.asyncio
    async def test_no_duplicate_for_same_sha(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test that we don't create duplicate CI checks for same SHA."""
        # Create first check
        await ci_check_dao.upsert_for_sha(
            task_id=test_task,
            pr_id=test_pr,
            sha="unique_sha",
            status="pending",
        )

        # Create second check with same SHA
        await ci_check_dao.upsert_for_sha(
            task_id=test_task,
            pr_id=test_pr,
            sha="unique_sha",
            status="success",
        )

        # List all checks - should be only 1
        checks = await ci_check_dao.list_by_task_id(test_task)
        sha_checks = [c for c in checks if c.sha == "unique_sha"]
        assert len(sha_checks) == 1

    @pytest.mark.asyncio
    async def test_supersede_pending_except_sha(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test that old pending checks are superseded when new SHA is detected."""
        # Create old pending check
        old_check = await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="old_sha",
        )

        # Create another old pending check without SHA
        old_check_no_sha = await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha=None,
        )

        # Supersede all except new SHA
        count = await ci_check_dao.supersede_pending_except_sha(test_pr, "new_sha")

        # Both old checks should be superseded
        assert count == 2

        # Verify old checks are superseded
        updated_old = await ci_check_dao.get(old_check.id)
        updated_old_no_sha = await ci_check_dao.get(old_check_no_sha.id)

        assert updated_old
        assert updated_old.status == "superseded"
        assert updated_old_no_sha
        assert updated_old_no_sha.status == "superseded"

    @pytest.mark.asyncio
    async def test_list_pending_due_for_check(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test listing pending checks due for polling."""
        # Create pending check with past next_check_at
        past_time = datetime.utcnow() - timedelta(minutes=5)
        await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="sha_due",
            next_check_at=past_time,
        )

        # Create pending check with future next_check_at
        future_time = datetime.utcnow() + timedelta(minutes=5)
        await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="sha_not_due",
            next_check_at=future_time,
        )

        # Create pending check with no next_check_at (should be due)
        await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="sha_no_time",
        )

        # Get pending checks due for polling
        due_checks = await ci_check_dao.list_pending_due_for_check()

        # Should get 2 checks (past and no time)
        due_shas = {c.sha for c in due_checks}
        assert "sha_due" in due_shas
        assert "sha_no_time" in due_shas
        assert "sha_not_due" not in due_shas

    @pytest.mark.asyncio
    async def test_update_next_check_with_increment(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test updating next check time with count increment."""
        # Create check
        ci_check = await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="sha_count",
        )

        assert ci_check.check_count == 0

        # Update with increment
        next_time = datetime.utcnow() + timedelta(seconds=10)
        await ci_check_dao.update_next_check(ci_check.id, next_time, increment_count=True)

        # Verify count incremented
        updated = await ci_check_dao.get(ci_check.id)
        assert updated
        assert updated.check_count == 1

    @pytest.mark.asyncio
    async def test_mark_as_timeout(
        self, ci_check_dao: CICheckDAO, test_task: str, test_pr: str
    ) -> None:
        """Test marking a CI check as timed out."""
        ci_check = await ci_check_dao.create(
            task_id=test_task,
            pr_id=test_pr,
            status="pending",
            sha="sha_timeout",
        )

        # Mark as timeout
        updated = await ci_check_dao.mark_as_timeout(ci_check.id)

        assert updated
        assert updated.status == "timeout"


class TestCICheckStatusDerivation:
    """Tests for CI status derivation logic."""

    def test_derive_success(self) -> None:
        """Test deriving success status."""
        from zloth_api.services.ci_check_service import CICheckService

        # Create minimal service for testing
        service = CICheckService.__new__(CICheckService)

        jobs = {"job1": "success", "job2": "success", "job3": "skipped"}
        status = service._derive_status_from_jobs(jobs)
        assert status == "success"

    def test_derive_failure(self) -> None:
        """Test deriving failure status."""
        from zloth_api.services.ci_check_service import CICheckService

        service = CICheckService.__new__(CICheckService)

        jobs = {"job1": "success", "job2": "failure"}
        status = service._derive_status_from_jobs(jobs)
        assert status == "failure"

    def test_derive_pending(self) -> None:
        """Test deriving pending status."""
        from zloth_api.services.ci_check_service import CICheckService

        service = CICheckService.__new__(CICheckService)

        jobs = {"job1": "success", "job2": "in_progress"}
        status = service._derive_status_from_jobs(jobs)
        assert status == "pending"

    def test_derive_empty_jobs(self) -> None:
        """Test deriving status with no jobs."""
        from zloth_api.services.ci_check_service import CICheckService

        service = CICheckService.__new__(CICheckService)

        status = service._derive_status_from_jobs({})
        assert status == "pending"

    def test_failure_takes_priority(self) -> None:
        """Test that failure takes priority over pending."""
        from zloth_api.services.ci_check_service import CICheckService

        service = CICheckService.__new__(CICheckService)

        jobs = {"job1": "failure", "job2": "in_progress", "job3": "success"}
        status = service._derive_status_from_jobs(jobs)
        assert status == "failure"
