"""Database connection and initialization."""

import aiosqlite
from pathlib import Path
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from dursor_api.config import settings


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or settings.data_dir / "dursor.db"
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Connect to the database."""
        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    async def initialize(self) -> None:
        """Initialize the database schema."""
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()

        if not self._connection:
            await self.connect()

        await self._connection.executescript(schema)
        await self._connection.commit()

        # Run migrations for existing databases
        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """Run database migrations for existing databases."""
        cursor = await self._connection.execute("PRAGMA table_info(runs)")
        columns = await cursor.fetchall()
        column_names = [col["name"] for col in columns]

        # Migration: Add session_id column to runs table if it doesn't exist
        if "session_id" not in column_names:
            await self._connection.execute(
                "ALTER TABLE runs ADD COLUMN session_id TEXT"
            )
            await self._connection.commit()

        # Migration: Add commit_sha column to runs table if it doesn't exist
        if "commit_sha" not in column_names:
            await self._connection.execute(
                "ALTER TABLE runs ADD COLUMN commit_sha TEXT"
            )
            await self._connection.commit()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection


# Global database instance
_db: Database | None = None


async def get_db() -> Database:
    """Get the database instance."""
    global _db
    if _db is None:
        _db = Database()
        await _db.connect()
        await _db.initialize()
    return _db


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[Database, None]:
    """Get database as async context manager."""
    db = await get_db()
    try:
        yield db
    finally:
        pass  # Connection managed globally
