"""Pydantic domain models for zloth API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from zloth_api.domain.enums import (
    AgenticPhase,
    BreakdownStatus,
    BrokenDownTaskType,
    CodingMode,
    EstimatedSize,
    ExecutorType,
    MessageRole,
    NotificationType,
    PRCreationMode,
    Provider,
    ReviewCategory,
    ReviewSeverity,
    ReviewStatus,
    RunStatus,
    TaskKanbanStatus,
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
    selected_branch: str | None = None  # user-selected branch for worktree base
    latest_commit: str
    workspace_path: str
    created_at: datetime

    class Config:
        from_attributes = True


class RepoTaskCounts(BaseModel):
    """Task counts by kanban status for a repository."""

    backlog: int = 0
    todo: int = 0
    in_progress: int = 0
    gating: int = 0
    in_review: int = 0
    done: int = 0
    archived: int = 0


class RepoSummary(BaseModel):
    """Repository summary with task statistics."""

    id: str
    repo_url: str
    repo_name: str | None = None  # Extracted from repo_url (e.g., "owner/repo")
    default_branch: str
    task_counts: RepoTaskCounts
    total_tasks: int = 0
    latest_activity: datetime | None = None  # Most recent task updated_at
    created_at: datetime


# ============================================================
# Task (Conversation Unit)
# ============================================================


class TaskCreate(BaseModel):
    """Request for creating a Task."""

    repo_id: str
    title: str | None = None
    coding_mode: CodingMode = CodingMode.INTERACTIVE


class Task(BaseModel):
    """Task (conversation unit)."""

    id: str
    repo_id: str
    title: str | None
    coding_mode: CodingMode = CodingMode.INTERACTIVE
    kanban_status: str = "backlog"  # Base status stored in DB (backlog/todo/archived)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutorRunStatus(BaseModel):
    """Status of a specific executor's run for a task."""

    executor_type: ExecutorType
    run_id: str | None = None  # None if no run for this executor
    status: RunStatus | None = None  # None if no run for this executor
    has_review: bool = False  # Whether this run has been reviewed


class TaskWithKanbanStatus(Task):
    """Task with computed kanban status for kanban board display."""

    computed_status: TaskKanbanStatus  # Final kanban status (including dynamic computation)
    repo_name: str | None = None  # Repository name (e.g., "owner/repo")
    run_count: int = 0
    running_count: int = 0  # Number of runs with status='running'
    completed_count: int = 0  # Number of completed runs
    pr_count: int = 0
    latest_pr_status: str | None = None
    latest_ci_status: str | None = None  # "pending" | "success" | "failure" | "error" | None
    executor_statuses: list[ExecutorRunStatus] = Field(
        default_factory=list, description="Status per executor type"
    )


class KanbanColumn(BaseModel):
    """Kanban column with tasks."""

    status: TaskKanbanStatus
    tasks: list[TaskWithKanbanStatus]
    count: int


class KanbanBoard(BaseModel):
    """Full kanban board response."""

    columns: list[KanbanColumn]
    total_tasks: int


class CICheckSummary(BaseModel):
    """CI check summary for task detail view."""

    id: str
    pr_id: str
    status: str  # "pending" | "success" | "failure" | "error"
    created_at: datetime
    updated_at: datetime


class TaskDetail(Task):
    """Task with additional details."""

    messages: list["Message"] = []
    runs: list["RunSummary"] = []
    prs: list["PRSummary"] = []
    ci_checks: list["CICheckSummary"] = []


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
    executor_types: list[ExecutorType] | None = Field(
        None,
        description="List of executor types to run in parallel (overrides executor_type)",
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
SUMMARY_FILE_PATH = ".zloth-summary.md"


class AgentConstraints(BaseModel):
    """Constraints for agent execution.

    This model defines constraints that are passed to AI Agents to ensure
    they only perform file editing operations, while git operations are
    managed by zloth (orchestrator management pattern).
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
# Role Execution Results (Common Interface)
# ============================================================


class RoleExecutionResult(BaseModel):
    """Base result interface for all AI Role executions.

    All AI Roles output this common data structure. Role-specific results
    extend this base class with additional fields.
    """

    success: bool = Field(..., description="Whether execution succeeded")
    summary: str | None = Field(None, description="Human-readable summary")
    logs: list[str] = Field(default_factory=list, description="Execution logs")
    warnings: list[str] = Field(default_factory=list, description="Warning messages")
    error: str | None = Field(None, description="Error message if failed")


class ImplementationResult(RoleExecutionResult):
    """Result specific to Implementation Role (RunService).

    Contains patch/diff data for file changes.
    """

    patch: str | None = Field(None, description="Unified diff patch")
    files_changed: list[FileDiff] = Field(default_factory=list, description="Changed files")
    session_id: str | None = Field(None, description="CLI session ID for continuation")


class ReviewExecutionResult(RoleExecutionResult):
    """Result specific to Review Role (ReviewService).

    Contains review feedbacks and scoring.
    """

    overall_score: float | None = Field(None, description="Overall score (0.0-1.0)")
    feedbacks: list["ReviewFeedbackItem"] = Field(
        default_factory=list, description="Review feedback items"
    )


class BreakdownExecutionResult(RoleExecutionResult):
    """Result specific to Breakdown Role (BreakdownService).

    Contains decomposed tasks and codebase analysis.
    """

    tasks: list["BrokenDownTask"] = Field(default_factory=list, description="Broken down tasks")
    codebase_analysis: "CodebaseAnalysis | None" = Field(
        None, description="Codebase analysis result"
    )


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
    installation_id: str | None = None  # Optional: if not set, auto-discover from installations


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
    default_pr_creation_mode: PRCreationMode = PRCreationMode.LINK
    default_coding_mode: CodingMode = CodingMode.INTERACTIVE
    auto_generate_pr_description: bool = False
    worktrees_dir: str | None = None  # Custom worktrees directory path
    enable_gating_status: bool = False  # Enable gating status for CI waiting


class UserPreferencesSave(BaseModel):
    """Request for saving user preferences."""

    default_repo_owner: str | None = None
    default_repo_name: str | None = None
    default_branch: str | None = None
    default_branch_prefix: str | None = None
    default_pr_creation_mode: PRCreationMode | None = None
    default_coding_mode: CodingMode | None = None
    auto_generate_pr_description: bool | None = None
    worktrees_dir: str | None = None  # Custom worktrees directory path
    enable_gating_status: bool | None = None  # Enable gating status for CI waiting


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


class PRLinkJob(BaseModel):
    """Response for starting async PR link generation."""

    job_id: str = Field(..., description="Job ID for polling status")
    status: str = Field(default="pending", description="Job status: pending, completed, failed")


class PRLinkJobResult(BaseModel):
    """Result of async PR link generation job."""

    job_id: str
    status: str = Field(..., description="Job status: pending, completed, failed")
    result: PRCreateLink | None = Field(None, description="Result if completed")
    error: str | None = Field(None, description="Error message if failed")


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


class BrokenDownSubTask(BaseModel):
    """A subtask within a broken down task."""

    title: str = Field(..., description="Subtask title")


class BrokenDownTask(BaseModel):
    """A task broken down from hearing content."""

    title: str = Field(..., description="Task title (max 50 chars)")
    description: str = Field(..., description="Task description with implementation details")
    type: BrokenDownTaskType = Field(..., description="Type of task")
    estimated_size: EstimatedSize = Field(..., description="Estimated size")
    target_files: list[str] = Field(default_factory=list, description="Files to modify")
    implementation_hint: str | None = Field(None, description="Implementation hints")
    tags: list[str] = Field(default_factory=list, description="Related tags")
    subtasks: list[BrokenDownSubTask] = Field(
        default_factory=list, description="Implementation steps"
    )


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
    backlog_items: list["BacklogItem"] = Field(
        default_factory=list, description="Created backlog items (v2)"
    )
    summary: str | None = Field(None, description="Summary of breakdown")
    original_content: str = Field(..., description="Original hearing content")
    codebase_analysis: CodebaseAnalysis | None = Field(None, description="Codebase analysis result")
    error: str | None = Field(None, description="Error message if failed")


class TaskBulkCreate(BaseModel):
    """Request for bulk creating tasks."""

    repo_id: str = Field(..., description="Repository ID")
    tasks: list[TaskCreate] = Field(..., description="Tasks to create")


class TaskBulkCreated(BaseModel):
    """Response from bulk task creation."""

    created_tasks: list[Task] = Field(..., description="Created tasks")
    count: int = Field(..., description="Number of tasks created")


# ============================================================
# Backlog
# ============================================================


class SubTask(BaseModel):
    """Subtask within a backlog item."""

    id: str = Field(..., description="Subtask ID")
    title: str = Field(..., description="Subtask title")
    completed: bool = Field(default=False, description="Whether subtask is completed")


class SubTaskCreate(BaseModel):
    """Request for creating a subtask."""

    title: str = Field(..., description="Subtask title")


class BacklogItemBase(BaseModel):
    """Base model for BacklogItem."""

    title: str = Field(..., description="Task title (max 50 chars)")
    description: str = Field(default="", description="Task description")
    type: BrokenDownTaskType = Field(default=BrokenDownTaskType.FEATURE, description="Task type")
    estimated_size: EstimatedSize = Field(
        default=EstimatedSize.MEDIUM, description="Estimated size"
    )
    target_files: list[str] = Field(default_factory=list, description="Target files")
    implementation_hint: str | None = Field(None, description="Implementation hints")
    tags: list[str] = Field(default_factory=list, description="Tags")


class BacklogItemCreate(BacklogItemBase):
    """Request for creating a BacklogItem."""

    repo_id: str = Field(..., description="Repository ID")
    subtasks: list[SubTaskCreate] = Field(default_factory=list, description="Subtasks")


class BacklogItemUpdate(BaseModel):
    """Request for updating a BacklogItem."""

    title: str | None = Field(None, description="Task title")
    description: str | None = Field(None, description="Task description")
    type: BrokenDownTaskType | None = Field(None, description="Task type")
    estimated_size: EstimatedSize | None = Field(None, description="Estimated size")
    target_files: list[str] | None = Field(None, description="Target files")
    implementation_hint: str | None = Field(None, description="Implementation hints")
    tags: list[str] | None = Field(None, description="Tags")
    subtasks: list[SubTask] | None = Field(None, description="Subtasks")


class BacklogItem(BacklogItemBase):
    """BacklogItem response."""

    id: str = Field(..., description="Backlog item ID")
    repo_id: str = Field(..., description="Repository ID")
    subtasks: list[SubTask] = Field(default_factory=list, description="Subtasks")
    task_id: str | None = Field(None, description="Linked task ID if promoted")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")

    class Config:
        from_attributes = True


# ============================================================
# Code Review
# ============================================================


class ReviewFeedbackItem(BaseModel):
    """Single feedback item in a review."""

    id: str
    file_path: str = Field(..., description="Target file path")
    line_start: int | None = Field(None, description="Start line number")
    line_end: int | None = Field(None, description="End line number")
    severity: ReviewSeverity
    category: ReviewCategory
    title: str = Field(..., description="Feedback title (1 line)")
    description: str = Field(..., description="Detailed description")
    suggestion: str | None = Field(None, description="Suggested fix")
    code_snippet: str | None = Field(None, description="Problematic code snippet")


class ReviewCreate(BaseModel):
    """Request for creating a Review."""

    target_run_ids: list[str] = Field(..., description="Run IDs to review")
    executor_type: ExecutorType = Field(
        default=ExecutorType.CLAUDE_CODE,
        description="Executor to use for review",
    )
    model_id: str | None = Field(None, description="Model ID for patch_agent executor")
    focus_areas: list[ReviewCategory] | None = Field(None, description="Areas to focus on")


class ReviewSummary(BaseModel):
    """Summary of a Review."""

    id: str
    task_id: str
    status: ReviewStatus
    executor_type: ExecutorType
    feedback_count: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    created_at: datetime


class Review(BaseModel):
    """Complete Review information."""

    id: str
    task_id: str
    target_run_ids: list[str]
    executor_type: ExecutorType
    model_id: str | None
    model_name: str | None
    status: ReviewStatus
    overall_summary: str | None = Field(None, description="Overall review summary")
    overall_score: float | None = Field(None, description="Overall score (0.0-1.0)")
    feedbacks: list[ReviewFeedbackItem] = []
    logs: list[str] = []
    error: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None

    class Config:
        from_attributes = True


class ReviewCreated(BaseModel):
    """Response for review creation."""

    review_id: str


class FixInstructionRequest(BaseModel):
    """Request for generating fix instruction from review."""

    review_id: str | None = Field(None, description="Review ID (set from URL path)")
    feedback_ids: list[str] | None = Field(
        None, description="Specific feedbacks to fix (None = all)"
    )
    severity_filter: list[ReviewSeverity] | None = Field(
        None, description="Filter by severity (None = all)"
    )
    additional_instruction: str | None = Field(None, description="Additional user instruction")


class FixInstructionResponse(BaseModel):
    """Generated fix instruction."""

    instruction: str
    target_feedbacks: list[ReviewFeedbackItem]
    estimated_changes: int


# ============================================================
# Agentic Execution
# ============================================================


class IterationLimits(BaseModel):
    """Iteration limits for agentic execution."""

    max_ci_iterations: int = Field(default=5, description="Max CI fix attempts")
    max_review_iterations: int = Field(default=3, description="Max review fix attempts")
    max_total_iterations: int = Field(default=10, description="Total iteration limit")
    min_review_score: float = Field(default=0.75, description="Minimum review score to pass")
    timeout_minutes: int = Field(default=60, description="Total timeout")
    ci_wait_timeout_minutes: int = Field(default=15, description="Max wait for CI")
    coding_timeout_minutes: int = Field(default=30, description="Max time for coding phase")
    escalate_after_iterations: int = Field(
        default=7, description="Alert after this many iterations"
    )


class AgenticState(BaseModel):
    """State of an agentic execution."""

    id: str = Field(..., description="Agentic run ID")
    task_id: str = Field(..., description="Associated task ID")
    mode: CodingMode = Field(..., description="Coding mode")
    phase: AgenticPhase = Field(..., description="Current phase")
    iteration: int = Field(default=0, description="Total iterations")
    ci_iterations: int = Field(default=0, description="CI fix iterations")
    review_iterations: int = Field(default=0, description="Review fix iterations")
    started_at: datetime = Field(..., description="Start time")
    last_activity: datetime = Field(..., description="Last activity time")
    pr_number: int | None = Field(None, description="Associated PR number")
    current_sha: str | None = Field(None, description="Current commit SHA")
    last_ci_result: "CIResult | None" = Field(None, description="Last CI result")
    last_review_score: float | None = Field(None, description="Last review score")
    error: str | None = Field(None, description="Error message if failed")
    human_approved: bool = Field(default=False, description="Human approval flag (Semi Auto)")

    class Config:
        from_attributes = True


class AgenticConfig(BaseModel):
    """Configuration for agentic execution."""

    limits: IterationLimits = Field(default_factory=IterationLimits)
    auto_merge_enabled: bool = Field(default=True, description="Enable auto-merge")
    merge_method: str = Field(default="squash", description="Merge method: merge, squash, rebase")
    delete_branch_after_merge: bool = Field(default=True, description="Delete branch after merge")


class AgenticStartRequest(BaseModel):
    """Request for starting agentic execution."""

    instruction: str = Field(..., description="Development instruction")
    mode: CodingMode = Field(default=CodingMode.FULL_AUTO, description="Coding mode")
    config: AgenticConfig | None = Field(None, description="Optional agentic configuration")


class AgenticStartResponse(BaseModel):
    """Response for starting agentic execution."""

    agentic_run_id: str
    status: str = "started"
    mode: CodingMode


class AgenticStatusResponse(BaseModel):
    """Response for agentic execution status."""

    agentic_run_id: str
    task_id: str
    mode: CodingMode
    phase: AgenticPhase
    iteration: int
    ci_iterations: int
    review_iterations: int
    pr_number: int | None
    last_review_score: float | None
    human_approved: bool
    error: str | None
    started_at: datetime
    last_activity: datetime


class RejectMergeRequest(BaseModel):
    """Request for rejecting merge (Semi Auto mode)."""

    feedback: str | None = Field(None, description="Optional feedback for AI to address")


# ============================================================
# CI Webhook
# ============================================================


class CIJobResult(BaseModel):
    """Result of a single CI job."""

    job_name: str
    result: str  # "success" | "failure" | "skipped" | "cancelled"
    error_log: str | None = None


class CIResult(BaseModel):
    """CI execution result."""

    success: bool
    workflow_run_id: int
    sha: str
    jobs: dict[str, str]  # job_name -> result
    failed_jobs: list[CIJobResult] = Field(default_factory=list)


class CIWebhookPayload(BaseModel):
    """Payload for CI completion webhook from GitHub Actions."""

    event: str = Field(..., description="Event type")
    repository: str = Field(..., description="Repository full name")
    ref: str = Field(..., description="Git ref")
    sha: str = Field(..., description="Commit SHA")
    pr_number: int | None = Field(None, description="PR number if applicable")
    workflow_run_id: int = Field(..., description="Workflow run ID")
    conclusion: str = Field(..., description="Workflow conclusion: success, failure, cancelled")
    jobs: dict[str, str] = Field(..., description="Job results: job_name -> result")


class CIWebhookResponse(BaseModel):
    """Response for CI webhook."""

    status: str
    action_taken: str | None = None
    failed_jobs: list[str] | None = None


class CICheck(BaseModel):
    """CI check result record for a PR."""

    id: str
    task_id: str
    pr_id: str
    status: str  # "pending" | "success" | "failure" | "error"
    workflow_run_id: int | None = None
    sha: str | None = None
    jobs: dict[str, str] = Field(default_factory=dict)  # job_name -> result
    failed_jobs: list[CIJobResult] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CICheckResponse(BaseModel):
    """Response for CI check API."""

    ci_check: CICheck
    is_complete: bool  # True if CI is finished (success/failure/error)


# ============================================================
# Merge Gate
# ============================================================


class MergeCondition(BaseModel):
    """Single merge condition check result."""

    name: str
    passed: bool
    message: str | None = None


class MergeConditionsResult(BaseModel):
    """Result of merge conditions check."""

    can_merge: bool
    conditions: list[MergeCondition]
    failed: list[str] = Field(default_factory=list)


class MergeResult(BaseModel):
    """Result of merge operation."""

    success: bool
    merge_sha: str | None = None
    error: str | None = None


# ============================================================
# Notification
# ============================================================


class NotificationEvent(BaseModel):
    """Notification event for agentic execution."""

    type: NotificationType
    task_id: str
    task_title: str | None = None
    pr_number: int | None = None
    pr_url: str | None = None
    message: str = ""
    mode: CodingMode | None = None
    iterations: int = 0
    review_score: float | None = None
    error: str | None = None


# ============================================================
# Development Metrics
# ============================================================


class PRMetrics(BaseModel):
    """PR-related metrics."""

    total_prs: int = 0
    merged_prs: int = 0
    closed_prs: int = 0
    open_prs: int = 0
    merge_rate: float = 0.0  # percentage
    avg_time_to_merge_hours: float | None = None


class ConversationMetrics(BaseModel):
    """Conversation/message metrics."""

    total_messages: int = 0
    user_messages: int = 0
    assistant_messages: int = 0
    avg_messages_per_task: float = 0.0
    avg_user_messages_per_task: float = 0.0


class RunMetrics(BaseModel):
    """Run execution metrics."""

    total_runs: int = 0
    succeeded_runs: int = 0
    failed_runs: int = 0
    canceled_runs: int = 0
    run_success_rate: float = 0.0  # percentage
    avg_run_duration_seconds: float | None = None
    avg_queue_wait_seconds: float | None = None


class ExecutorDistribution(BaseModel):
    """Distribution of runs by executor type."""

    executor_type: ExecutorType
    count: int = 0
    percentage: float = 0.0


class CIMetrics(BaseModel):
    """CI check metrics."""

    total_ci_checks: int = 0
    passed_ci_checks: int = 0
    failed_ci_checks: int = 0
    ci_success_rate: float = 0.0  # percentage
    avg_ci_fix_iterations: float = 0.0


class ReviewMetrics(BaseModel):
    """Code review metrics."""

    total_reviews: int = 0
    avg_review_score: float | None = None
    critical_issues: int = 0
    high_issues: int = 0
    medium_issues: int = 0
    low_issues: int = 0


class AgenticMetrics(BaseModel):
    """Agentic execution metrics."""

    total_agentic_runs: int = 0
    completed_agentic_runs: int = 0
    failed_agentic_runs: int = 0
    agentic_completion_rate: float = 0.0  # percentage
    avg_total_iterations: float = 0.0
    avg_ci_iterations: float = 0.0
    avg_review_iterations: float = 0.0


class ProductivityMetrics(BaseModel):
    """Overall productivity metrics."""

    avg_cycle_time_hours: float | None = None  # task creation to PR merge
    throughput_per_week: float = 0.0  # merged PRs per week
    first_time_success_rate: float = 0.0  # tasks with 1 run


class MetricsSummary(BaseModel):
    """Aggregated metrics summary."""

    period: str  # e.g., "7d", "30d"
    period_start: datetime
    period_end: datetime

    # Headline metrics
    merge_rate: float = 0.0
    avg_cycle_time_hours: float | None = None
    throughput: float = 0.0
    run_success_rate: float = 0.0

    # Counts
    total_tasks: int = 0
    total_prs: int = 0
    total_runs: int = 0
    total_messages: int = 0

    # Comparisons (vs previous period)
    merge_rate_change: float | None = None
    cycle_time_change: float | None = None
    throughput_change: float | None = None


class MetricsDataPoint(BaseModel):
    """Single data point in a trend."""

    timestamp: datetime
    value: float


class MetricsTrend(BaseModel):
    """Metrics trend over time."""

    metric_name: str
    data_points: list[MetricsDataPoint] = Field(default_factory=list)
    trend: str = "stable"  # "up", "down", "stable"
    change_percentage: float = 0.0


class RealtimeMetrics(BaseModel):
    """Current system state metrics."""

    active_tasks: int = 0
    running_runs: int = 0
    pending_ci_checks: int = 0
    open_prs: int = 0

    # Today's stats
    tasks_created_today: int = 0
    runs_completed_today: int = 0
    prs_merged_today: int = 0


class MetricsDetail(BaseModel):
    """Complete metrics detail response."""

    summary: MetricsSummary
    pr_metrics: PRMetrics
    conversation_metrics: ConversationMetrics
    run_metrics: RunMetrics
    executor_distribution: list[ExecutorDistribution] = Field(default_factory=list)
    ci_metrics: CIMetrics
    review_metrics: ReviewMetrics
    agentic_metrics: AgenticMetrics
    productivity_metrics: ProductivityMetrics
    realtime: RealtimeMetrics


# ============================================================
# CLI Tools Status
# ============================================================


class CLIToolStatus(BaseModel):
    """Status of a single CLI tool."""

    name: str = Field(..., description="CLI tool name (claude, codex, gemini)")
    available: bool = Field(..., description="Whether the CLI tool is available")
    version: str | None = Field(None, description="CLI tool version if available")
    path: str = Field(..., description="Configured path for the CLI tool")
    error: str | None = Field(None, description="Error message if not available")


class CLIToolsStatus(BaseModel):
    """Status of all CLI tools."""

    claude: CLIToolStatus
    codex: CLIToolStatus
    gemini: CLIToolStatus
