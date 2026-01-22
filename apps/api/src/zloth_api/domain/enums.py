"""Enums for zloth domain models."""

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
    - in_progress, in_review, gating, done: Dynamically computed from Run/PR/CI (overrides DB)
    """

    BACKLOG = "backlog"
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    IN_REVIEW = "in_review"
    GATING = "gating"
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


class PRUpdateMode(str, Enum):
    """Mode for PR regeneration update.

    Controls what gets updated when regenerating PR content.
    """

    BOTH = "both"  # Update both title and description
    DESCRIPTION = "description"  # Update description only
    TITLE = "title"  # Update title only


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


class CodingMode(str, Enum):
    """Coding mode for task execution.

    Defines the level of automation for coding tasks:
    - INTERACTIVE: Manual control at each step (default)
    - SEMI_AUTO: Automatic execution with human merge approval
    - FULL_AUTO: Fully autonomous execution including merge
    """

    INTERACTIVE = "interactive"  # Human controls each step
    SEMI_AUTO = "semi_auto"  # Auto execution, human merges
    FULL_AUTO = "full_auto"  # Fully autonomous


class AgenticPhase(str, Enum):
    """Agentic execution phase.

    Represents the current phase of an agentic execution cycle:
    CODING → WAITING_CI → REVIEWING → (AWAITING_HUMAN | MERGE_CHECK) → MERGING → COMPLETED
    """

    CODING = "coding"  # Claude Code generating/fixing code
    WAITING_CI = "waiting_ci"  # Waiting for CI results
    REVIEWING = "reviewing"  # Codex reviewing code
    FIXING_CI = "fixing_ci"  # Fixing CI failures
    FIXING_REVIEW = "fixing_review"  # Addressing review feedback
    AWAITING_HUMAN = "awaiting_human"  # Semi Auto: waiting for human approval
    MERGE_CHECK = "merge_check"  # Checking merge conditions
    MERGING = "merging"  # Executing merge
    COMPLETED = "completed"  # Successfully completed
    FAILED = "failed"  # Failed (unrecoverable)


class NotificationType(str, Enum):
    """Notification event type for agentic execution."""

    READY_FOR_MERGE = "ready_for_merge"  # PR ready for human review (Semi Auto)
    COMPLETED = "completed"  # Task successfully completed
    FAILED = "failed"  # Task failed
    WARNING = "warning"  # Warning (high iteration count, etc.)
