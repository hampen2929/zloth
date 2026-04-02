"""Tests for AI Task Creator service."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zloth_api.domain.enums import BreakdownStatus, CodingMode, ExecutorType
from zloth_api.domain.models import (
    AICreatedTask,
    AITaskCreateRequest,
    AITaskCreateResponse,
)
from zloth_api.services.ai_task_creator import (
    AI_TASKS_RESULT_FILE,
    AITaskCreatorService,
)
from zloth_api.services.output_manager import OutputManager
from zloth_api.storage.dao import MessageDAO, RepoDAO, TaskDAO


@pytest.fixture
def mock_repo_dao() -> AsyncMock:
    """Create a mock RepoDAO."""
    dao = AsyncMock(spec=RepoDAO)
    dao.get = AsyncMock()
    return dao


@pytest.fixture
def mock_task_dao() -> AsyncMock:
    """Create a mock TaskDAO."""
    dao = AsyncMock(spec=TaskDAO)
    dao.create = AsyncMock()
    return dao


@pytest.fixture
def mock_message_dao() -> AsyncMock:
    """Create a mock MessageDAO."""
    dao = AsyncMock(spec=MessageDAO)
    dao.create = AsyncMock()
    return dao


@pytest.fixture
def mock_output_manager() -> MagicMock:
    """Create a mock OutputManager."""
    manager = MagicMock(spec=OutputManager)
    manager.publish_async = AsyncMock()
    manager.mark_complete = AsyncMock()
    manager.get_history = AsyncMock(return_value=[])
    manager.is_complete = AsyncMock(return_value=False)
    return manager


@pytest.fixture
def service(
    mock_repo_dao: AsyncMock,
    mock_task_dao: AsyncMock,
    mock_message_dao: AsyncMock,
    mock_output_manager: MagicMock,
) -> AITaskCreatorService:
    """Create AITaskCreatorService with mocked dependencies."""
    return AITaskCreatorService(
        repo_dao=mock_repo_dao,
        task_dao=mock_task_dao,
        message_dao=mock_message_dao,
        output_manager=mock_output_manager,
    )


class TestAITaskCreatorService:
    """Tests for AITaskCreatorService."""

    @pytest.mark.asyncio
    async def test_start_returns_running_status(
        self,
        service: AITaskCreatorService,
        mock_repo_dao: AsyncMock,
    ) -> None:
        """Test that start() returns RUNNING status immediately."""
        mock_repo = MagicMock()
        mock_repo.id = "repo-1"
        mock_repo.workspace_path = "/tmp/workspace"
        mock_repo.repo_url = "https://github.com/test/repo"
        mock_repo_dao.get.return_value = mock_repo

        request = AITaskCreateRequest(
            repo_id="repo-1",
            instruction="Add authentication",
            executor_type=ExecutorType.CLAUDE_CODE,
            coding_mode=CodingMode.SEMI_AUTO,
        )

        # Patch the executor to avoid actual execution
        with patch.object(service, "_run", new_callable=AsyncMock):
            result = await service.start(request)

        assert result.status == BreakdownStatus.RUNNING
        assert result.session_id
        assert result.created_tasks == []

    @pytest.mark.asyncio
    async def test_start_repo_not_found(
        self,
        service: AITaskCreatorService,
        mock_repo_dao: AsyncMock,
    ) -> None:
        """Test that start() returns FAILED when repo not found."""
        mock_repo_dao.get.return_value = None

        request = AITaskCreateRequest(
            repo_id="nonexistent",
            instruction="Test",
        )

        result = await service.start(request)

        assert result.status == BreakdownStatus.FAILED
        assert "not found" in (result.error or "")

    @pytest.mark.asyncio
    async def test_get_result_returns_none_for_unknown_session(
        self,
        service: AITaskCreatorService,
    ) -> None:
        """Test that get_result() returns None for unknown session."""
        result = await service.get_result("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_logs(
        self,
        service: AITaskCreatorService,
        mock_output_manager: MagicMock,
    ) -> None:
        """Test that get_logs() returns correct format."""
        mock_output_manager.get_history.return_value = []
        mock_output_manager.is_complete.return_value = True

        logs, is_complete = await service.get_logs("session-1")

        assert logs == []
        assert is_complete is True

    def test_get_executor_rejects_patch_agent(
        self,
        service: AITaskCreatorService,
    ) -> None:
        """Test that patch_agent is rejected."""
        with pytest.raises(ValueError, match="patch_agent"):
            service._get_executor(ExecutorType.PATCH_AGENT)

    def test_get_executor_returns_claude(
        self,
        service: AITaskCreatorService,
    ) -> None:
        """Test that claude_code executor is returned."""
        executor = service._get_executor(ExecutorType.CLAUDE_CODE)
        assert executor is not None

    def test_get_executor_returns_codex(
        self,
        service: AITaskCreatorService,
    ) -> None:
        """Test that codex_cli executor is returned."""
        executor = service._get_executor(ExecutorType.CODEX_CLI)
        assert executor is not None

    def test_get_executor_returns_gemini(
        self,
        service: AITaskCreatorService,
    ) -> None:
        """Test that gemini_cli executor is returned."""
        executor = service._get_executor(ExecutorType.GEMINI_CLI)
        assert executor is not None


class TestJSONParsing:
    """Tests for JSON result parsing."""

    @pytest.fixture
    def service(
        self,
        mock_repo_dao: AsyncMock,
        mock_task_dao: AsyncMock,
        mock_message_dao: AsyncMock,
        mock_output_manager: MagicMock,
    ) -> AITaskCreatorService:
        """Create service for parsing tests."""
        return AITaskCreatorService(
            repo_dao=mock_repo_dao,
            task_dao=mock_task_dao,
            message_dao=mock_message_dao,
            output_manager=mock_output_manager,
        )

    def test_parse_json_data_valid(self, service: AITaskCreatorService) -> None:
        """Test parsing valid JSON data."""
        data: dict[str, Any] = {
            "codebase_analysis": {
                "files_analyzed": 30,
                "relevant_modules": ["auth"],
                "tech_stack": ["FastAPI"],
            },
            "tasks": [
                {
                    "title": "Add login",
                    "instruction": "Implement login endpoint",
                },
                {
                    "title": "Add logout",
                    "instruction": "Implement logout endpoint",
                },
            ],
        }

        tasks, analysis = service._parse_json_data(data)

        assert len(tasks) == 2
        assert tasks[0]["title"] == "Add login"
        assert tasks[1]["title"] == "Add logout"
        assert analysis is not None
        assert analysis.files_analyzed == 30

    def test_parse_json_data_empty_tasks(self, service: AITaskCreatorService) -> None:
        """Test parsing with empty tasks list."""
        data: dict[str, Any] = {"tasks": []}

        tasks, analysis = service._parse_json_data(data)

        assert len(tasks) == 0
        assert analysis is None

    def test_parse_json_data_no_tasks_key(self, service: AITaskCreatorService) -> None:
        """Test parsing with missing tasks key."""
        data: dict[str, Any] = {"codebase_analysis": {"files_analyzed": 10}}

        tasks, analysis = service._parse_json_data(data)

        assert len(tasks) == 0

    def test_parse_json_data_invalid_task_entries(self, service: AITaskCreatorService) -> None:
        """Test parsing with invalid task entries (missing title)."""
        data: dict[str, Any] = {
            "tasks": [
                {"title": "Valid task", "instruction": "Do something"},
                {"instruction": "No title"},  # Missing title
                "not a dict",  # Invalid type
            ]
        }

        tasks, analysis = service._parse_json_data(data)

        assert len(tasks) == 1
        assert tasks[0]["title"] == "Valid task"

    def test_extract_json_from_logs_code_fence(self, service: AITaskCreatorService) -> None:
        """Test extracting JSON from markdown code fence in logs."""
        logs = [
            "Analyzing codebase...",
            "```json",
            '{"tasks": [{"title": "Test task", "instruction": "Do test"}]}',
            "```",
        ]

        result = service._extract_json_from_logs(logs)

        assert result is not None
        assert "tasks" in result

    def test_extract_json_from_logs_no_json(self, service: AITaskCreatorService) -> None:
        """Test extraction returns None when no JSON found."""
        logs = ["No JSON here", "Just text"]

        result = service._extract_json_from_logs(logs)

        assert result is None

    def test_parse_result_from_file(self, service: AITaskCreatorService, tmp_path: Path) -> None:
        """Test parsing result from file."""
        result_file = tmp_path / AI_TASKS_RESULT_FILE
        data = {
            "tasks": [
                {"title": "Task 1", "instruction": "Do task 1"},
            ]
        }
        result_file.write_text(json.dumps(data))

        result = service._parse_result(result_file, [])

        assert result is not None
        tasks, _ = result
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Task 1"

    def test_parse_result_fallback_to_logs(
        self, service: AITaskCreatorService, tmp_path: Path
    ) -> None:
        """Test parsing falls back to logs when file doesn't exist."""
        result_file = tmp_path / "nonexistent.json"
        logs = [
            '```json\n{"tasks": [{"title": "From logs"}]}\n```',
        ]

        result = service._parse_result(result_file, logs)

        assert result is not None
        tasks, _ = result
        assert len(tasks) == 1
        assert tasks[0]["title"] == "From logs"

    def test_parse_result_returns_none_on_failure(
        self, service: AITaskCreatorService, tmp_path: Path
    ) -> None:
        """Test parsing returns None when nothing is parseable."""
        result_file = tmp_path / "nonexistent.json"

        result = service._parse_result(result_file, ["no json here"])

        assert result is None


class TestDomainModels:
    """Tests for AI task creation domain models."""

    def test_ai_task_create_request_defaults(self) -> None:
        """Test AITaskCreateRequest default values."""
        request = AITaskCreateRequest(
            repo_id="repo-1",
            instruction="Build something",
        )

        assert request.executor_type == ExecutorType.CLAUDE_CODE
        assert request.coding_mode == CodingMode.SEMI_AUTO
        assert request.auto_start is False
        assert request.context is None

    def test_ai_task_create_response_defaults(self) -> None:
        """Test AITaskCreateResponse default values."""
        response = AITaskCreateResponse(
            session_id="session-1",
            status=BreakdownStatus.RUNNING,
        )

        assert response.created_tasks == []
        assert response.summary is None
        assert response.codebase_analysis is None
        assert response.error is None

    def test_ai_created_task(self) -> None:
        """Test AICreatedTask model."""
        task = AICreatedTask(
            id="task-1",
            title="Login feature",
            instruction="Implement JWT login",
            coding_mode=CodingMode.SEMI_AUTO,
            auto_started=True,
        )

        assert task.id == "task-1"
        assert task.auto_started is True
