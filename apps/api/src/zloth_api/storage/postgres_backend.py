"""PostgreSQL backend implementation using asyncpg."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from datetime import datetime
from typing import Any
from urllib.parse import urlparse

try:
    import asyncpg
except ImportError:
    asyncpg = None  # type: ignore[assignment]

from zloth_api.storage.backend import DatabaseBackend, RowProtocol


class PostgresRow:
    """Wrapper for asyncpg.Record that implements RowProtocol."""

    def __init__(self, record: asyncpg.Record) -> None:
        self._record = record

    def keys(self) -> Sequence[str]:
        """Return column names."""
        return list(self._record.keys())

    def __getitem__(self, key: str) -> Any:
        """Get value by column name."""
        value = self._record[key]
        # Handle datetime conversion for compatibility with SQLite string format
        if isinstance(value, datetime):
            return value.isoformat()
        return value


class PostgresBackend(DatabaseBackend):
    """PostgreSQL database backend using asyncpg.

    Provides async PostgreSQL operations with connection pooling
    and the unified DatabaseBackend interface.
    """

    def __init__(
        self,
        connection_string: str,
        min_pool_size: int = 2,
        max_pool_size: int = 10,
    ) -> None:
        """Initialize PostgreSQL backend.

        Args:
            connection_string: PostgreSQL connection URL.
            min_pool_size: Minimum number of connections in the pool.
            max_pool_size: Maximum number of connections in the pool.
        """
        if asyncpg is None:
            raise ImportError(
                "asyncpg is required for PostgreSQL support. Install it with: pip install asyncpg"
            )

        self.connection_string = connection_string
        self.min_pool_size = min_pool_size
        self.max_pool_size = max_pool_size
        self._pool: asyncpg.Pool | None = None

    async def connect(self) -> None:
        """Establish database connection pool."""
        self._pool = await asyncpg.create_pool(
            self.connection_string,
            min_size=self.min_pool_size,
            max_size=self.max_pool_size,
            init=self._init_connection,
        )

    async def _init_connection(self, conn: asyncpg.Connection) -> None:
        """Initialize each connection with custom type codecs."""
        # Register JSON codec for JSONB columns
        await conn.set_type_codec(
            "jsonb",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )
        await conn.set_type_codec(
            "json",
            encoder=json.dumps,
            decoder=json.loads,
            schema="pg_catalog",
        )

    async def disconnect(self) -> None:
        """Close database connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    @property
    def pool(self) -> asyncpg.Pool:
        """Get the connection pool."""
        if not self._pool:
            raise RuntimeError("Database not connected")
        return self._pool

    async def initialize(self, schema_sql: str) -> None:
        """Initialize database schema."""
        async with self.pool.acquire() as conn:
            await conn.execute(schema_sql)

    async def execute(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        """Execute a query and return affected row count."""
        translated = self.translate_query(query)
        params_tuple = self._prepare_params(params)

        async with self.pool.acquire() as conn:
            result = await conn.execute(translated, *params_tuple)
            # asyncpg returns 'UPDATE N' or 'DELETE N' strings
            # Parse the count from the result
            if result.startswith(("UPDATE", "DELETE", "INSERT")):
                parts = result.split()
                if len(parts) >= 2:
                    try:
                        return int(parts[1])
                    except ValueError:
                        pass
            return 0

    async def execute_many(
        self,
        query: str,
        params_list: Sequence[Sequence[Any]],
    ) -> None:
        """Execute a query with multiple parameter sets."""
        translated = self.translate_query(query)

        async with self.pool.acquire() as conn:
            await conn.executemany(translated, params_list)

    async def fetch_one(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> RowProtocol | None:
        """Execute a query and fetch one row."""
        translated = self.translate_query(query)
        params_tuple = self._prepare_params(params)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(translated, *params_tuple)
            if row is None:
                return None
            return PostgresRow(row)

    async def fetch_all(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> list[RowProtocol]:
        """Execute a query and fetch all rows."""
        translated = self.translate_query(query)
        params_tuple = self._prepare_params(params)

        async with self.pool.acquire() as conn:
            rows = await conn.fetch(translated, *params_tuple)
            return [PostgresRow(row) for row in rows]

    async def fetch_val(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        column: int = 0,
    ) -> Any:
        """Execute a query and fetch a single value."""
        translated = self.translate_query(query)
        params_tuple = self._prepare_params(params)

        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(translated, *params_tuple)
            if row is None:
                return None
            # asyncpg returns Record, access by index
            return row[column]

    def transaction(self) -> AbstractAsyncContextManager[None]:
        """Context manager for database transactions."""

        @asynccontextmanager
        async def _transaction() -> AsyncIterator[None]:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    # Store connection for nested operations
                    self._transaction_conn = conn
                    try:
                        yield
                    finally:
                        self._transaction_conn = None

        return _transaction()

    def transaction_with_lock(self) -> AbstractAsyncContextManager[None]:
        """Context manager for exclusive transaction.

        PostgreSQL doesn't need special syntax for exclusive transactions.
        Row-level locking should be done with FOR UPDATE in queries.
        """
        return self.transaction()

    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name = %s
            )
        """
        result = await self.fetch_val(query, (table_name,))
        return bool(result)

    async def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        query = """
            SELECT EXISTS (
                SELECT FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = %s
                AND column_name = %s
            )
        """
        result = await self.fetch_val(query, (table_name, column_name))
        return bool(result)

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

        if default is not None:
            query = (
                f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} DEFAULT {default}"
            )
        else:
            query = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"

        async with self.pool.acquire() as conn:
            await conn.execute(query)

    @property
    def placeholder_style(self) -> str:
        """Return the placeholder style for this backend."""
        return "numeric"

    def _prepare_params(self, params: Sequence[Any] | Mapping[str, Any] | None) -> tuple[Any, ...]:
        """Convert params to tuple for asyncpg."""
        if params is None:
            return ()
        if isinstance(params, Mapping):
            raise TypeError("asyncpg does not support named parameters directly")
        return tuple(params)

    async def claim_job_with_lock(
        self,
        locked_by: str,
        now_iso: str,
    ) -> RowProtocol | None:
        """Atomically claim the next available job using FOR UPDATE SKIP LOCKED.

        This is a PostgreSQL-optimized version that avoids table-level locks.

        Args:
            locked_by: Identifier for the worker claiming the job.
            now_iso: Current timestamp in ISO format.

        Returns:
            Claimed job row or None if no jobs available.
        """
        query = """
            UPDATE jobs
            SET status = 'running',
                attempts = attempts + 1,
                locked_at = $1,
                locked_by = $2,
                updated_at = $1
            WHERE id = (
                SELECT id FROM jobs
                WHERE status = 'queued'
                  AND available_at <= $1
                ORDER BY created_at ASC
                LIMIT 1
                FOR UPDATE SKIP LOCKED
            )
            RETURNING *
        """
        async with self.pool.acquire() as conn:
            row = await conn.fetchrow(query, now_iso, locked_by)
            if row is None:
                return None
            return PostgresRow(row)


def get_connection_params(connection_string: str) -> dict[str, Any]:
    """Parse PostgreSQL connection string into parameters.

    Args:
        connection_string: PostgreSQL connection URL.

    Returns:
        Dictionary of connection parameters.
    """
    parsed = urlparse(connection_string)

    params: dict[str, Any] = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 5432,
        "database": parsed.path.lstrip("/") if parsed.path else "zloth",
    }

    if parsed.username:
        params["user"] = parsed.username
    if parsed.password:
        params["password"] = parsed.password

    return params
