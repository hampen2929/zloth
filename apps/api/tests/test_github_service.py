"""Tests for GitHub App service configuration."""

from __future__ import annotations

import pytest

from zloth_api.domain.models import GitHubAppConfigSave
from zloth_api.services.github_service import GitHubService
from zloth_api.storage.db import Database


class TestGitHubServiceConfig:
    """Tests for GitHub App configuration save/load."""

    @pytest.fixture
    def github_service(self, test_db: Database) -> GitHubService:
        """Create a GitHubService instance for testing."""
        return GitHubService(test_db)

    @pytest.mark.asyncio
    async def test_save_config_stores_private_key(
        self, github_service: GitHubService
    ) -> None:
        """Test that save_config correctly stores the private key."""
        # Arrange
        config_data = GitHubAppConfigSave(
            app_id="123456",
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            installation_id="789",
        )

        # Act
        result = await github_service.save_config(config_data)

        # Assert - check response
        assert result.is_configured is True
        assert result.has_private_key is True
        assert result.app_id == "123456"
        assert result.source == "db"

    @pytest.mark.asyncio
    async def test_save_config_then_get_config(
        self, github_service: GitHubService
    ) -> None:
        """Test that get_config returns correct data after save_config."""
        # Arrange
        config_data = GitHubAppConfigSave(
            app_id="123456",
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
            installation_id="789",
        )

        # Act
        await github_service.save_config(config_data)
        result = await github_service.get_config()

        # Assert
        assert result.is_configured is True
        assert result.has_private_key is True
        assert result.app_id == "123456"
        assert result.source == "db"

    @pytest.mark.asyncio
    async def test_save_config_initial_requires_private_key(
        self, github_service: GitHubService
    ) -> None:
        """Test that initial save requires private key."""
        # Arrange
        config_data = GitHubAppConfigSave(
            app_id="123456",
            private_key=None,  # No private key
        )

        # Act & Assert
        with pytest.raises(ValueError, match="Private key is required"):
            await github_service.save_config(config_data)

    @pytest.mark.asyncio
    async def test_update_config_preserves_private_key(
        self, github_service: GitHubService
    ) -> None:
        """Test that updating without private key preserves existing key."""
        # Arrange - initial save with private key
        initial_config = GitHubAppConfigSave(
            app_id="123456",
            private_key="-----BEGIN RSA PRIVATE KEY-----\ntest\n-----END RSA PRIVATE KEY-----",
        )
        await github_service.save_config(initial_config)

        # Act - update without private key
        update_config = GitHubAppConfigSave(
            app_id="999999",
            private_key=None,  # Not providing new private key
        )
        result = await github_service.save_config(update_config)

        # Assert - private key should still exist
        assert result.has_private_key is True
        assert result.app_id == "999999"

        # Verify with get_config
        get_result = await github_service.get_config()
        assert get_result.is_configured is True
        assert get_result.has_private_key is True
