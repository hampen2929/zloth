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
