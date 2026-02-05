"""SQLite backend implementation using aiosqlite."""

from __future__ import annotations

from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from zloth_api.storage.backend import DatabaseBackend, RowProtocol


class SQLiteRow:
    """Wrapper for aiosqlite.Row that implements RowProtocol."""

    def __init__(self, row: aiosqlite.Row) -> None:
        self._row = row

    def keys(self) -> Sequence[str]:
        """Return column names."""
        return self._row.keys()

    def __getitem__(self, key: str) -> Any:
        """Get value by column name."""
        return self._row[key]


class SQLiteBackend(DatabaseBackend):
    """SQLite database backend using aiosqlite.

    Provides async SQLite operations with the unified DatabaseBackend interface.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database file.
        """
        self.db_path = Path(db_path)
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        """Establish database connection."""
        # Ensure parent directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._connection = await aiosqlite.connect(self.db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA foreign_keys = ON")
        await self._connection.execute("PRAGMA journal_mode = WAL")

    async def disconnect(self) -> None:
        """Close database connection."""
        if self._connection:
            await self._connection.close()
            self._connection = None

    @property
    def connection(self) -> aiosqlite.Connection:
        """Get the database connection."""
        if not self._connection:
            raise RuntimeError("Database not connected")
        return self._connection

    async def initialize(self, schema_sql: str) -> None:
        """Initialize database schema."""
        conn = self.connection
        await conn.executescript(schema_sql)
        await conn.commit()

    async def execute(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        """Execute a query and return affected row count."""
        conn = self.connection
        translated = self.translate_query(query)
        cursor = await conn.execute(translated, params or ())
        await conn.commit()
        return cursor.rowcount

    async def execute_many(
        self,
        query: str,
        params_list: Sequence[Sequence[Any]],
    ) -> None:
        """Execute a query with multiple parameter sets."""
        conn = self.connection
        translated = self.translate_query(query)
        await conn.executemany(translated, params_list)
        await conn.commit()

    async def fetch_one(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> RowProtocol | None:
        """Execute a query and fetch one row."""
        conn = self.connection
        translated = self.translate_query(query)
        cursor = await conn.execute(translated, params or ())
        row = await cursor.fetchone()
        if row is None:
            return None
        return SQLiteRow(row)

    async def fetch_all(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> list[RowProtocol]:
        """Execute a query and fetch all rows."""
        conn = self.connection
        translated = self.translate_query(query)
        cursor = await conn.execute(translated, params or ())
        rows = await cursor.fetchall()
        return [SQLiteRow(row) for row in rows]

    async def fetch_val(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        column: int = 0,
    ) -> Any:
        """Execute a query and fetch a single value."""
        conn = self.connection
        translated = self.translate_query(query)
        cursor = await conn.execute(translated, params or ())
        row = await cursor.fetchone()
        if row is None:
            return None
        return row[column]

    def transaction(self) -> AbstractAsyncContextManager[None]:
        """Context manager for database transactions."""

        @asynccontextmanager
        async def _transaction() -> AsyncIterator[None]:
            conn = self.connection
            await conn.execute("BEGIN")
            try:
                yield
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return _transaction()

    def transaction_with_lock(self) -> AbstractAsyncContextManager[None]:
        """Context manager for exclusive transaction.

        Uses BEGIN IMMEDIATE for SQLite to acquire a write lock immediately.
        """

        @asynccontextmanager
        async def _transaction() -> AsyncIterator[None]:
            conn = self.connection
            await conn.execute("BEGIN IMMEDIATE")
            try:
                yield
                await conn.execute("COMMIT")
            except Exception:
                await conn.execute("ROLLBACK")
                raise

        return _transaction()

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        query = """
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name=%s
        """
        count = await self.fetch_val(query, (table_name,))
        return count > 0

    async def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        conn = self.connection
        cursor = await conn.execute(f"PRAGMA table_info({table_name})")
        columns = await cursor.fetchall()
        column_names = [col["name"] for col in columns]
        return column_name in column_names

    async def add_column(
        self,
        table_name: str,
        column_name: str,
        column_type: str,
        default: str | None = None,
    ) -> None:
        """Add a column to an existing table if it doesn't exist."""
        if await self.column_exists(table_name, column_name):
            return

        conn = self.connection
        if default is not None:
            query = (
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default}"
            )
        else:
            query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        await conn.execute(query)
        await conn.commit()

    @property
    def placeholder_style(self) -> str:
        """Return the placeholder style for this backend."""
        return "qmark"

    async def execute_raw(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> aiosqlite.Cursor:
        """Execute a raw query without translation (for SQLite-specific operations).

        This is used for operations that need SQLite-specific syntax.
        """
        conn = self.connection
        cursor = await conn.execute(query, params or ())
        await conn.commit()
        return cursor

    async def fetch_all_raw(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> list[aiosqlite.Row]:
        """Fetch all rows without wrapping (for backward compatibility)."""
        conn = self.connection
        cursor = await conn.execute(query, params or ())
        return list(await cursor.fetchall())
