"""Tests for domain enums."""

from dursor_api.domain.enums import (
    ExecutorType,
    MessageRole,
    PRCreationMode,
    Provider,
    RunStatus,
)


def test_provider_values() -> None:
    """Test Provider enum has expected values."""
    assert Provider.OPENAI.value == "openai"
    assert Provider.ANTHROPIC.value == "anthropic"
    assert Provider.GOOGLE.value == "google"


def test_run_status_values() -> None:
    """Test RunStatus enum has expected values."""
    assert RunStatus.QUEUED.value == "queued"
    assert RunStatus.RUNNING.value == "running"
    assert RunStatus.SUCCEEDED.value == "succeeded"
    assert RunStatus.FAILED.value == "failed"
    assert RunStatus.CANCELED.value == "canceled"


def test_message_role_values() -> None:
    """Test MessageRole enum has expected values."""
    assert MessageRole.USER.value == "user"
    assert MessageRole.ASSISTANT.value == "assistant"
    assert MessageRole.SYSTEM.value == "system"


def test_executor_type_values() -> None:
    """Test ExecutorType enum has expected values."""
    assert ExecutorType.PATCH_AGENT.value == "patch_agent"
    assert ExecutorType.CLAUDE_CODE.value == "claude_code"
    assert ExecutorType.CODEX_CLI.value == "codex_cli"
    assert ExecutorType.GEMINI_CLI.value == "gemini_cli"


def test_pr_creation_mode_values() -> None:
    """Test PRCreationMode enum has expected values."""
    assert PRCreationMode.CREATE.value == "create"
    assert PRCreationMode.LINK.value == "link"
