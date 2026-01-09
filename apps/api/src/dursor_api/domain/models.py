"""Pydantic domain models for dursor API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dursor_api.domain.enums import (
    BreakdownStatus,
    BrokenDownTaskType,
    EstimatedSize,
    ExecutorType,
    MessageRole,
    PRCreationMode,
    Provider,
    RunStatus,
)

# ============================================================
# Model Profile
# ============================================================


class ModelProfileBase(BaseModel):
    """Base model for ModelProfile."""

    provider: Provider
    model_name: str = Field(..., description="Model identifier (e.g., gpt-4o, claude-3-opus)")
    display_name: str | None = Field(None, description="Human-friendly name")


class ModelProfileCreate(ModelProfileBase):
    """Request model for creating a ModelProfile."""

    api_key: str = Field(..., description="API key for the provider")


class ModelProfile(ModelProfileBase):
    """ModelProfile response (without API key)."""

    id: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Repository
# ============================================================


class RepoCloneRequest(BaseModel):
    """Request for cloning a repository."""

    repo_url: str = Field(..., description="Git repository URL")
    ref: str | None = Field(None, description="Branch or commit to checkout")


class Repo(BaseModel):
    """Repository information."""

    id: str
    repo_url: str
    default_branch: str
    latest_commit: str
    workspace_path: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Task (Conversation Unit)
# ============================================================


class TaskCreate(BaseModel):
    """Request for creating a Task."""

    repo_id: str
    title: str | None = None


class Task(BaseModel):
    """Task (conversation unit)."""

    id: str
    repo_id: str
    title: str | None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TaskDetail(Task):
    """Task with additional details."""

    messages: list["Message"] = []
    runs: list["RunSummary"] = []
    prs: list["PRSummary"] = []


# ============================================================
# Message
# ============================================================


class MessageCreate(BaseModel):
    """Request for creating a Message."""

    role: MessageRole
    content: str


class Message(BaseModel):
    """Chat message in a task."""

    id: str
    task_id: str
    role: MessageRole
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Run (Parallel Execution Unit)
# ============================================================


class RunCreate(BaseModel):
    """Request for creating Runs."""

    instruction: str = Field(..., description="Natural language instruction")
    model_ids: list[str] | None = Field(
        None, description="List of model profile IDs to run (required for patch_agent)"
    )
    base_ref: str | None = Field(None, description="Base branch/commit")
    executor_type: ExecutorType = Field(
        default=ExecutorType.PATCH_AGENT,
        description="Executor type: patch_agent (LLM) or claude_code (CLI)",
    )
    message_id: str | None = Field(None, description="ID of the triggering message")


class RunSummary(BaseModel):
    """Summary of a Run."""

    id: str
    message_id: str | None = None
    model_id: str | None
    model_name: str | None
    provider: Provider | None
    executor_type: ExecutorType
    working_branch: str | None = None
    status: RunStatus
    created_at: datetime


class FileDiff(BaseModel):
    """File diff information."""

    path: str
    old_path: str | None = None
    added_lines: int = 0
    removed_lines: int = 0
    patch: str = ""


class Run(BaseModel):
    """Run (model execution unit)."""

    id: str
    task_id: str
    message_id: str | None = None  # Links run to triggering message
    model_id: str | None
    model_name: str | None
    provider: Provider | None
    executor_type: ExecutorType = ExecutorType.PATCH_AGENT
    working_branch: str | None = None
    worktree_path: str | None = None
    session_id: str | None = None  # CLI session ID for conversation persistence
    instruction: str
    base_ref: str | None
    commit_sha: str | None = None  # Latest commit SHA for the run
    status: RunStatus
    summary: str | None = None
    patch: str | None = None
    files_changed: list[FileDiff] = []
    logs: list[str] = []
    warnings: list[str] = []
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


# ============================================================
# Pull Request
# ============================================================


class PRCreate(BaseModel):
    """Request for creating a PR."""

    selected_run_id: str = Field(..., description="ID of the run to use for PR")
    title: str
    body: str | None = None


class PRCreateAuto(BaseModel):
    """Request for auto-generating PR title and body using AI."""

    selected_run_id: str = Field(..., description="ID of the run to use for PR")


class PRUpdate(BaseModel):
    """Request for updating a PR."""

    selected_run_id: str = Field(..., description="ID of the run to apply")
    message: str | None = Field(None, description="Commit message")


class PRSummary(BaseModel):
    """Summary of a PR."""

    id: str
    number: int
    url: str
    branch: str
    status: str


class PR(BaseModel):
    """Pull Request information."""

    id: str
    task_id: str
    number: int
    url: str
    branch: str
    title: str
    body: str | None
    latest_commit: str
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


# ============================================================
# Agent I/F
# ============================================================


# Summary file path constant (outside Pydantic model to avoid field issues)
SUMMARY_FILE_PATH = ".dursor-summary.md"


class AgentConstraints(BaseModel):
    """Constraints for agent execution.

    This model defines constraints that are passed to AI Agents to ensure
    they only perform file editing operations, while git operations are
    managed by dursor (orchestrator management pattern).
    """

    max_files_changed: int | None = Field(None, description="Max number of files to change")
    forbidden_paths: list[str] = Field(
        default_factory=lambda: [
            ".git",
            ".env",
            ".env.*",
            "*.key",
            "*.pem",
            "*.secret",
        ],
        description="Paths that cannot be modified",
    )
    forbidden_commands: list[str] = Field(
        default_factory=lambda: [
            "git commit",
            "git push",
            "git checkout",
            "git reset --hard",
            "git rebase",
            "git merge",
        ],
        description="Git commands that are forbidden for agents",
    )
    allowed_git_commands: list[str] = Field(
        default_factory=lambda: [
            "git status",
            "git diff",
            "git log",
            "git show",
            "git branch",
        ],
        description="Read-only git commands that are allowed",
    )

    def to_prompt(self) -> str:
        """Convert constraints to prompt format for injection into agent instructions.

        Returns:
            Formatted string with constraints for agent prompts.
        """
        forbidden_paths_str = "\n".join(f"- {p}" for p in self.forbidden_paths)
        forbidden_commands_str = ", ".join(f"`{c}`" for c in self.forbidden_commands)
        allowed_commands_str = "\n".join(f"- `{c}`" for c in self.allowed_git_commands)

        return f"""## Important Constraints

### Forbidden Operations
- The following git commands are forbidden: {forbidden_commands_str}
- Only edit files, do not commit or push
- Changes will be automatically detected and committed by the system after your edits

### Forbidden Paths
Access to the following paths is forbidden:
{forbidden_paths_str}

### Allowed Git Commands (Read-only)
{allowed_commands_str}

### Summary File (REQUIRED)
After completing all changes, you MUST create a summary file at `{SUMMARY_FILE_PATH}`.
This file should contain a brief summary (1-2 sentences in English) of what you did.

Example content for `{SUMMARY_FILE_PATH}`:
```
Added user authentication with JWT tokens and password reset functionality.
```

Important:
- Write ONLY the summary text, no headers or formatting
- Keep it concise (1-2 sentences)
- Write in English
- This file will be automatically removed after reading
"""


class AgentRequest(BaseModel):
    """Input for Agent execution."""

    workspace_path: str = Field(..., description="Path to the cloned workspace")
    base_ref: str = Field(..., description="Base branch/commit")
    instruction: str = Field(..., description="Natural language instruction")
    context: dict[str, Any] | None = Field(None, description="Additional context")
    constraints: AgentConstraints = Field(default_factory=lambda: AgentConstraints())


class AgentResult(BaseModel):
    """Output from Agent execution."""

    summary: str = Field(..., description="Human-readable summary")
    patch: str = Field(..., description="Unified diff patch")
    files_changed: list[FileDiff] = Field(default_factory=list)
    logs: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


# ============================================================
# API Responses
# ============================================================


class RunsCreated(BaseModel):
    """Response for run creation."""

    run_ids: list[str]


class PRCreated(BaseModel):
    """Response for PR creation."""

    pr_id: str
    url: str
    branch: str
    number: int


class PRUpdated(BaseModel):
    """Response for PR update."""

    url: str
    latest_commit: str


# ============================================================
# GitHub App Configuration
# ============================================================


class GitHubAppConfig(BaseModel):
    """GitHub App configuration status."""

    app_id: str | None = None
    app_id_masked: str | None = None  # Masked version for display
    installation_id: str | None = None
    installation_id_masked: str | None = None  # Masked version for display
    has_private_key: bool = False
    is_configured: bool = False
    source: str | None = None  # 'env' or 'db'


class GitHubAppConfigSave(BaseModel):
    """Request for saving GitHub App configuration."""

    app_id: str
    private_key: str | None = None  # Optional for updates
    installation_id: str


class GitHubRepository(BaseModel):
    """GitHub repository information."""

    id: int
    name: str
    full_name: str
    owner: str
    default_branch: str
    private: bool


class RepoSelectRequest(BaseModel):
    """Request for selecting a repository by name."""

    owner: str
    repo: str
    branch: str | None = None


# ============================================================
# User Preferences
# ============================================================


class UserPreferences(BaseModel):
    """User preferences for default settings."""

    default_repo_owner: str | None = None
    default_repo_name: str | None = None
    default_branch: str | None = None
    default_branch_prefix: str | None = None
    default_pr_creation_mode: PRCreationMode = PRCreationMode.CREATE


class UserPreferencesSave(BaseModel):
    """Request for saving user preferences."""

    default_repo_owner: str | None = None
    default_repo_name: str | None = None
    default_branch: str | None = None
    default_branch_prefix: str | None = None
    default_pr_creation_mode: PRCreationMode | None = None


class PRCreateLink(BaseModel):
    """Response for PR creation link generation (manual PR creation)."""

    url: str
    branch: str
    base: str


class PRSyncRequest(BaseModel):
    """Request for syncing a PR created manually on GitHub."""

    selected_run_id: str = Field(..., description="ID of the run to use for syncing PR")


class PRSyncResult(BaseModel):
    """Result of attempting to sync a manually created PR."""

    found: bool
    pr: "PRCreated | None" = None


# ============================================================
# Task Breakdown
# ============================================================


class TaskBreakdownRequest(BaseModel):
    """Request for breaking down a task from hearing content."""

    content: str = Field(..., description="Hearing content to break down into tasks")
    executor_type: ExecutorType = Field(
        default=ExecutorType.CLAUDE_CODE,
        description="Agent tool to use for breakdown (CLI only)",
    )
    repo_id: str = Field(..., description="Target repository ID")
    context: dict[str, Any] | None = Field(None, description="Additional context")


class BrokenDownTask(BaseModel):
    """A task broken down from hearing content."""

    title: str = Field(..., description="Task title (max 50 chars)")
    description: str = Field(..., description="Task description with implementation details")
    type: BrokenDownTaskType = Field(..., description="Type of task")
    estimated_size: EstimatedSize = Field(..., description="Estimated size")
    target_files: list[str] = Field(default_factory=list, description="Files to modify")
    implementation_hint: str | None = Field(None, description="Implementation hints")
    tags: list[str] = Field(default_factory=list, description="Related tags")


class CodebaseAnalysis(BaseModel):
    """Result of codebase analysis during breakdown."""

    files_analyzed: int = Field(..., description="Number of files analyzed")
    relevant_modules: list[str] = Field(default_factory=list, description="Relevant modules")
    tech_stack: list[str] = Field(default_factory=list, description="Detected tech stack")


class TaskBreakdownResponse(BaseModel):
    """Response from task breakdown."""

    breakdown_id: str = Field(..., description="Breakdown session ID")
    status: BreakdownStatus = Field(..., description="Breakdown status")
    tasks: list[BrokenDownTask] = Field(default_factory=list, description="Broken down tasks")
    summary: str | None = Field(None, description="Summary of breakdown")
    original_content: str = Field(..., description="Original hearing content")
    codebase_analysis: CodebaseAnalysis | None = Field(
        None, description="Codebase analysis result"
    )
    error: str | None = Field(None, description="Error message if failed")


class TaskBulkCreate(BaseModel):
    """Request for bulk creating tasks."""

    repo_id: str = Field(..., description="Repository ID")
    tasks: list[TaskCreate] = Field(..., description="Tasks to create")


class TaskBulkCreated(BaseModel):
    """Response from bulk task creation."""

    created_tasks: list[Task] = Field(..., description="Created tasks")
    count: int = Field(..., description="Number of tasks created")
