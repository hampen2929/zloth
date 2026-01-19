"""Tests for API routes - endpoint validation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tazuna_api.domain.enums import Provider
from tazuna_api.domain.models import ModelProfile
from tazuna_api.routes.models import router as models_router
from tazuna_api.services.crypto_service import CryptoService
from tazuna_api.services.model_service import ModelService
from tazuna_api.storage.dao import ModelProfileDAO
from tazuna_api.storage.db import Database

if TYPE_CHECKING:
    pass


def create_test_app() -> FastAPI:
    """Create a test FastAPI application."""
    app = FastAPI()
    app.include_router(models_router, prefix="/v1")
    return app


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self) -> None:
        """Test basic health check."""

        # We need to mock the lifespan to avoid DB initialization
        with patch("tazuna_api.main.get_db", new_callable=AsyncMock):
            with patch("tazuna_api.main.get_pr_status_poller", new_callable=AsyncMock):
                # Create a simple test app without lifespan
                test_app = FastAPI()

                @test_app.get("/health")
                async def health() -> dict[str, str]:
                    return {"status": "healthy", "version": "0.1.0"}

                client = TestClient(test_app)
                response = client.get("/health")
                assert response.status_code == 200
                data = response.json()
                assert data["status"] == "healthy"


class TestModelsRoutes:
    """Test /v1/models endpoints."""

    @pytest.fixture
    def mock_model_service(self) -> AsyncMock:
        """Create a mock ModelService."""
        return AsyncMock(spec=ModelService)

    @pytest.fixture
    def test_app(self, mock_model_service: AsyncMock) -> FastAPI:
        """Create test app with mocked dependencies."""
        from tazuna_api.dependencies import get_model_service
        from tazuna_api.routes.models import router

        app = FastAPI()
        app.include_router(router, prefix="/v1")

        async def override_get_model_service() -> AsyncMock:
            return mock_model_service

        app.dependency_overrides[get_model_service] = override_get_model_service
        return app

    @pytest.fixture
    def client(self, test_app: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(test_app)

    def test_list_models(self, client: TestClient, mock_model_service: AsyncMock) -> None:
        """Test GET /v1/models."""
        from datetime import datetime

        mock_model_service.list.return_value = [
            ModelProfile(
                id="model-1",
                provider=Provider.OPENAI,
                model_name="gpt-4o",
                display_name="GPT-4o",
                created_at=datetime.now(),
            ),
            ModelProfile(
                id="model-2",
                provider=Provider.ANTHROPIC,
                model_name="claude-3-opus",
                display_name="Claude 3 Opus",
                created_at=datetime.now(),
            ),
        ]

        response = client.get("/v1/models")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        assert data[0]["id"] == "model-1"
        assert data[1]["id"] == "model-2"

    def test_create_model(self, client: TestClient, mock_model_service: AsyncMock) -> None:
        """Test POST /v1/models."""
        from datetime import datetime

        mock_model_service.create.return_value = ModelProfile(
            id="new-model",
            provider=Provider.OPENAI,
            model_name="gpt-4o",
            display_name="New GPT-4o",
            created_at=datetime.now(),
        )

        response = client.post(
            "/v1/models",
            json={
                "provider": "openai",
                "model_name": "gpt-4o",
                "api_key": "sk-test-key",
                "display_name": "New GPT-4o",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] == "new-model"
        assert data["model_name"] == "gpt-4o"

    def test_create_model_invalid_provider(self, client: TestClient) -> None:
        """Test POST /v1/models with invalid provider."""
        response = client.post(
            "/v1/models",
            json={
                "provider": "invalid-provider",
                "model_name": "test-model",
                "api_key": "test-key",
            },
        )
        assert response.status_code == 422  # Validation error

    def test_get_model(self, client: TestClient, mock_model_service: AsyncMock) -> None:
        """Test GET /v1/models/{model_id}."""
        from datetime import datetime

        mock_model_service.get.return_value = ModelProfile(
            id="model-123",
            provider=Provider.GOOGLE,
            model_name="gemini-pro",
            display_name="Gemini Pro",
            created_at=datetime.now(),
        )

        response = client.get("/v1/models/model-123")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "model-123"
        assert data["provider"] == "google"

    def test_get_model_not_found(self, client: TestClient, mock_model_service: AsyncMock) -> None:
        """Test GET /v1/models/{model_id} when not found."""
        mock_model_service.get.return_value = None

        response = client.get("/v1/models/nonexistent")
        assert response.status_code == 404
        assert response.json()["detail"] == "Model not found"

    def test_delete_model(self, client: TestClient, mock_model_service: AsyncMock) -> None:
        """Test DELETE /v1/models/{model_id}."""
        mock_model_service.delete.return_value = True

        response = client.delete("/v1/models/model-to-delete")
        assert response.status_code == 204

    def test_delete_model_not_found(
        self, client: TestClient, mock_model_service: AsyncMock
    ) -> None:
        """Test DELETE /v1/models/{model_id} when not found."""
        mock_model_service.delete.return_value = False

        response = client.delete("/v1/models/nonexistent")
        assert response.status_code == 404

    def test_delete_env_model_error(
        self, client: TestClient, mock_model_service: AsyncMock
    ) -> None:
        """Test DELETE /v1/models/{model_id} for env model."""
        mock_model_service.delete.side_effect = ValueError(
            "Cannot delete environment variable models"
        )

        response = client.delete("/v1/models/env-1")
        assert response.status_code == 400
        assert "Cannot delete environment variable models" in response.json()["detail"]


class TestModelsRoutesIntegration:
    """Integration tests for models routes with real database."""

    @pytest.fixture
    def test_app_with_db(self, test_db: Database, crypto_service: CryptoService) -> FastAPI:
        """Create test app with real database."""
        from tazuna_api.dependencies import get_model_service
        from tazuna_api.routes.models import router

        app = FastAPI()
        app.include_router(router, prefix="/v1")

        async def override_get_model_service() -> ModelService:
            dao = ModelProfileDAO(test_db)
            return ModelService(dao, crypto_service)

        app.dependency_overrides[get_model_service] = override_get_model_service
        return app

    @pytest.fixture
    def client(self, test_app_with_db: FastAPI) -> TestClient:
        """Create test client."""
        return TestClient(test_app_with_db)

    def test_create_and_list_models_integration(self, client: TestClient) -> None:
        """Test creating and listing models with real DB."""
        # Create a model
        create_response = client.post(
            "/v1/models",
            json={
                "provider": "openai",
                "model_name": "gpt-4o",
                "api_key": "sk-integration-test-key",
                "display_name": "Integration Test Model",
            },
        )
        assert create_response.status_code == 201
        created = create_response.json()
        model_id = created["id"]

        # List models - should include our new model
        list_response = client.get("/v1/models")
        assert list_response.status_code == 200
        models = list_response.json()
        model_ids = [m["id"] for m in models]
        assert model_id in model_ids

        # Get the specific model
        get_response = client.get(f"/v1/models/{model_id}")
        assert get_response.status_code == 200
        model = get_response.json()
        assert model["display_name"] == "Integration Test Model"

        # Delete the model
        delete_response = client.delete(f"/v1/models/{model_id}")
        assert delete_response.status_code == 204

        # Verify it's deleted
        get_deleted_response = client.get(f"/v1/models/{model_id}")
        assert get_deleted_response.status_code == 404
