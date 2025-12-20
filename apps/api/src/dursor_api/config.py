"""Configuration for dursor API."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="DURSOR_",
    )

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    # Paths
    base_dir: Path = Field(default_factory=lambda: Path(__file__).parent.parent.parent.parent.parent)
    workspaces_dir: Path | None = Field(default=None)
    data_dir: Path | None = Field(default=None)

    # Database
    database_url: str | None = Field(default=None)

    # Security
    encryption_key: str = Field(default="")  # Must be set in production

    # GitHub (Legacy PAT - deprecated, use GitHub App instead)
    github_pat: str = Field(default="")

    # GitHub App Configuration
    github_app_id: str = Field(default="")
    github_app_private_key: str = Field(default="")  # Base64 encoded
    github_app_installation_id: str = Field(default="")

    def model_post_init(self, __context) -> None:
        """Set derived paths after initialization."""
        if self.workspaces_dir is None:
            self.workspaces_dir = self.base_dir / "workspaces"
        if self.data_dir is None:
            self.data_dir = self.base_dir / "data"
        if self.database_url is None:
            self.database_url = f"sqlite+aiosqlite:///{self.data_dir}/dursor.db"

        # Ensure directories exist
        self.workspaces_dir.mkdir(parents=True, exist_ok=True)
        self.data_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
