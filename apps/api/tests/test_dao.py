"""Tests for Data Access Objects (DAOs) - data integrity layer."""

from __future__ import annotations

import pytest

from tazuna_api.domain.enums import (
    ExecutorType,
    MessageRole,
    Provider,
    RunStatus,
)
from tazuna_api.storage.dao import (
    MessageDAO,
    ModelProfileDAO,
    RepoDAO,
    RunDAO,
    TaskDAO,
)
from tazuna_api.storage.db import Database


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
