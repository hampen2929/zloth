"""Database connection and initialization.

This module provides a unified Database class that works with both
SQLite (aiosqlite) and PostgreSQL (asyncpg) backends. The backend is
selected based on the ZLOTH_DATABASE_URL environment variable:

- sqlite:///path/to/db.sqlite (default)
- postgresql://user:pass@host:port/dbname
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiosqlite

from zloth_api.config import settings
from zloth_api.storage.backend import DatabaseBackend, parse_database_url

if TYPE_CHECKING:
    from zloth_api.storage.sqlite_backend import SQLiteBackend


class Database:
    """Database wrapper with support for SQLite and PostgreSQL backends.

    This class provides a unified interface for database operations that
    works with both SQLite and PostgreSQL. The backend is automatically
    selected based on the database URL.

    For backward compatibility, the class also exposes the raw aiosqlite
    connection when using SQLite backend.
    """

    def __init__(
        self,
        db_path: Path | None = None,
        database_url: str | None = None,
    ) -> None:
        """Initialize database.

        Args:
            db_path: Path to SQLite database file (legacy parameter).
            database_url: Database URL (sqlite:// or postgresql://).
                         If not provided, uses settings.database_url.
        """
        self._backend: DatabaseBackend | None = None
        self._backend_type: str = "sqlite"
        self._connection_string: str = ""

        # Determine database URL
        if database_url:
            url = database_url
        elif db_path:
            # Legacy: db_path parameter for SQLite
            url = f"sqlite:///{db_path}"
        elif settings.database_url:
            url = settings.database_url
        elif settings.data_dir:
            url = f"sqlite:///{settings.data_dir / 'zloth.db'}"
        else:
            raise ValueError("No database URL or path provided")

        self._backend_type, self._connection_string = parse_database_url(url)

        # For backward compatibility with tests that use db_path
        if self._backend_type == "sqlite":
            self.db_path = Path(self._connection_string)
        else:
            self.db_path = None  # type: ignore[assignment]

    async def connect(self) -> None:
        """Connect to the database."""
        if self._backend_type == "sqlite":
            from zloth_api.storage.sqlite_backend import SQLiteBackend

            self._backend = SQLiteBackend(self._connection_string)
        elif self._backend_type == "postgresql":
            from zloth_api.storage.postgres_backend import PostgresBackend

            self._backend = PostgresBackend(self._connection_string)
        else:
            raise ValueError(f"Unsupported backend type: {self._backend_type}")

        await self._backend.connect()

    async def disconnect(self) -> None:
        """Disconnect from the database."""
        if self._backend:
            await self._backend.disconnect()
            self._backend = None

    async def initialize(self) -> None:
        """Initialize the database schema."""
        if not self._backend:
            await self.connect()

        # Load appropriate schema
        schema_path = Path(__file__).parent / self._get_schema_filename()
        schema = schema_path.read_text()

        await self.backend.initialize(schema)

        # Run migrations for existing databases
        await self._run_migrations()

    def _get_schema_filename(self) -> str:
        """Get the appropriate schema filename for the backend."""
        if self._backend_type == "postgresql":
            return "schema_postgres.sql"
        return "schema.sql"

    async def _run_migrations(self) -> None:
        """Run database migrations for existing databases."""
        backend = self.backend

        # Migration: Add session_id column to runs table if it doesn't exist
        await backend.add_column("runs", "session_id", "TEXT")

        # Migration: Add commit_sha column to runs table if it doesn't exist
        await backend.add_column("runs", "commit_sha", "TEXT")

        # Migration: Add message_id column to runs table if it doesn't exist
        # Note: PostgreSQL doesn't support adding FK constraint in ALTER TABLE ADD COLUMN
        await backend.add_column("runs", "message_id", "TEXT")

        # user_preferences migrations
        await backend.add_column("user_preferences", "default_branch_prefix", "TEXT")
        await backend.add_column("user_preferences", "default_pr_creation_mode", "TEXT")
        await backend.add_column("user_preferences", "default_coding_mode", "TEXT")
        await backend.add_column("user_preferences", "auto_generate_pr_description", "INTEGER", "0")
        await backend.add_column(
            "user_preferences", "update_pr_title_on_regenerate", "INTEGER", "1"
        )
        await backend.add_column("user_preferences", "enable_gating_status", "INTEGER", "0")
        await backend.add_column("user_preferences", "notify_on_ready", "INTEGER", "1")
        await backend.add_column("user_preferences", "notify_on_complete", "INTEGER", "1")
        await backend.add_column("user_preferences", "notify_on_failure", "INTEGER", "1")
        await backend.add_column("user_preferences", "notify_on_warning", "INTEGER", "1")
        await backend.add_column("user_preferences", "merge_method", "TEXT", "'squash'")
        await backend.add_column("user_preferences", "review_min_score", "REAL", "0.75")

    @property
    def backend(self) -> DatabaseBackend:
        """Get the database backend."""
        if not self._backend:
            raise RuntimeError("Database not connected")
        return self._backend

    @property
    def backend_type(self) -> str:
        """Get the backend type ('sqlite' or 'postgresql')."""
        return self._backend_type

    @property
    def is_postgres(self) -> bool:
        """Check if using PostgreSQL backend."""
        return self._backend_type == "postgresql"

    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite backend."""
        return self._backend_type == "sqlite"

        # Migration: Add language column if it doesn't exist
        if "language" not in pref_column_names:
            await conn.execute("ALTER TABLE user_preferences ADD COLUMN language TEXT DEFAULT 'en'")
            await conn.commit()

        # Migration: Add base_ref column to tasks table if it doesn't exist
        # This is for workspace/branch consistency (Phase 1.1 from docs/workspace_branch.md)
        cursor = await conn.execute("PRAGMA table_info(tasks)")
        task_columns = await cursor.fetchall()
        task_column_names = [col["name"] for col in task_columns]

        if "base_ref" not in task_column_names:
            await conn.execute("ALTER TABLE tasks ADD COLUMN base_ref TEXT")
            await conn.commit()

        if "workspace_path" not in task_column_names:
            await conn.execute("ALTER TABLE tasks ADD COLUMN workspace_path TEXT")
            await conn.commit()

        if "working_branch" not in task_column_names:
            await conn.execute("ALTER TABLE tasks ADD COLUMN working_branch TEXT")
            await conn.commit()

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the raw aiosqlite connection (SQLite only).

        This property is provided for backward compatibility with existing
        DAO code. For new code, use the backend interface instead.

        Raises:
            RuntimeError: If not using SQLite backend or not connected.
        """
        if self._backend_type != "sqlite":
            raise RuntimeError(
                "Direct connection access is only available for SQLite backend. "
                "Use backend interface for PostgreSQL."
            )
        if not self._backend:
            raise RuntimeError("Database not connected")


        sqlite_backend: SQLiteBackend = self._backend  # type: ignore[assignment]
        return sqlite_backend.connection

    async def fetch_one(
        self, query: str, params: tuple[Any, ...] | None = None
    ) -> aiosqlite.Row | None:
        """Execute a query and fetch one row (SQLite compatibility).

        For backward compatibility. New code should use backend.fetch_one().
        """
        if self._backend_type == "sqlite":
            conn = self.connection
            cursor = await conn.execute(query, params or ())
            return await cursor.fetchone()
        else:
            # For PostgreSQL, translate query and use backend
            row = await self.backend.fetch_one(query, params)
            return row  # type: ignore[return-value]

    async def execute(self, query: str, params: tuple[Any, ...] | None = None) -> aiosqlite.Cursor:
        """Execute a query and return the cursor (SQLite compatibility).

        For backward compatibility. New code should use backend.execute().
        """
        if self._backend_type == "sqlite":
            conn = self.connection
            cursor = await conn.execute(query, params or ())
            await conn.commit()
            return cursor
        else:
            # For PostgreSQL, use backend
            await self.backend.execute(query, params)
            # Return a dummy cursor-like object for compatibility
            return _DummyCursor()  # type: ignore[return-value]


class _DummyCursor:
    """Dummy cursor for PostgreSQL backward compatibility."""

    rowcount: int = 0

    async def fetchone(self) -> None:
        """Fetch one row (not supported in PostgreSQL compatibility mode)."""
        return None

    async def fetchall(self) -> list[Any]:
        """Fetch all rows (not supported in PostgreSQL compatibility mode)."""
        return []


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


async def reset_db() -> None:
    """Reset the global database instance.

    Useful for testing and reconfiguration.
    """
    global _db
    if _db is not None:
        await _db.disconnect()
        _db = None


@asynccontextmanager
async def get_db_context() -> AsyncGenerator[Database]:
    """Get database as async context manager."""
    db = await get_db()
    try:
        yield db
    finally:
        pass  # Connection managed globally


async def create_database(database_url: str | None = None) -> Database:
    """Create a new database instance with the specified URL.

    This is useful for creating separate database connections,
    e.g., for testing or multi-tenant scenarios.

    Args:
        database_url: Database URL. If not provided, uses settings.

    Returns:
        New Database instance (not the global singleton).
    """
    db = Database(database_url=database_url)
    await db.connect()
    await db.initialize()
    return db
