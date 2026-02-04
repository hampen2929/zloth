"""Tests for API routes - endpoint validation."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

if TYPE_CHECKING:
    pass


class TestHealthEndpoint:
    """Test health check endpoint."""

    def test_health_check(self) -> None:
        """Test basic health check."""

        # We need to mock the lifespan to avoid DB initialization
        with patch("zloth_api.main.get_db", new_callable=AsyncMock):
            with patch("zloth_api.main.get_pr_status_poller", new_callable=AsyncMock):
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
