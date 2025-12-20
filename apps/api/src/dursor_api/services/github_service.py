"""GitHub App service for dursor API."""

import base64
import time
from typing import Any

import httpx
import jwt

from dursor_api.config import settings
from dursor_api.domain.models import (
    GitHubAppConfig,
    GitHubAppConfigSave,
    GitHubRepository,
)
from dursor_api.storage.db import Database


class GitHubService:
    """Service for GitHub App operations."""

    def __init__(self, db: Database):
        self.db = db
        self._token_cache: dict[str, tuple[str, float]] = {}

    def _mask_value(self, value: str, visible_chars: int = 4) -> str:
        """Mask a value, showing only the last few characters."""
        if not value:
            return ""
        if len(value) <= visible_chars:
            return "*" * len(value)
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]

    async def get_config(self) -> GitHubAppConfig:
        """Get GitHub App configuration status."""
        # Check environment variables first
        if (
            settings.github_app_id
            and settings.github_app_private_key
            and settings.github_app_installation_id
        ):
            return GitHubAppConfig(
                app_id=settings.github_app_id,
                app_id_masked=self._mask_value(settings.github_app_id),
                installation_id=settings.github_app_installation_id,
                installation_id_masked=self._mask_value(settings.github_app_installation_id),
                has_private_key=True,
                is_configured=True,
                source="env",
            )

        # Check database
        row = await self.db.fetch_one(
            "SELECT app_id, installation_id, private_key FROM github_app_config WHERE id = 1"
        )
        if row and row["app_id"] and row["installation_id"]:
            return GitHubAppConfig(
                app_id=row["app_id"],
                app_id_masked=self._mask_value(row["app_id"]),
                installation_id=row["installation_id"],
                installation_id_masked=self._mask_value(row["installation_id"]),
                has_private_key=bool(row.get("private_key")),
                is_configured=True,
                source="db",
            )

        return GitHubAppConfig(is_configured=False)

    async def save_config(self, data: GitHubAppConfigSave) -> GitHubAppConfig:
        """Save GitHub App configuration to database."""
        # Check if config exists
        existing = await self.db.fetch_one(
            "SELECT id FROM github_app_config WHERE id = 1"
        )

        if data.private_key:
            # Encode private key to base64 for storage
            encoded_key = base64.b64encode(data.private_key.encode()).decode()
        else:
            encoded_key = None

        if existing:
            # Update
            if encoded_key:
                await self.db.execute(
                    """
                    UPDATE github_app_config
                    SET app_id = ?, private_key = ?, installation_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    """,
                    (data.app_id, encoded_key, data.installation_id),
                )
            else:
                await self.db.execute(
                    """
                    UPDATE github_app_config
                    SET app_id = ?, installation_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = 1
                    """,
                    (data.app_id, data.installation_id),
                )
        else:
            # Insert
            if not encoded_key:
                raise ValueError("Private key is required for initial configuration")
            await self.db.execute(
                """
                INSERT INTO github_app_config (id, app_id, private_key, installation_id)
                VALUES (1, ?, ?, ?)
                """,
                (data.app_id, encoded_key, data.installation_id),
            )

        # Clear token cache
        self._token_cache.clear()

        return GitHubAppConfig(
            app_id=data.app_id,
            installation_id=data.installation_id,
            is_configured=True,
            source="db",
        )

    async def _get_private_key(self) -> str | None:
        """Get private key from env or database."""
        if settings.github_app_private_key:
            try:
                return base64.b64decode(settings.github_app_private_key).decode()
            except Exception:
                # Assume it's already decoded
                return settings.github_app_private_key

        row = await self.db.fetch_one(
            "SELECT private_key FROM github_app_config WHERE id = 1"
        )
        if row and row["private_key"]:
            return base64.b64decode(row["private_key"]).decode()

        return None

    async def _get_app_credentials(self) -> tuple[str, str, str] | None:
        """Get app ID, private key, and installation ID."""
        config = await self.get_config()
        if not config.is_configured:
            return None

        private_key = await self._get_private_key()
        if not private_key:
            return None

        if config.source == "env":
            return (
                settings.github_app_id,
                private_key,
                settings.github_app_installation_id,
            )
        else:
            return (
                config.app_id,
                private_key,
                config.installation_id,
            )

    def _generate_jwt(self, app_id: str, private_key: str) -> str:
        """Generate JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60 seconds in the past
            "exp": now + (10 * 60),  # 10 minutes from now
            "iss": app_id,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def _get_installation_token(self) -> str | None:
        """Get or refresh installation access token."""
        creds = await self._get_app_credentials()
        if not creds:
            return None

        app_id, private_key, installation_id = creds
        cache_key = f"{app_id}:{installation_id}"

        # Check cache
        if cache_key in self._token_cache:
            token, expires_at = self._token_cache[cache_key]
            if time.time() < expires_at - 60:  # 1 minute buffer
                return token

        # Generate new token
        jwt_token = self._generate_jwt(app_id, private_key)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{installation_id}/access_tokens",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            data = response.json()

        token = data["token"]
        # GitHub tokens expire in 1 hour, cache for slightly less
        self._token_cache[cache_key] = (token, time.time() + 3500)

        return token

    async def _github_request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> Any:
        """Make authenticated request to GitHub API."""
        token = await self._get_installation_token()
        if not token:
            raise ValueError("GitHub App not configured")

        async with httpx.AsyncClient() as client:
            response = await client.request(
                method,
                f"https://api.github.com{endpoint}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                **kwargs,
            )
            response.raise_for_status()
            return response.json()

    async def list_repos(self) -> list[GitHubRepository]:
        """List repositories accessible to the GitHub App."""
        data = await self._github_request(
            "GET", "/installation/repositories", params={"per_page": 100}
        )

        repos = []
        for repo in data.get("repositories", []):
            repos.append(
                GitHubRepository(
                    id=repo["id"],
                    name=repo["name"],
                    full_name=repo["full_name"],
                    owner=repo["owner"]["login"],
                    default_branch=repo["default_branch"],
                    private=repo["private"],
                )
            )

        return repos

    async def list_branches(self, owner: str, repo: str) -> list[str]:
        """List branches for a repository."""
        data = await self._github_request(
            "GET", f"/repos/{owner}/{repo}/branches", params={"per_page": 100}
        )

        return [branch["name"] for branch in data]

    async def clone_url(self, owner: str, repo: str) -> str:
        """Get authenticated clone URL for a repository."""
        token = await self._get_installation_token()
        if not token:
            raise ValueError("GitHub App not configured")

        return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"
