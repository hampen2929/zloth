"""Enums for dursor domain models."""

from enum import Enum


class Provider(str, Enum):
    """LLM Provider."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class RunStatus(str, Enum):
    """Run execution status."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ExecutorType(str, Enum):
    """Executor type for runs."""

    PATCH_AGENT = "patch_agent"  # LLM-based patch generation
    CLAUDE_CODE = "claude_code"  # Claude Code CLI execution
    CODEX_CLI = "codex_cli"  # OpenAI Codex CLI execution
    GEMINI_CLI = "gemini_cli"  # Google Gemini CLI execution


class PRCreationMode(str, Enum):
    """Default behavior for 'Create PR' actions."""

    CREATE = "create"  # Create PR immediately via GitHub API
    LINK = "link"  # Open a GitHub compare link; user creates PR manually


class BreakdownStatus(str, Enum):
    """Task breakdown status."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class BrokenDownTaskType(str, Enum):
    """Type of broken down task."""

    FEATURE = "feature"
    BUG_FIX = "bug_fix"
    REFACTORING = "refactoring"
    DOCS = "docs"
    TEST = "test"


class EstimatedSize(str, Enum):
    """Estimated size of a task."""

    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
