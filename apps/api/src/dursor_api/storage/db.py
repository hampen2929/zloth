"""Database connection and initialization."""

import logging
import re
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import aiosqlite

from dursor_api.config import settings

logger = logging.getLogger(__name__)


class Database:
    """Async SQLite database wrapper."""

    def __init__(self, db_path: Path | None = None):
        if db_path:
            self.db_path = db_path
        elif settings.data_dir:
            self.db_path = settings.data_dir / "dursor.db"
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

    def _parse_schema_columns(self, schema: str) -> dict[str, list[tuple[str, str]]]:
        """Parse schema.sql and extract column definitions for each table.

        Returns:
            dict mapping table_name -> list of (column_name, column_definition)
        """
        tables: dict[str, list[tuple[str, str]]] = {}

        # Remove SQL comments (-- style)
        schema_no_comments = re.sub(r"--[^\n]*", "", schema)

        # Match CREATE TABLE statements
        table_pattern = re.compile(
            r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s*\((.*?)\);",
            re.IGNORECASE | re.DOTALL,
        )

        for match in table_pattern.finditer(schema_no_comments):
            table_name = match.group(1)
            body = match.group(2)

            columns: list[tuple[str, str]] = []
            # Split by comma, but handle nested parentheses (for CHECK constraints, etc.)
            parts = self._split_column_definitions(body)

            for part in parts:
                part = part.strip()
                if not part:
                    continue

                # Skip constraints (PRIMARY KEY, FOREIGN KEY, CHECK, UNIQUE, INDEX)
                upper_part = part.upper()
                if any(
                    upper_part.startswith(kw)
                    for kw in ["PRIMARY KEY", "FOREIGN KEY", "CHECK", "UNIQUE", "INDEX"]
                ):
                    continue

                # Extract column name and definition
                # Column definition starts with column name followed by type/constraints
                col_match = re.match(r"(\w+)\s+(.*)", part, re.DOTALL)
                if col_match:
                    col_name = col_match.group(1)
                    col_def = col_match.group(2).strip()
                    # Skip if it's a table constraint keyword
                    if col_name.upper() not in [
                        "PRIMARY",
                        "FOREIGN",
                        "CHECK",
                        "UNIQUE",
                        "INDEX",
                        "CONSTRAINT",
                    ]:
                        columns.append((col_name, col_def))

            tables[table_name] = columns

        return tables

    def _split_column_definitions(self, body: str) -> list[str]:
        """Split column definitions by comma, respecting parentheses."""
        parts: list[str] = []
        current = ""
        depth = 0

        for char in body:
            if char == "(":
                depth += 1
                current += char
            elif char == ")":
                depth -= 1
                current += char
            elif char == "," and depth == 0:
                parts.append(current)
                current = ""
            else:
                current += char

        if current.strip():
            parts.append(current)

        return parts

    async def _run_migrations(self) -> None:
        """Run database migrations for existing databases.

        Automatically adds missing columns by comparing schema.sql with existing tables.
        """
        schema_path = Path(__file__).parent / "schema.sql"
        schema = schema_path.read_text()

        # Parse expected columns from schema
        schema_tables = self._parse_schema_columns(schema)

        # For each table in schema, check and add missing columns
        for table_name, expected_columns in schema_tables.items():
            await self._migrate_table_columns(table_name, expected_columns)

    async def _migrate_table_columns(
        self, table_name: str, expected_columns: list[tuple[str, str]]
    ) -> None:
        """Add missing columns to a table.

        Args:
            table_name: Name of the table to migrate
            expected_columns: List of (column_name, column_definition) from schema
        """
        conn = self.connection
        # Get existing columns
        cursor = await conn.execute(f"PRAGMA table_info({table_name})")
        rows = await cursor.fetchall()
        existing_columns = {row["name"] for row in rows}

        # Add missing columns
        for col_name, col_def in expected_columns:
            if col_name not in existing_columns:
                # Build ALTER TABLE statement
                # SQLite requires DEFAULT for new columns if table has data
                alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                try:
                    await conn.execute(alter_sql)
                    await conn.commit()
                    logger.info(
                        f"Migration: Added column '{col_name}' to table '{table_name}'"
                    )
                except Exception as e:
                    logger.warning(
                        f"Migration: Failed to add column '{col_name}' to '{table_name}': {e}"
                    )

        # Migration: Add enable_gating_status column if it doesn't exist
        if "enable_gating_status" not in pref_column_names:
            await conn.execute(
                "ALTER TABLE user_preferences ADD COLUMN enable_gating_status INTEGER DEFAULT 0"
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
