"""Enums for dursor domain models."""

from enum import Enum


class Provider(str, Enum):
    """LLM Provider."""

    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    GOOGLE = "google"


class RoleExecutionStatus(str, Enum):
    """AI Role execution status. All Roles share this common status lifecycle."""

    QUEUED = "queued"  # Waiting in queue
    RUNNING = "running"  # Currently executing
    SUCCEEDED = "succeeded"  # Completed successfully
    FAILED = "failed"  # Execution failed
    CANCELED = "canceled"  # Canceled by user


# Backward compatibility aliases
RunStatus = RoleExecutionStatus


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


class TaskKanbanStatus(str, Enum):
    """Task kanban status.

    - backlog, todo, archived: Stored in DB (manually set by human)
    - in_progress, in_review, done: Dynamically computed from Run/PR (overrides DB)
    """

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    DONE = "done"
    ARCHIVED = "archived"


class TaskBaseKanbanStatus(str, Enum):
    """Task base kanban status (stored in DB, manually set by human)."""

    BACKLOG = "backlog"
    TODO = "todo"
    ARCHIVED = "archived"


class PRStatus(str, Enum):
    """PR status on GitHub."""

    OPEN = "open"
    MERGED = "merged"
    CLOSED = "closed"


class BacklogStatus(str, Enum):
    """Backlog item status."""

    DRAFT = "draft"  # Just created, not yet refined
    READY = "ready"  # Ready to be worked on
    IN_PROGRESS = "in_progress"  # Task created and work started
    DONE = "done"  # Completed


class ReviewSeverity(str, Enum):
    """Review feedback severity level."""

    CRITICAL = "critical"  # Security vulnerabilities, data loss risks
    HIGH = "high"  # Significant bugs, performance issues
    MEDIUM = "medium"  # Code quality, maintainability concerns
    LOW = "low"  # Style suggestions, minor improvements


class ReviewCategory(str, Enum):
    """Review feedback category."""

    SECURITY = "security"  # Security issues
    BUG = "bug"  # Bugs and logic errors
    PERFORMANCE = "performance"  # Performance issues
    MAINTAINABILITY = "maintainability"  # Code maintainability
    BEST_PRACTICE = "best_practice"  # Best practices
    STYLE = "style"  # Code style
    DOCUMENTATION = "documentation"  # Documentation issues
    TEST = "test"  # Test-related issues


# ReviewStatus alias for backward compatibility
ReviewStatus = RoleExecutionStatus
