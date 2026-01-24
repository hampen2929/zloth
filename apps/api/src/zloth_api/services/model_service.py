"""Model profile management service."""

from datetime import UTC, datetime

from zloth_api.config import EnvModelConfig, settings
from zloth_api.domain.enums import Provider
from zloth_api.domain.models import ModelProfile, ModelProfileCreate
from zloth_api.services.crypto_service import CryptoService
from zloth_api.storage.dao import ModelProfileDAO

# Prefix for environment variable model IDs
ENV_MODEL_ID_PREFIX = "env-"


def _env_model_to_profile(index: int, env_model: EnvModelConfig) -> ModelProfile:
    """Convert an EnvModelConfig to a ModelProfile.

    Args:
        index: Index of the model (1-based).
        env_model: Environment model configuration.

    Returns:
        ModelProfile instance.
    """
    return ModelProfile(
        id=f"{ENV_MODEL_ID_PREFIX}{index}",
        provider=Provider(env_model.provider),
        model_name=env_model.model_name,
        display_name=env_model.display_name or f"{env_model.provider}/{env_model.model_name}",
        created_at=datetime.now(UTC),
    )


class ModelService:
    """Service for managing model profiles."""

    def __init__(self, dao: ModelProfileDAO, crypto: CryptoService):
        self.dao = dao
        self.crypto = crypto

    async def create(self, data: ModelProfileCreate) -> ModelProfile:
        """Create a new model profile.

        Args:
            data: Model profile creation data.

        Returns:
            Created model profile.
        """
        # Encrypt the API key
        encrypted_key = self.crypto.encrypt(data.api_key)

        return await self.dao.create(
            provider=data.provider,
            model_name=data.model_name,
            api_key_encrypted=encrypted_key,
            display_name=data.display_name,
        )

    async def get(self, model_id: str) -> ModelProfile | None:
        """Get a model profile by ID.

        Args:
            model_id: Model profile ID.

        Returns:
            Model profile or None if not found.
        """
        # Check if it's an env model
        if model_id.startswith(ENV_MODEL_ID_PREFIX):
            try:
                index = int(model_id[len(ENV_MODEL_ID_PREFIX) :])
                env_models = settings.env_models
                if 1 <= index <= len(env_models):
                    return _env_model_to_profile(index, env_models[index - 1])
            except ValueError:
                pass
            return None

        return await self.dao.get(model_id)

    async def list(self) -> list[ModelProfile]:
        """List all model profiles.

        Returns:
            List of model profiles (env models first, then DB models).
        """
        # Get models from environment variables
        env_models = settings.env_models
        env_profiles = [_env_model_to_profile(i + 1, model) for i, model in enumerate(env_models)]

        # Get models from database
        db_profiles = await self.dao.list()

        return env_profiles + db_profiles

    async def delete(self, model_id: str) -> bool:
        """Delete a model profile.

        Args:
            model_id: Model profile ID.

        Returns:
            True if deleted, False if not found.

        Raises:
            ValueError: If trying to delete an env model.
        """
        if model_id.startswith(ENV_MODEL_ID_PREFIX):
            # Keep ValueError for backward compatibility with callers/tests.
            raise ValueError("Cannot delete environment variable models")

        return await self.dao.delete(model_id)

    async def get_decrypted_key(self, model_id: str) -> str | None:
        """Get the decrypted API key for a model profile.

        Args:
            model_id: Model profile ID.

        Returns:
            Decrypted API key or None if not found.
        """
        # Check if it's an env model
        if model_id.startswith(ENV_MODEL_ID_PREFIX):
            try:
                index = int(model_id[len(ENV_MODEL_ID_PREFIX) :])
                env_models = settings.env_models
                if 1 <= index <= len(env_models):
                    return env_models[index - 1].api_key
            except ValueError:
                pass
            return None

        encrypted = await self.dao.get_encrypted_key(model_id)
        if not encrypted:
            return None
        return self.crypto.decrypt(encrypted)
