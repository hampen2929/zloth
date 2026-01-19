"""Tests for ModelService - model profile management with encryption."""

from __future__ import annotations

import pytest

from tazuna_api.domain.enums import Provider
from tazuna_api.domain.models import ModelProfileCreate
from tazuna_api.services.crypto_service import CryptoService
from tazuna_api.services.model_service import ModelService
from tazuna_api.storage.dao import ModelProfileDAO
from tazuna_api.storage.db import Database


class TestModelService:
    """Test suite for ModelService."""

    @pytest.fixture
    def dao(self, test_db: Database) -> ModelProfileDAO:
        """Create ModelProfileDAO instance."""
        return ModelProfileDAO(test_db)

    @pytest.fixture
    def service(self, dao: ModelProfileDAO, crypto_service: CryptoService) -> ModelService:
        """Create ModelService instance."""
        return ModelService(dao, crypto_service)

    @pytest.mark.asyncio
    async def test_create_model_encrypts_api_key(
        self, service: ModelService, dao: ModelProfileDAO, crypto_service: CryptoService
    ) -> None:
        """Test that creating a model profile encrypts the API key."""
        api_key = "sk-test-secret-key-12345"
        data = ModelProfileCreate(
            provider=Provider.OPENAI,
            model_name="gpt-4o",
            api_key=api_key,
            display_name="Test GPT-4o",
        )

        profile = await service.create(data)

        # Verify profile was created
        assert profile.id is not None
        assert profile.provider == Provider.OPENAI
        assert profile.model_name == "gpt-4o"

        # Verify the stored key is encrypted (different from original)
        encrypted_key = await dao.get_encrypted_key(profile.id)
        assert encrypted_key is not None
        assert encrypted_key != api_key

        # Verify we can decrypt to get original
        decrypted = crypto_service.decrypt(encrypted_key)
        assert decrypted == api_key

    @pytest.mark.asyncio
    async def test_get_decrypted_key(self, service: ModelService) -> None:
        """Test retrieving decrypted API key."""
        api_key = "sk-anthropic-key-67890"
        data = ModelProfileCreate(
            provider=Provider.ANTHROPIC,
            model_name="claude-3-opus",
            api_key=api_key,
        )

        profile = await service.create(data)

        # Get decrypted key through service
        decrypted_key = await service.get_decrypted_key(profile.id)
        assert decrypted_key == api_key

    @pytest.mark.asyncio
    async def test_get_decrypted_key_not_found(self, service: ModelService) -> None:
        """Test getting decrypted key for nonexistent profile."""
        result = await service.get_decrypted_key("nonexistent-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_list_models(self, service: ModelService) -> None:
        """Test listing all model profiles."""
        # Create some models
        await service.create(
            ModelProfileCreate(
                provider=Provider.OPENAI,
                model_name="gpt-4o",
                api_key="key1",
            )
        )
        await service.create(
            ModelProfileCreate(
                provider=Provider.ANTHROPIC,
                model_name="claude-3-opus",
                api_key="key2",
            )
        )

        models = await service.list()
        # At least 2 models should be in the list
        assert len(models) >= 2

    @pytest.mark.asyncio
    async def test_get_model(self, service: ModelService) -> None:
        """Test getting a model by ID."""
        data = ModelProfileCreate(
            provider=Provider.GOOGLE,
            model_name="gemini-pro",
            api_key="google-key",
            display_name="Gemini Pro",
        )

        created = await service.create(data)
        retrieved = await service.get(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.provider == Provider.GOOGLE
        assert retrieved.model_name == "gemini-pro"
        assert retrieved.display_name == "Gemini Pro"

    @pytest.mark.asyncio
    async def test_get_nonexistent_model(self, service: ModelService) -> None:
        """Test getting a nonexistent model returns None."""
        result = await service.get("nonexistent-model-id")
        assert result is None

    @pytest.mark.asyncio
    async def test_delete_model(self, service: ModelService) -> None:
        """Test deleting a model profile."""
        data = ModelProfileCreate(
            provider=Provider.OPENAI,
            model_name="gpt-4",
            api_key="delete-key",
        )

        created = await service.create(data)
        deleted = await service.delete(created.id)

        assert deleted is True

        # Verify deletion
        retrieved = await service.get(created.id)
        assert retrieved is None

    @pytest.mark.asyncio
    async def test_delete_nonexistent_model(self, service: ModelService) -> None:
        """Test deleting nonexistent model returns False."""
        deleted = await service.delete("nonexistent-id")
        assert deleted is False

    @pytest.mark.asyncio
    async def test_cannot_delete_env_model(self, service: ModelService) -> None:
        """Test that env models cannot be deleted."""
        with pytest.raises(ValueError, match="Cannot delete environment variable models"):
            await service.delete("env-1")

    @pytest.mark.asyncio
    async def test_model_profile_without_display_name(self, service: ModelService) -> None:
        """Test creating model profile without display name."""
        data = ModelProfileCreate(
            provider=Provider.OPENAI,
            model_name="gpt-4o-mini",
            api_key="test-key",
        )

        profile = await service.create(data)
        assert profile.display_name is None
