"""Configuration for zloth API."""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get project root directory (4 levels up from this file)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# Load .env file into os.environ
load_dotenv(_PROJECT_ROOT / ".env")


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="ZLOTH_",
        extra="ignore",  # Ignore non-ZLOTH_ env vars like OPENAI_API_KEY
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Paths
    base_dir: Path = Field(
        default_factory=lambda: Path(__file__).parent.parent.parent.parent.parent
    )
    workspaces_dir: Path | None = Field(
        default=None,
        description="Directory for git clone workspaces. Defaults to ~/.zloth/workspaces "
        "to avoid inheriting parent directory's CLAUDE.md",
    )
    worktrees_dir: Path | None = Field(
        default=None,
        description="Directory for git worktrees. Defaults to ~/.zloth/worktrees "
        "to avoid inheriting parent directory's CLAUDE.md",
    )
    data_dir: Path | None = Field(
        default=None,
        description="Directory for SQLite database. Defaults to ~/.zloth/data "
        "to store data outside the project directory",
    )

    # Database
    database_url: str | None = Field(default=None)

    # Security
    encryption_key: str = Field(default="")  # Must be set in production

    # GitHub App Configuration
    github_app_id: str = Field(default="")
    github_app_private_key: str = Field(default="")  # Base64 encoded
    github_app_installation_id: str = Field(default="")

    # CLI Executor Paths (optional, defaults to executable name in PATH)
    claude_cli_path: str = Field(default="claude")
    codex_cli_path: str = Field(default="codex")
    gemini_cli_path: str = Field(default="gemini")

    # Agentic Mode Configuration
    agentic_enabled: bool = Field(default=True, description="Enable agentic mode")
    agentic_auto_merge: bool = Field(
        default=True, description="Enable auto-merge in Full Auto mode"
    )

    # Agentic Iteration Limits
    agentic_max_total_iterations: int = Field(default=10, description="Max total iterations")
    agentic_max_ci_iterations: int = Field(default=5, description="Max CI fix iterations")
    agentic_max_review_iterations: int = Field(default=3, description="Max review fix iterations")
    agentic_timeout_minutes: int = Field(default=60, description="Total timeout in minutes")

    # CI Polling Configuration
    ci_polling_interval_seconds: int = Field(
        default=30, description="Interval between CI status polls (seconds)"
    )
    ci_polling_timeout_minutes: int = Field(
        default=30, description="Timeout for CI polling (minutes)"
    )
    ci_polling_enabled: bool = Field(
        default=True, description="Enable CI polling (alternative to webhooks)"
    )

    # Queue Configuration (architecture v2: UI-API-Queue-Worker pattern)
    queue_url: str | None = Field(
        default=None,
        description="Queue backend URL. Defaults to SQLite in data_dir. "
        "Examples: 'sqlite:///path/to/queue.db', 'redis://localhost:6379', "
        "'servicebus://...' (Azure Service Bus)",
    )
    queue_max_concurrent_tasks: int = Field(
        default=5, description="Maximum concurrent task executions (prevents overload)"
    )
    queue_task_timeout_seconds: int = Field(
        default=3600, description="Default timeout for task execution in seconds (1 hour)"
    )
    queue_cleanup_completed_tasks: bool = Field(
        default=True, description="Automatically clean up completed tasks from memory"
    )
    queue_cleanup_older_than_hours: int = Field(
        default=24, description="Remove completed jobs older than this many hours"
    )

    # Worker Configuration (architecture v2)
    worker_enabled: bool = Field(
        default=True,
        description="Enable background job worker. Set to false for API-only mode "
        "(workers run as separate processes)",
    )
    worker_concurrency: int = Field(
        default=4, description="Number of concurrent jobs per worker process"
    )
    worker_poll_interval_seconds: float = Field(
        default=1.0, description="Interval between queue polls in seconds"
    )
    worker_id_prefix: str = Field(
        default="worker", description="Prefix for auto-generated worker IDs"
    )
    job_timeout_seconds: int = Field(
        default=600, description="Maximum time for a single job execution (10 minutes)"
    )

    # Quality Thresholds
    review_min_score: float = Field(default=0.75, description="Minimum review score")
    coverage_threshold: int = Field(default=80, description="Minimum coverage percentage")

    # Webhook
    webhook_secret: str = Field(default="", description="Webhook HMAC secret")

    # Merge Settings
    merge_method: str = Field(default="squash", description="Merge method: merge, squash, rebase")
    merge_delete_branch: bool = Field(default=True, description="Delete branch after merge")

    # Workspace Isolation Mode
    use_clone_isolation: bool = Field(
        default=True,
        description="Use git clone instead of worktree for workspace isolation. "
        "Clone mode provides better support for remote sync and conflict resolution.",
    )

    # Workspace Branch Sharing
    share_workspace_across_executors: bool = Field(
        default=False,
        description="Share workspace/branch across different executor types within the same task. "
        "When enabled, all executor types (claude_code, codex_cli, gemini_cli) will use the "
        "same branch, allowing work to be continued by a different AI tool.",
    )

    # Notification
    slack_webhook_url: str = Field(default="", description="Slack webhook URL")
    notify_email: str = Field(default="", description="Notification email address")
    notify_on_ready: bool = Field(default=True, description="Notify when PR ready (Semi Auto)")
    notify_on_complete: bool = Field(default=True, description="Notify on completion")
    notify_on_failure: bool = Field(default=True, description="Notify on failure")
    notify_on_warning: bool = Field(default=True, description="Notify on warnings")
    warn_iteration_threshold: int = Field(default=7, description="Warn after this many iterations")

    def model_post_init(self, __context: object) -> None:
        """Set derived paths after initialization."""
        if self.workspaces_dir is None:
            # Default to ~/.zloth/workspaces to avoid inheriting
            # parent directory's CLAUDE.md when CLI agents run in workspaces
            self.workspaces_dir = Path.home() / ".zloth" / "workspaces"
        if self.worktrees_dir is None:
            # Default to ~/.zloth/worktrees to avoid inheriting
            # parent directory's CLAUDE.md when CLI agents run in worktrees
            self.worktrees_dir = Path.home() / ".zloth" / "worktrees"
        if self.data_dir is None:
            # Default to ~/.zloth/data to store database outside the project directory
            self.data_dir = Path.home() / ".zloth" / "data"
        if self.database_url is None:
            self.database_url = f"sqlite+aiosqlite:///{self.data_dir}/zloth.db"

        # Ensure directories exist and are writable
        for dir_path, dir_name in [
            (self.workspaces_dir, "workspaces"),
            (self.worktrees_dir, "worktrees"),
            (self.data_dir, "data"),
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
            if not os.access(dir_path, os.W_OK):
                raise PermissionError(
                    f"Directory '{dir_path}' is not writable. "
                    f"Please fix permissions with: chmod -R u+w {dir_path}"
                )


settings = Settings()
