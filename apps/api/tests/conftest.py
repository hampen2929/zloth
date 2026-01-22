"""Pytest configuration and fixtures for zloth API tests."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncGenerator, Generator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest
import pytest_asyncio

from zloth_api.services.crypto_service import CryptoService
from zloth_api.storage.db import Database

if TYPE_CHECKING:
    import aiosqlite


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def crypto_service() -> CryptoService:
    """Create a CryptoService instance for testing."""
    return CryptoService("test-encryption-key-12345")


@pytest_asyncio.fixture
async def test_db(tmp_path: Path) -> AsyncGenerator[Database]:
    """Create an in-memory database for testing.

    Uses a temporary file to allow testing with real SQLite features.
    """
    db_path = tmp_path / "test.db"
    db = Database(db_path=db_path)
    await db.connect()
    await db.initialize()
    yield db
    await db.disconnect()


@pytest_asyncio.fixture
async def db_connection(test_db: Database) -> aiosqlite.Connection:
    """Get the database connection for direct queries."""
    return test_db.connection
