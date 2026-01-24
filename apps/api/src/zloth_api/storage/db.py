"""Database connection and initialization."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from zloth_api.config import settings


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path | None = None):
        if db_path:
            self.db_path = db_path
        elif settings.data_dir:
            self.db_path = settings.data_dir / "zloth.db"
        else:
            raise ValueError("data_dir must be set in settings")
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

        conn = self.connection
        await conn.executescript(schema)
        await conn.commit()

        # Run migrations for existing databases
        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """Run database migrations for existing databases."""
        conn = self.connection
        cursor = await conn.execute("PRAGMA table_info(runs)")
        columns = await cursor.fetchall()
        column_names = [col["name"] for col in columns]

        # Migration: Add session_id column to runs table if it doesn't exist
        if "session_id" not in column_names:
            await conn.execute("ALTER TABLE runs ADD COLUMN session_id TEXT")
            await conn.commit()

        # Migration: Add commit_sha column to runs table if it doesn't exist
        if "commit_sha" not in column_names:
            await conn.execute("ALTER TABLE runs ADD COLUMN commit_sha TEXT")
            await conn.commit()

        # Migration: Add message_id column to runs table if it doesn't exist
        if "message_id" not in column_names:
            await conn.execute(
                "ALTER TABLE runs ADD COLUMN message_id TEXT REFERENCES messages(id)"
            )
            await conn.commit()

        # Migration: Add default_branch_prefix column to user_preferences table if it doesn't exist
        cursor = await conn.execute("PRAGMA table_info(user_preferences)")
        pref_columns = await cursor.fetchall()
        pref_column_names = [col["name"] for col in pref_columns]

        if "default_branch_prefix" not in pref_column_names:
            await conn.execute("ALTER TABLE user_preferences ADD COLUMN default_branch_prefix TEXT")
            await conn.commit()

        # Migration: Add default_pr_creation_mode column if it doesn't exist
        if "default_pr_creation_mode" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN default_pr_creation_mode TEXT"
            )
            await conn.commit()

        # Migration: Add default_coding_mode column if it doesn't exist
        if "default_coding_mode" not in pref_column_names:
            await conn.execute("ALTER TABLE user_preferences ADD COLUMN default_coding_mode TEXT")
            await conn.commit()

        # Migration: Add auto_generate_pr_description column if it doesn't exist
        if "auto_generate_pr_description" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences "
                "ADD COLUMN auto_generate_pr_description INTEGER DEFAULT 0"
            )
            await conn.commit()

        # Migration: Add update_pr_title_on_regenerate column if it doesn't exist
        if "update_pr_title_on_regenerate" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences "
                "ADD COLUMN update_pr_title_on_regenerate INTEGER DEFAULT 1"
            )
            await conn.commit()

        # Migration: Add enable_gating_status column if it doesn't exist
        if "enable_gating_status" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN enable_gating_status INTEGER DEFAULT 0"
            )
            await conn.commit()

        # Migration: Add notify_on_ready column if it doesn't exist
        if "notify_on_ready" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN notify_on_ready INTEGER DEFAULT 1"
            )
            await conn.commit()

        # Migration: Add notify_on_complete column if it doesn't exist
        if "notify_on_complete" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN notify_on_complete INTEGER DEFAULT 1"
            )
            await conn.commit()

        # Migration: Add notify_on_failure column if it doesn't exist
        if "notify_on_failure" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN notify_on_failure INTEGER DEFAULT 1"
            )
            await conn.commit()

        # Migration: Add notify_on_warning column if it doesn't exist
        if "notify_on_warning" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN notify_on_warning INTEGER DEFAULT 1"
            )
            await conn.commit()

        # Migration: Add merge_method column if it doesn't exist
        if "merge_method" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN merge_method TEXT DEFAULT 'squash'"
            )
            await conn.commit()

        # Migration: Add review_min_score column if it doesn't exist
        if "review_min_score" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN review_min_score REAL DEFAULT 0.75"
            )
            await conn.commit()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    async def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> aiosqlite.Row | None:
        """Execute a query and fetch one row."""
        conn = self.connection
        cursor = await conn.execute(query, params or ())
        return await cursor.fetchone()

    async def execute(self, query: str, params: tuple[Any, ...] | None = None) -> aiosqlite.Cursor:
        """Execute a query and return the cursor."""
        conn = self.connection
        cursor = await conn.execute(query, params or ())
        await conn.commit()
        return cursor


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
async def get_db_context() -> AsyncGenerator[Database]:
    """Get database as async context manager."""
    db = await get_db()
    try:
        yield db
    finally:
        pass  # Connection managed globally
