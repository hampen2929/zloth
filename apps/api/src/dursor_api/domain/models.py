"""Pydantic domain models for dursor API."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from dursor_api.domain.enums import MessageRole, Provider, RunStatus


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
    model_ids: list[str] = Field(..., description="List of model profile IDs to run")
    base_ref: str | None = Field(None, description="Base branch/commit")


class RunSummary(BaseModel):
    """Summary of a Run."""

    id: str
    model_id: str
    model_name: str
    provider: Provider
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
    model_id: str
    model_name: str
    provider: Provider
    instruction: str
    base_ref: str | None
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


class AgentConstraints(BaseModel):
    """Constraints for agent execution."""

    max_files_changed: int | None = Field(None, description="Max number of files to change")
    forbidden_paths: list[str] = Field(
        default_factory=lambda: [".git", ".env", "*.secret", "*.key"],
        description="Paths that cannot be modified",
    )


class AgentRequest(BaseModel):
    """Input for Agent execution."""

    workspace_path: str = Field(..., description="Path to the cloned workspace")
    base_ref: str = Field(..., description="Base branch/commit")
    instruction: str = Field(..., description="Natural language instruction")
    context: dict[str, Any] | None = Field(None, description="Additional context")
    constraints: AgentConstraints = Field(default_factory=AgentConstraints)


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
