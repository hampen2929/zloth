import asyncio
from pathlib import Path

import pytest

from zloth_api.storage.db import Database
from zloth_api.config import settings
from zloth_api.services.github_service import GitHubService
from zloth_api.domain.models import GitHubAppConfigSave


@pytest.mark.asyncio
async def test_initial_save_and_get_config_db_only(monkeypatch, tmp_path: Path):
    # Ensure env does not interfere
    for key in [
        "ZLOTH_GITHUB_APP_ID",
        "ZLOTH_GITHUB_APP_PRIVATE_KEY",
        "ZLOTH_GITHUB_APP_INSTALLATION_ID",
    ]:
        monkeypatch.delenv(key, raising=False)

    # Also clear already-loaded settings to avoid env precedence
    settings.github_app_id = ""
    settings.github_app_private_key = ""
    settings.github_app_installation_id = ""

    db = Database(db_path=tmp_path / "test_github.db")
    await db.connect()
    await db.initialize()
    svc = GitHubService(db)

    # Not configured initially
    cfg0 = await svc.get_config()
    assert cfg0.is_configured is False

    # Save both app_id and private_key
    pem = "-----BEGIN RSA PRIVATE KEY-----\nabc\n-----END RSA PRIVATE KEY-----\n"
    saved = await svc.save_config(GitHubAppConfigSave(app_id="123", private_key=pem))
    # Save returns canonical config
    assert saved.is_configured is True
    assert saved.source == "db"

    # Fetch again and verify flags
    cfg1 = await svc.get_config()
    assert cfg1.is_configured is True
    assert cfg1.has_private_key is True
    assert cfg1.app_id == "123"

    # Private key can be retrieved for token generation
    pk = await svc._get_private_key()
    assert pk.startswith("-----BEGIN")
