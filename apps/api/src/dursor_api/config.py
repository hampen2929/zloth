"""Configuration for dursor API."""

import os
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get project root directory (4 levels up from this file)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent

# Load .env file into os.environ
load_dotenv(_PROJECT_ROOT / ".env")


class EnvModelConfig(BaseModel):
    """Model configuration loaded from environment variables."""

    provider: str
    model_name: str
    api_key: str
    display_name: str | None = None


def _parse_env_models() -> list[EnvModelConfig]:
    """Parse model configurations from environment variables.

    Supports provider-specific format:
        OPENAI_API_KEY, OPENAI_MODEL
        ANTHROPIC_API_KEY, ANTHROPIC_MODEL
        GEMINI_API_KEY, GEMINI_MODEL

    Returns:
        List of model configurations.
    """
    models: list[EnvModelConfig] = []

    # OpenAI
    openai_api_key = os.environ.get("OPENAI_API_KEY")
    openai_model = os.environ.get("OPENAI_MODEL")
    if openai_api_key and openai_model:
        models.append(
            EnvModelConfig(
                provider="openai",
                model_name=openai_model,
                api_key=openai_api_key,
                display_name=f"OpenAI {openai_model}",
            )
        )

    # Anthropic
    anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
    anthropic_model = os.environ.get("ANTHROPIC_MODEL")
    if anthropic_api_key and anthropic_model:
        models.append(
            EnvModelConfig(
                provider="anthropic",
                model_name=anthropic_model,
                api_key=anthropic_api_key,
                display_name=f"Anthropic {anthropic_model}",
            )
        )

    # Google (Gemini)
    gemini_api_key = os.environ.get("GEMINI_API_KEY")
    gemini_model = os.environ.get("GEMINI_MODEL")
    if gemini_api_key and gemini_model:
        models.append(
            EnvModelConfig(
                provider="google",
                model_name=gemini_model,
                api_key=gemini_api_key,
                display_name=f"Gemini {gemini_model}",
            )
        )

    return models


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=str(_PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        env_prefix="DURSOR_",
        extra="ignore",  # Ignore non-DURSOR_ env vars like OPENAI_API_KEY
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

        # Ensure directories exist and are writable
        for dir_path, dir_name in [
            (self.workspaces_dir, "workspaces"),
            (self.data_dir, "data"),
        ]:
            dir_path.mkdir(parents=True, exist_ok=True)
            if not os.access(dir_path, os.W_OK):
                raise PermissionError(
                    f"Directory '{dir_path}' is not writable. "
                    f"Please fix permissions with: chmod -R u+w {dir_path}"
                )

    @property
    def env_models(self) -> list[EnvModelConfig]:
        """Get model configurations from environment variables."""
        return _parse_env_models()


settings = Settings()
