"""Database backend abstraction for SQLite and PostgreSQL support.

This module provides a unified interface for database operations that can
work with both SQLite (aiosqlite) and PostgreSQL (asyncpg) backends.
The backend is selected based on the DATABASE_URL scheme.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class RowProtocol(Protocol):
    """Protocol for database row objects."""

    def keys(self) -> Sequence[str]:
        """Return column names."""
        ...

    def __getitem__(self, key: str) -> Any:
        """Get value by column name."""
        ...


class DatabaseBackend(ABC):
    """Abstract base class for database backends.

    Provides a unified interface for SQLite and PostgreSQL operations.
    All SQL queries should use %s style placeholders which will be
    translated to the appropriate format for each backend.
    """

    @abstractmethod
    async def connect(self) -> None:
        """Establish database connection."""
        ...

    @abstractmethod
    async def disconnect(self) -> None:
        """Close database connection."""
        ...

    @abstractmethod
    async def initialize(self, schema_sql: str) -> None:
        """Initialize database schema."""
        ...

    @abstractmethod
    async def execute(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> int:
        """Execute a query and return affected row count.

        Args:
            query: SQL query with %s placeholders.
            params: Query parameters as sequence or mapping.

        Returns:
            Number of affected rows.
        """
        ...

    @abstractmethod
    async def execute_many(
        self,
        query: str,
        params_list: Sequence[Sequence[Any]],
    ) -> None:
        """Execute a query with multiple parameter sets.

        Args:
            query: SQL query with %s placeholders.
            params_list: List of parameter sequences.
        """
        ...

    @abstractmethod
    async def fetch_one(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> RowProtocol | None:
        """Execute a query and fetch one row.

        Args:
            query: SQL query with %s placeholders.
            params: Query parameters.

        Returns:
            Row object or None if not found.
        """
        ...

    @abstractmethod
    async def fetch_all(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
    ) -> list[RowProtocol]:
        """Execute a query and fetch all rows.

        Args:
            query: SQL query with %s placeholders.
            params: Query parameters.

        Returns:
            List of row objects.
        """
        ...

    @abstractmethod
    async def fetch_val(
        self,
        query: str,
        params: Sequence[Any] | Mapping[str, Any] | None = None,
        column: int = 0,
    ) -> Any:
        """Execute a query and fetch a single value.

        Args:
            query: SQL query with %s placeholders.
            params: Query parameters.
            column: Column index to return (default 0).

        Returns:
            Single value from the first row, or None.
        """
        ...

    @abstractmethod
    def transaction(self) -> AbstractAsyncContextManager[None]:
        """Context manager for database transactions.

        Usage:
            async with db.transaction():
                await db.execute(...)
                await db.execute(...)
        """
        ...

    @abstractmethod
    def transaction_with_lock(self) -> AbstractAsyncContextManager[None]:
        """Context manager for exclusive transaction (for atomic operations).

        SQLite: Uses BEGIN IMMEDIATE
        PostgreSQL: Uses standard BEGIN (row-level locking via FOR UPDATE)
        """
        ...

    @abstractmethod
    async def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database."""
        ...

    @abstractmethod
    async def column_exists(self, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        ...

    @abstractmethod
    async def add_column(
        self,
        table_name: str,
        column_name: str,
        column_type: str,
        default: str | None = None,
    ) -> None:
        """Add a column to an existing table if it doesn't exist.

        Args:
            table_name: Name of the table.
            column_name: Name of the column to add.
            column_type: SQL type of the column.
            default: Optional default value expression.
        """
        ...

    @property
    @abstractmethod
    def placeholder_style(self) -> str:
        """Return the placeholder style for this backend.

        Returns:
            'qmark' for SQLite (?), 'numeric' for PostgreSQL ($1, $2, ...)
        """
        ...

    def translate_query(self, query: str) -> str:
        """Translate a query with %s placeholders to backend-specific format.

        Args:
            query: SQL query with %s placeholders.

        Returns:
            Query with backend-specific placeholders.
        """
        if self.placeholder_style == "qmark":
            return query.replace("%s", "?")
        elif self.placeholder_style == "numeric":
            # Convert %s to $1, $2, $3, etc.
            result = []
            param_index = 0
            i = 0
            while i < len(query):
                if i < len(query) - 1 and query[i : i + 2] == "%s":
                    param_index += 1
                    result.append(f"${param_index}")
                    i += 2
                else:
                    result.append(query[i])
                    i += 1
            return "".join(result)
        else:
            return query


def parse_database_url(url: str) -> tuple[str, str]:
    """Parse a database URL and return (backend_type, connection_string).

    Supported URL formats:
    - sqlite:///path/to/db.sqlite
    - sqlite+aiosqlite:///path/to/db.sqlite
    - postgresql://user:pass@host:port/dbname
    - postgres://user:pass@host:port/dbname
    - postgresql+asyncpg://user:pass@host:port/dbname

    Args:
        url: Database URL string.

    Returns:
        Tuple of (backend_type, connection_string).
        backend_type is 'sqlite' or 'postgresql'.

    Raises:
        ValueError: If the URL scheme is not supported.
    """
    if url.startswith(("sqlite:", "sqlite+")):
        # Extract path from sqlite URL
        # sqlite:///path -> /path
        # sqlite+aiosqlite:///path -> /path
        if ":///" in url:
            path = url.split(":///", 1)[1]
        elif "://" in url:
            path = url.split("://", 1)[1]
        else:
            raise ValueError(f"Invalid SQLite URL format: {url}")
        return ("sqlite", path)

    if url.startswith(("postgresql:", "postgres:", "postgresql+")):
        # Normalize to standard postgresql:// format
        if url.startswith("postgres://"):
            conn_str = "postgresql://" + url[len("postgres://") :]
        elif url.startswith("postgresql+asyncpg://"):
            conn_str = "postgresql://" + url[len("postgresql+asyncpg://") :]
        else:
            conn_str = url
        return ("postgresql", conn_str)

    raise ValueError(
        f"Unsupported database URL scheme: {url}. Supported: sqlite://, postgresql://, postgres://"
    )
