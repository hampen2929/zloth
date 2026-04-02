from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from zloth_api.config import settings
from zloth_api.routes.github import router as github_router
from zloth_api.storage.db import Database


@pytest.fixture
def app_with_real_db(tmp_path: Path) -> FastAPI:
    # Ensure env does not force ENV mode
    settings.github_app_id = ""
    settings.github_app_private_key = ""
    settings.github_app_installation_id = ""

    app = FastAPI()

    # Inject a Database instance bound to a temp file by monkeypatching get_db
    from zloth_api.storage import db as db_module

    db_module._db = Database(db_path=tmp_path / "routes_test.db")

    @app.on_event("startup")
    async def _init_db() -> None:  # pragma: no cover - simple init wrapper
        await db_module._db.connect()
        await db_module._db.initialize()

    app.include_router(github_router, prefix="/v1")
    return app


def test_save_and_get_github_config_via_routes(app_with_real_db: FastAPI) -> None:
    client = TestClient(app_with_real_db)
    with client:
        # Initially not configured
        r0 = client.get("/v1/github/config")
        assert r0.status_code == 200
        assert r0.json()["is_configured"] is False

        pem = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"
        r1 = client.post(
            "/v1/github/config",
            json={"app_id": "123", "private_key": pem},
        )
        assert r1.status_code == 200
        body = r1.json()
        assert body["is_configured"] is True
        assert body["has_private_key"] is True
        assert body["source"] == "db"

        r2 = client.get("/v1/github/config")
        assert r2.status_code == 200
        body2 = r2.json()
        assert body2["is_configured"] is True
        assert body2["has_private_key"] is True
