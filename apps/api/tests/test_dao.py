"""Tests for Data Access Objects (DAOs) - data integrity layer."""

from __future__ import annotations

import pytest

from zloth_api.domain.enums import (
    ExecutorType,
    MessageRole,
    Provider,
    RunStatus,
)
from zloth_api.storage.dao import (
    AgenticRunDAO,
    BacklogDAO,
    CICheckDAO,
    MessageDAO,
    ModelProfileDAO,
    RepoDAO,
    ReviewDAO,
    RunDAO,
    TaskDAO,
)
from zloth_api.storage.db import Database


class TestModelProfileDAO:
    """Test suite for ModelProfileDAO."""

    @pytest.fixture
    def dao(self, test_db: Database) -> ModelProfileDAO:
        """Create ModelProfileDAO instance."""
        return ModelProfileDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get(self, dao: ModelProfileDAO) -> None:
        """Test creating and retrieving a model profile."""
        profile = await dao.create(
            provider=Provider.OPENAI,
            model_name="gpt-4o",
            api_key_encrypted="encrypted-key-123",
            display_name="GPT-4o Test",
        )

        assert profile.id is not None
        assert profile.provider == Provider.OPENAI
        assert profile.model_name == "gpt-4o"
        assert profile.display_name == "GPT-4o Test"

        # Retrieve and verify
        retrieved = await dao.get(profile.id)
        assert retrieved is not None
        assert retrieved.id == profile.id
        assert retrieved.provider == profile.provider
        assert retrieved.model_name == profile.model_name

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, dao: ModelProfileDAO) -> None:
        """Test that getting a nonexistent profile returns None."""
        result = await dao.get("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_profiles(self, dao: ModelProfileDAO) -> None:
        """Test listing all model profiles."""
        # Create multiple profiles
        await dao.create(
            provider=Provider.OPENAI,
            model_name="gpt-4o",
            api_key_encrypted="key1",
        )
        await dao.create(
            provider=Provider.ANTHROPIC,
            model_name="claude-3-opus",
            api_key_encrypted="key2",
        )

        profiles = await dao.list()
        assert len(profiles) >= 2

    @pytest.mark.asyncio
    async def test_delete_profile(self, dao: ModelProfileDAO) -> None:
        """Test deleting a model profile."""
        profile = await dao.create(
            provider=Provider.GOOGLE,
            model_name="gemini-pro",
            api_key_encrypted="key",
        )

        deleted = await dao.delete(profile.id)
        assert deleted is True

        # Verify deletion
        retrieved = await dao.get(profile.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_returns_false(self, dao: ModelProfileDAO) -> None:
        """Test that deleting a nonexistent profile returns False."""
        deleted = await dao.delete("nonexistent-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_encrypted_key(self, dao: ModelProfileDAO) -> None:
        """Test retrieving encrypted API key."""
        encrypted_key = "encrypted-api-key-secret"
        profile = await dao.create(
            provider=Provider.OPENAI,
            model_name="gpt-4o",
            api_key_encrypted=encrypted_key,
        )

        retrieved_key = await dao.get_encrypted_key(profile.id)
        assert retrieved_key == encrypted_key


class TestRepoDAO:
    """Test suite for RepoDAO."""

    @pytest.fixture
    def dao(self, test_db: Database) -> RepoDAO:
        """Create RepoDAO instance."""
        return RepoDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get(self, dao: RepoDAO) -> None:
        """Test creating and retrieving a repository."""
        repo = await dao.create(
            repo_url="https://github.com/test/repo",
            default_branch="main",
            latest_commit="abc123",
            workspace_path="/workspaces/test",
        )

        assert repo.id is not None
        assert repo.repo_url == "https://github.com/test/repo"
        assert repo.default_branch == "main"
        assert repo.latest_commit == "abc123"

        # Retrieve and verify
        retrieved = await dao.get(repo.id)
        assert retrieved is not None
        assert retrieved.id == repo.id
        assert retrieved.repo_url == repo.repo_url

    @pytest.mark.asyncio
    async def test_find_by_url(self, dao: RepoDAO) -> None:
        """Test finding repository by URL."""
        repo_url = "https://github.com/unique/repo"
        await dao.create(
            repo_url=repo_url,
            default_branch="main",
            latest_commit="def456",
            workspace_path="/workspaces/unique",
        )

        found = await dao.find_by_url(repo_url)
        assert found is not None
        assert found.repo_url == repo_url

    @pytest.mark.asyncio
    async def test_find_by_url_not_found(self, dao: RepoDAO) -> None:
        """Test finding repository by URL that doesn't exist."""
        found = await dao.find_by_url("https://github.com/nonexistent/repo")
        assert found is None

    @pytest.mark.asyncio
    async def test_update_selected_branch(self, dao: RepoDAO) -> None:
        """Test updating selected branch."""
        repo = await dao.create(
            repo_url="https://github.com/test/branch",
            default_branch="main",
            latest_commit="ghi789",
            workspace_path="/workspaces/branch",
        )

        await dao.update_selected_branch(repo.id, "feature-branch")

        updated = await dao.get(repo.id)
        assert updated is not None
        assert updated.selected_branch == "feature-branch"


class TestTaskDAO:
    """Test suite for TaskDAO."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        """Create RepoDAO instance."""
        return RepoDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> TaskDAO:
        """Create TaskDAO instance."""
        return TaskDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get(self, dao: TaskDAO, repo_dao: RepoDAO) -> None:
        """Test creating and retrieving a task."""
        # Create a repo first
        repo = await repo_dao.create(
            repo_url="https://github.com/test/task-repo",
            default_branch="main",
            latest_commit="jkl012",
            workspace_path="/workspaces/task",
        )

        task = await dao.create(repo_id=repo.id, title="Test Task")

        assert task.id is not None
        assert task.repo_id == repo.id
        assert task.title == "Test Task"

        # Retrieve and verify
        retrieved = await dao.get(task.id)
        assert retrieved is not None
        assert retrieved.id == task.id
        assert retrieved.title == task.title

    @pytest.mark.asyncio
    async def test_update_title(self, dao: TaskDAO, repo_dao: RepoDAO) -> None:
        """Test updating task title."""
        repo = await repo_dao.create(
            repo_url="https://github.com/test/title-repo",
            default_branch="main",
            latest_commit="mno345",
            workspace_path="/workspaces/title",
        )

        task = await dao.create(repo_id=repo.id, title="Original Title")
        await dao.update_title(task.id, "Updated Title")

        updated = await dao.get(task.id)
        assert updated is not None
        assert updated.title == "Updated Title"

    @pytest.mark.asyncio
    async def test_list_by_repo(self, dao: TaskDAO, repo_dao: RepoDAO) -> None:
        """Test listing tasks by repository."""
        repo1 = await repo_dao.create(
            repo_url="https://github.com/test/repo1",
            default_branch="main",
            latest_commit="pqr678",
            workspace_path="/workspaces/repo1",
        )
        repo2 = await repo_dao.create(
            repo_url="https://github.com/test/repo2",
            default_branch="main",
            latest_commit="stu901",
            workspace_path="/workspaces/repo2",
        )

        await dao.create(repo_id=repo1.id, title="Task 1")
        await dao.create(repo_id=repo1.id, title="Task 2")
        await dao.create(repo_id=repo2.id, title="Task 3")

        tasks_repo1 = await dao.list(repo_id=repo1.id)
        assert len(tasks_repo1) == 2

        tasks_repo2 = await dao.list(repo_id=repo2.id)
        assert len(tasks_repo2) == 1


class TestMessageDAO:
    """Test suite for MessageDAO."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        """Create RepoDAO instance."""
        return RepoDAO(test_db)

    @pytest.fixture
    def task_dao(self, test_db: Database) -> TaskDAO:
        """Create TaskDAO instance."""
        return TaskDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> MessageDAO:
        """Create MessageDAO instance."""
        return MessageDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_list(
        self, dao: MessageDAO, task_dao: TaskDAO, repo_dao: RepoDAO
    ) -> None:
        """Test creating and listing messages."""
        repo = await repo_dao.create(
            repo_url="https://github.com/test/msg-repo",
            default_branch="main",
            latest_commit="vwx234",
            workspace_path="/workspaces/msg",
        )
        task = await task_dao.create(repo_id=repo.id, title="Message Task")

        # Create messages
        msg1 = await dao.create(task_id=task.id, role=MessageRole.USER, content="Hello")
        msg2 = await dao.create(task_id=task.id, role=MessageRole.ASSISTANT, content="Hi there!")

        assert msg1.role == MessageRole.USER
        assert msg2.role == MessageRole.ASSISTANT

        # List messages
        messages = await dao.list(task_id=task.id)
        assert len(messages) == 2
        # Should be ordered by created_at ASC
        assert messages[0].content == "Hello"
        assert messages[1].content == "Hi there!"


class TestRunDAO:
    """Test suite for RunDAO."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        """Create RepoDAO instance."""
        return RepoDAO(test_db)

    @pytest.fixture
    def task_dao(self, test_db: Database) -> TaskDAO:
        """Create TaskDAO instance."""
        return TaskDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> RunDAO:
        """Create RunDAO instance."""
        return RunDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get(self, dao: RunDAO, task_dao: TaskDAO, repo_dao: RepoDAO) -> None:
        """Test creating and retrieving a run."""
        repo = await repo_dao.create(
            repo_url="https://github.com/test/run-repo",
            default_branch="main",
            latest_commit="yza567",
            workspace_path="/workspaces/run",
        )
        task = await task_dao.create(repo_id=repo.id, title="Run Task")

        run = await dao.create(
            task_id=task.id,
            instruction="Fix the bug",
            executor_type=ExecutorType.CLAUDE_CODE,
            model_name="claude-3-opus",
            provider=Provider.ANTHROPIC,
        )

        assert run.id is not None
        assert run.task_id == task.id
        assert run.instruction == "Fix the bug"
        assert run.status == RunStatus.QUEUED
        assert run.executor_type == ExecutorType.CLAUDE_CODE

        # Retrieve and verify
        retrieved = await dao.get(run.id)
        assert retrieved is not None
        assert retrieved.id == run.id
        assert retrieved.instruction == run.instruction

    @pytest.mark.asyncio
    async def test_update_status(self, dao: RunDAO, task_dao: TaskDAO, repo_dao: RepoDAO) -> None:
        """Test updating run status."""
        repo = await repo_dao.create(
            repo_url="https://github.com/test/status-repo",
            default_branch="main",
            latest_commit="bcd890",
            workspace_path="/workspaces/status",
        )
        task = await task_dao.create(repo_id=repo.id, title="Status Task")

        run = await dao.create(
            task_id=task.id,
            instruction="Update status test",
            executor_type=ExecutorType.PATCH_AGENT,
        )

        # Update to running
        await dao.update_status(run.id, RunStatus.RUNNING)
        updated = await dao.get(run.id)
        assert updated is not None
        assert updated.status == RunStatus.RUNNING
        assert updated.started_at is not None

        # Update to succeeded with results
        await dao.update_status(
            run.id,
            RunStatus.SUCCEEDED,
            summary="Fixed the issue",
            patch="--- a/file.py\n+++ b/file.py\n",
        )
        completed = await dao.get(run.id)
        assert completed is not None
        assert completed.status == RunStatus.SUCCEEDED
        assert completed.summary == "Fixed the issue"
        assert completed.completed_at is not None

    @pytest.mark.asyncio
    async def test_update_status_with_error(
        self, dao: RunDAO, task_dao: TaskDAO, repo_dao: RepoDAO
    ) -> None:
        """Test updating run status with error."""
        repo = await repo_dao.create(
            repo_url="https://github.com/test/error-repo",
            default_branch="main",
            latest_commit="efg123",
            workspace_path="/workspaces/error",
        )
        task = await task_dao.create(repo_id=repo.id, title="Error Task")

        run = await dao.create(
            task_id=task.id,
            instruction="Will fail",
            executor_type=ExecutorType.PATCH_AGENT,
        )

        await dao.update_status(run.id, RunStatus.FAILED, error="Something went wrong")
        failed = await dao.get(run.id)
        assert failed is not None
        assert failed.status == RunStatus.FAILED
        assert failed.error == "Something went wrong"

    @pytest.mark.asyncio
    async def test_list_runs_by_task(
        self, dao: RunDAO, task_dao: TaskDAO, repo_dao: RepoDAO
    ) -> None:
        """Test listing runs by task."""
        repo = await repo_dao.create(
            repo_url="https://github.com/test/list-repo",
            default_branch="main",
            latest_commit="hij456",
            workspace_path="/workspaces/list",
        )
        task = await task_dao.create(repo_id=repo.id, title="List Task")

        # Create multiple runs
        await dao.create(
            task_id=task.id,
            instruction="Run 1",
            executor_type=ExecutorType.CLAUDE_CODE,
        )
        await dao.create(
            task_id=task.id,
            instruction="Run 2",
            executor_type=ExecutorType.CODEX_CLI,
        )

        runs = await dao.list(task_id=task.id)
        assert len(runs) == 2


class TestBacklogDAO:
    """Test suite for BacklogDAO (JSON field decoding)."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        return RepoDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> BacklogDAO:
        return BacklogDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get_decodes_json_fields(
        self, dao: BacklogDAO, repo_dao: RepoDAO
    ) -> None:
        repo = await repo_dao.create(
            repo_url="https://github.com/test/backlog-repo",
            default_branch="main",
            latest_commit="aaa111",
            workspace_path="/workspaces/backlog",
        )

        item = await dao.create(
            repo_id=repo.id,
            title="Backlog Item",
            target_files=["a.py", "b.py"],
            tags=["refactor", "dao"],
            subtasks=[{"title": "step 1"}, {"title": "step 2"}],
        )

        retrieved = await dao.get(item.id)
        assert retrieved is not None
        assert retrieved.id == item.id
        assert retrieved.target_files == ["a.py", "b.py"]
        assert retrieved.tags == ["refactor", "dao"]
        assert len(retrieved.subtasks) == 2
        assert retrieved.subtasks[0].title == "step 1"


class TestCICheckDAO:
    """Test suite for CICheckDAO (JSON field decoding)."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        return RepoDAO(test_db)

    @pytest.fixture
    def task_dao(self, test_db: Database) -> TaskDAO:
        return TaskDAO(test_db)

    @pytest.fixture
    def pr_dao(self, test_db: Database):
        from zloth_api.storage.dao import PRDAO

        return PRDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> CICheckDAO:
        return CICheckDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get_decodes_json_fields(
        self, dao: CICheckDAO, repo_dao: RepoDAO, task_dao: TaskDAO, pr_dao
    ) -> None:
        repo = await repo_dao.create(
            repo_url="https://github.com/test/ci-repo",
            default_branch="main",
            latest_commit="bbb222",
            workspace_path="/workspaces/ci",
        )
        task = await task_dao.create(repo_id=repo.id, title="CI Task")
        pr = await pr_dao.create(
            task_id=task.id,
            number=1,
            url="https://github.com/test/ci-repo/pull/1",
            branch="test-branch",
            title="PR",
            body=None,
            latest_commit="sha123",
        )

        created = await dao.create(
            task_id=task.id,
            pr_id=pr.id,
            status="pending",
            jobs={"lint": "success"},
            failed_jobs=[],
        )

        retrieved = await dao.get(created.id)
        assert retrieved is not None
        assert retrieved.jobs == {"lint": "success"}
        assert retrieved.failed_jobs == []


class TestReviewDAO:
    """Test suite for ReviewDAO (JSON field decoding + join)."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        return RepoDAO(test_db)

    @pytest.fixture
    def task_dao(self, test_db: Database) -> TaskDAO:
        return TaskDAO(test_db)

    @pytest.fixture
    def run_dao(self, test_db: Database) -> RunDAO:
        return RunDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> ReviewDAO:
        return ReviewDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get_decodes_json_fields(
        self, dao: ReviewDAO, repo_dao: RepoDAO, task_dao: TaskDAO, run_dao: RunDAO
    ) -> None:
        from datetime import datetime

        from zloth_api.domain.enums import ReviewStatus
        from zloth_api.domain.models import Review
        from zloth_api.storage.dao import generate_id

        repo = await repo_dao.create(
            repo_url="https://github.com/test/review-repo",
            default_branch="main",
            latest_commit="ccc333",
            workspace_path="/workspaces/review",
        )
        task = await task_dao.create(repo_id=repo.id, title="Review Task")
        run = await run_dao.create(
            task_id=task.id, instruction="Do thing", executor_type=ExecutorType.PATCH_AGENT
        )

        review = Review(
            id=generate_id(),
            task_id=task.id,
            target_run_ids=[run.id],
            executor_type=ExecutorType.CLAUDE_CODE,
            model_id=None,
            model_name=None,
            status=ReviewStatus.QUEUED,
            created_at=datetime.utcnow(),
        )
        await dao.create(review)

        retrieved = await dao.get(review.id)
        assert retrieved is not None
        assert retrieved.target_run_ids == [run.id]
        assert retrieved.logs == []
        assert retrieved.feedbacks == []


class TestAgenticRunDAO:
    """Test suite for AgenticRunDAO (JSON field decoding)."""

    @pytest.fixture
    def repo_dao(self, test_db: Database) -> RepoDAO:
        return RepoDAO(test_db)

    @pytest.fixture
    def task_dao(self, test_db: Database) -> TaskDAO:
        return TaskDAO(test_db)

    @pytest.fixture
    def dao(self, test_db: Database) -> AgenticRunDAO:
        return AgenticRunDAO(test_db)

    @pytest.mark.asyncio
    async def test_create_and_get_decodes_last_ci_result(
        self, dao: AgenticRunDAO, repo_dao: RepoDAO, task_dao: TaskDAO
    ) -> None:
        from datetime import datetime

        from zloth_api.domain.enums import AgenticPhase, CodingMode
        from zloth_api.domain.models import AgenticState, CIJobResult, CIResult
        from zloth_api.storage.dao import generate_id

        repo = await repo_dao.create(
            repo_url="https://github.com/test/agentic-repo",
            default_branch="main",
            latest_commit="ddd444",
            workspace_path="/workspaces/agentic",
        )
        task = await task_dao.create(repo_id=repo.id, title="Agentic Task")

        ci_result = CIResult(
            success=True,
            workflow_run_id=123,
            sha="sha-ci",
            jobs={"test": "success"},
            failed_jobs=[CIJobResult(job_name="x", result="skipped")],
        )
        state = AgenticState(
            id=generate_id(),
            task_id=task.id,
            mode=CodingMode.INTERACTIVE,
            phase=AgenticPhase.CODING,
            iteration=1,
            ci_iterations=0,
            review_iterations=0,
            started_at=datetime.utcnow(),
            last_activity=datetime.utcnow(),
            pr_number=None,
            current_sha=None,
            last_ci_result=ci_result,
            last_review_score=None,
            error=None,
            human_approved=False,
        )
        await dao.create(state)

        retrieved = await dao.get(state.id)
        assert retrieved is not None
        assert retrieved.last_ci_result is not None
        assert retrieved.last_ci_result.workflow_run_id == 123
