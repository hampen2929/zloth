"""GitHub App service for tazuna API."""

import base64
import time
from typing import Any

import httpx
import jwt

from tazuna_api.config import settings
from tazuna_api.domain.models import (
    GitHubAppConfig,
    GitHubAppConfigSave,
    GitHubRepository,
)
from tazuna_api.storage.db import Database


class GitHubService:
    """Service for GitHub App operations."""

    def __init__(self, db: Database):
        self.db = db
        self._token_cache: dict[str, tuple[str, float]] = {}
        self._installations_cache: list[dict] | None = None

    def _mask_value(self, value: str, visible_chars: int = 4) -> str:
        """Mask a value, showing only the last few characters."""
        if not value:
            return ""
        if len(value) <= visible_chars:
            return "*" * len(value)
        return "*" * (len(value) - visible_chars) + value[-visible_chars:]

    async def get_config(self) -> GitHubAppConfig:
        """Get GitHub App configuration status.

        Note: installation_id is optional. If not set, the service will
        auto-discover installations from the GitHub App.
        """
        # Check environment variables first
        if settings.github_app_id and settings.github_app_private_key:
            installation_id = settings.github_app_installation_id or None
            return GitHubAppConfig(
                app_id=settings.github_app_id,
                app_id_masked=self._mask_value(settings.github_app_id),
                installation_id=installation_id,
                installation_id_masked=self._mask_value(installation_id)
                if installation_id
                else None,
                has_private_key=True,
                is_configured=True,
                source="env",
            )

        # Check database
        row = await self.db.fetch_one(
            "SELECT app_id, installation_id, private_key FROM github_app_config WHERE id = 1"
        )
        if row and row["app_id"] and row["private_key"]:
            installation_id = row["installation_id"] if row["installation_id"] else None
            return GitHubAppConfig(
                app_id=row["app_id"],
                app_id_masked=self._mask_value(row["app_id"]),
                installation_id=installation_id,
                installation_id_masked=self._mask_value(installation_id)
                if installation_id
                else None,
                has_private_key=True,
                is_configured=True,
                source="db",
            )

        return GitHubAppConfig(is_configured=False)

    async def save_config(self, data: GitHubAppConfigSave) -> GitHubAppConfig:
        """Save GitHub App configuration to database.

        Note: installation_id is optional. If not provided, the service will
        auto-discover installations from the GitHub App.
        """
        # Check if config exists
        existing = await self.db.fetch_one("SELECT id FROM github_app_config WHERE id = 1")

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
                    SET app_id = ?, private_key = ?, installation_id = ?,
                        updated_at = CURRENT_TIMESTAMP
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
        # Clear installations cache
        self._installations_cache = None

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

        row = await self.db.fetch_one("SELECT private_key FROM github_app_config WHERE id = 1")
        if row and row["private_key"]:
            return base64.b64decode(row["private_key"]).decode()

        return None

    async def _get_app_credentials(
        self, *, require_installation_id: bool = False
    ) -> tuple[str, str, str | None] | None:
        """Get app ID, private key, and optionally installation ID.

        Args:
            require_installation_id: If True, returns None when installation_id is not set.

        Returns:
            Tuple of (app_id, private_key, installation_id) or None if not configured.
            installation_id may be None if not set and require_installation_id is False.
        """
        config = await self.get_config()
        if not config.is_configured:
            return None

        private_key = await self._get_private_key()
        if not private_key:
            return None

        app_id: str | None
        installation_id: str | None
        if config.source == "env":
            app_id = settings.github_app_id
            installation_id = settings.github_app_installation_id or None
        else:
            app_id = config.app_id
            installation_id = config.installation_id

        if not app_id:
            return None

        if require_installation_id and not installation_id:
            return None

        return (app_id, private_key, installation_id)

    def _generate_jwt(self, app_id: str, private_key: str) -> str:
        """Generate JWT for GitHub App authentication."""
        now = int(time.time())
        payload = {
            "iat": now - 60,  # 60 seconds in the past
            "exp": now + (10 * 60),  # 10 minutes from now
            "iss": app_id,
        }
        return jwt.encode(payload, private_key, algorithm="RS256")

    async def _list_installations(self) -> list[dict]:
        """List all installations of this GitHub App.

        Returns:
            List of installation dicts with 'id', 'account', etc.
        """
        if self._installations_cache is not None:
            return self._installations_cache

        creds = await self._get_app_credentials()
        if not creds:
            return []

        app_id, private_key, _ = creds
        jwt_token = self._generate_jwt(app_id, private_key)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                "https://api.github.com/app/installations",
                headers={
                    "Authorization": f"Bearer {jwt_token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            response.raise_for_status()
            installations = response.json()

        self._installations_cache = installations
        return installations

    async def _get_installation_for_owner(self, owner: str) -> str | None:
        """Find the installation ID for a specific repository owner.

        GitHub App installations are per-account (user or organization).
        This method finds the installation that has access to repositories
        owned by the given owner.

        Args:
            owner: Repository owner (GitHub username or organization name).

        Returns:
            Installation ID if found, None otherwise.
        """
        installations = await self._list_installations()
        for installation in installations:
            account = installation.get("account", {})
            if account.get("login", "").lower() == owner.lower():
                return str(installation["id"])
        return None

    async def _get_installation_token(self, installation_id: str | None = None) -> str | None:
        """Get or refresh installation access token.

        Args:
            installation_id: Optional installation ID. If not provided,
                uses configured installation_id or first available installation.

        Returns:
            Installation access token or None if not available.
        """
        creds = await self._get_app_credentials()
        if not creds:
            return None

        app_id, private_key, configured_installation_id = creds

        # Determine which installation_id to use
        target_installation_id = installation_id or configured_installation_id

        if not target_installation_id:
            # Auto-discover: get first available installation
            installations = await self._list_installations()
            if not installations:
                return None
            target_installation_id = str(installations[0]["id"])

        cache_key = f"{app_id}:{target_installation_id}"

        # Check cache
        if cache_key in self._token_cache:
            token, expires_at = self._token_cache[cache_key]
            if time.time() < expires_at - 60:  # 1 minute buffer
                return token

        # Generate new token
        jwt_token = self._generate_jwt(app_id, private_key)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"https://api.github.com/app/installations/{target_installation_id}/access_tokens",
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
        self,
        method: str,
        endpoint: str,
        *,
        installation_id: str | None = None,
        **kwargs: Any,
    ) -> Any:
        """Make authenticated request to GitHub API.

        Args:
            method: HTTP method.
            endpoint: API endpoint path.
            installation_id: Optional installation ID for the token.
            **kwargs: Additional arguments for the request.
        """
        token = await self._get_installation_token(installation_id)
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
        """List repositories accessible to the GitHub App.

        If installation_id is configured, returns repos from that installation.
        Otherwise, returns repos from all installations.
        """
        creds = await self._get_app_credentials()
        if not creds:
            raise ValueError("GitHub App not configured")

        _, _, configured_installation_id = creds

        repos: list[GitHubRepository] = []
        seen_ids: set[int] = set()

        if configured_installation_id:
            # Single installation mode
            installation_ids = [configured_installation_id]
        else:
            # Multi-installation mode: get all installations
            installations = await self._list_installations()
            if not installations:
                return []
            installation_ids = [str(inst["id"]) for inst in installations]

        for inst_id in installation_ids:
            try:
                data = await self._github_request(
                    "GET",
                    "/installation/repositories",
                    installation_id=inst_id,
                    params={"per_page": 100},
                )

                for repo in data.get("repositories", []):
                    if repo["id"] not in seen_ids:
                        seen_ids.add(repo["id"])
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
            except Exception:
                # Skip failed installations
                continue

        return repos

    async def list_branches(self, owner: str, repo: str) -> list[str]:
        """List all branches for a repository with pagination support."""
        all_branches: list[str] = []
        page = 1

        while True:
            data = await self._github_request(
                "GET",
                f"/repos/{owner}/{repo}/branches",
                params={"per_page": 100, "page": page},
            )

            if not data:
                break

            all_branches.extend(branch["name"] for branch in data)

            # If we got less than 100, we've reached the last page
            if len(data) < 100:
                break

            page += 1

        return all_branches

    async def clone_url(self, owner: str, repo: str) -> str:
        """Get authenticated clone URL for a repository.

        This method finds the correct GitHub App installation for the repository
        owner and generates a token with access to that owner's repositories.

        Args:
            owner: Repository owner (GitHub username or organization name).
            repo: Repository name.

        Returns:
            Authenticated git URL in format:
            https://x-access-token:TOKEN@github.com/owner/repo.git

        Raises:
            ValueError: If GitHub App is not configured or not installed
                for the given owner.
        """
        # First, try to find the installation for this specific owner
        installation_id = await self._get_installation_for_owner(owner)

        # Get token using the owner-specific installation (if found)
        # or fall back to default behavior
        token = await self._get_installation_token(installation_id)
        if not token:
            if installation_id is None:
                raise ValueError(
                    f"GitHub App is not installed for owner '{owner}'. "
                    "Please install the GitHub App on this account/organization."
                )
            raise ValueError("GitHub App not configured")

        return f"https://x-access-token:{token}@github.com/{owner}/{repo}.git"

    async def get_auth_url(self, owner: str, repo: str) -> str:
        """Get authenticated URL for git push operations.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Authenticated git URL.
        """
        return await self.clone_url(owner, repo)

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        head: str,
        base: str,
        body: str | None = None,
    ) -> dict:
        """Create a Pull Request via GitHub API.

        Args:
            owner: Repository owner.
            repo: Repository name.
            title: PR title.
            head: Head branch name.
            base: Base branch name.
            body: PR body (optional).

        Returns:
            GitHub API response as dict containing 'number' and 'html_url'.
        """
        return await self._github_request(
            "POST",
            f"/repos/{owner}/{repo}/pulls",
            json={
                "title": title,
                "body": body or "",
                "head": head,
                "base": base,
            },
        )

    async def update_pull_request(
        self,
        owner: str,
        repo: str,
        pr_number: int,
        title: str | None = None,
        body: str | None = None,
    ) -> dict:
        """Update a Pull Request via GitHub API.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: PR number.
            title: New PR title (optional).
            body: New PR body (optional).

        Returns:
            GitHub API response as dict.
        """
        update_data = {}
        if title is not None:
            update_data["title"] = title
        if body is not None:
            update_data["body"] = body

        return await self._github_request(
            "PATCH",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
            json=update_data,
        )

    async def find_pull_request_by_head(
        self,
        owner: str,
        repo: str,
        *,
        head: str,
        base: str | None = None,
        state: str = "all",
    ) -> dict | None:
        """Find a pull request by head branch (and optional base branch).

        Args:
            owner: Repository owner.
            repo: Repository name.
            head: Head in the form "owner:branch".
            base: Optional base branch name.
            state: PR state: open|closed|all.

        Returns:
            PR dict if found, else None.
        """
        params: dict[str, Any] = {
            "head": head,
            "state": state,
            "per_page": 20,
            "sort": "created",
            "direction": "desc",
        }
        if base:
            params["base"] = base

        try:
            prs = await self._github_request(
                "GET",
                f"/repos/{owner}/{repo}/pulls",
                params=params,
            )
        except httpx.HTTPStatusError as e:
            # 404 can occur when:
            # - Repository doesn't exist
            # - GitHub App doesn't have access to the repository
            # In these cases, return None (PR not found) rather than raising
            if e.response.status_code == 404:
                return None
            raise

        if isinstance(prs, list) and prs:
            return prs[0]
        return None

    async def get_pull_request_status(
        self,
        owner: str,
        repo: str,
        pr_number: int,
    ) -> dict:
        """Get PR status from GitHub API.

        Args:
            owner: Repository owner.
            repo: Repository name.
            pr_number: PR number.

        Returns:
            Dict with:
                - state: "open" | "closed"
                - merged: bool
                - merged_at: str | None
        """
        pr_data = await self._github_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
        )

        return {
            "state": pr_data.get("state", "open"),
            "merged": pr_data.get("merged", False),
            "merged_at": pr_data.get("merged_at"),
        }

    # =========================================
    # Agentic Mode Methods
    # =========================================

    async def get_pr_check_status(self, pr_number: int, repo_full_name: str) -> str:
        """Get combined CI check status for a PR.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name (owner/repo).

        Returns:
            Combined status: "success", "pending", "failure", or "error".
        """
        owner, repo = repo_full_name.split("/", 1)

        # Get PR to find the head SHA
        pr_data = await self._github_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
        )

        head_sha = pr_data.get("head", {}).get("sha")
        if not head_sha:
            return "error"

        # Get combined status
        status_data = await self._github_request(
            "GET",
            f"/repos/{owner}/{repo}/commits/{head_sha}/status",
        )

        return status_data.get("state", "pending")

    async def check_pr_conflicts(self, pr_number: int, repo_full_name: str) -> bool:
        """Check if PR has merge conflicts.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name (owner/repo).

        Returns:
            True if PR has conflicts, False otherwise.
        """
        owner, repo = repo_full_name.split("/", 1)

        pr_data = await self._github_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
        )

        # GitHub uses "dirty" for conflict state
        mergeable_state = pr_data.get("mergeable_state", "unknown")
        return mergeable_state == "dirty"

    async def is_pr_mergeable(self, pr_number: int, repo_full_name: str) -> bool:
        """Check if PR is mergeable.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name (owner/repo).

        Returns:
            True if PR is mergeable, False otherwise.
        """
        owner, repo = repo_full_name.split("/", 1)

        pr_data = await self._github_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
        )

        # mergeable can be null while GitHub is computing
        mergeable = pr_data.get("mergeable")
        return mergeable is True

    async def merge_pr(
        self,
        pr_number: int,
        repo_full_name: str,
        method: str = "squash",
    ) -> str | None:
        """Merge a pull request.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name (owner/repo).
            method: Merge method: "merge", "squash", or "rebase".

        Returns:
            Merge commit SHA if successful, None otherwise.
        """
        owner, repo = repo_full_name.split("/", 1)

        result = await self._github_request(
            "PUT",
            f"/repos/{owner}/{repo}/pulls/{pr_number}/merge",
            json={"merge_method": method},
        )

        return result.get("sha")

    async def delete_pr_branch(self, pr_number: int, repo_full_name: str) -> bool:
        """Delete the branch associated with a PR.

        Args:
            pr_number: PR number.
            repo_full_name: Full repository name (owner/repo).

        Returns:
            True if branch was deleted, False otherwise.
        """
        owner, repo = repo_full_name.split("/", 1)

        # Get PR to find the branch name
        pr_data = await self._github_request(
            "GET",
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
        )

        branch_name = pr_data.get("head", {}).get("ref")
        if not branch_name:
            return False

        token = await self._get_installation_token()
        if not token:
            return False

        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{branch_name}",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
            return response.status_code == 204
