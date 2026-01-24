"""Utilities for mapping SQLite rows to Pydantic models.

This module centralizes common patterns used across DAOs:
- Converting aiosqlite.Row (or mapping-like row) into a plain dict
- Decoding JSON-serialized columns
- Applying backward-compat/default fallbacks for missing/nullable columns
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping
from typing import Any

from pydantic import BaseModel


def row_to_dict(row: Any) -> dict[str, Any]:
    """Convert a database row into a plain dict.

    Supports aiosqlite.Row (preferred) and other Mapping-like rows.
    """
    if row is None:
        raise ValueError("row is None")

    if hasattr(row, "keys"):
        # aiosqlite.Row supports .keys() and bracket access.
        keys = row.keys()  # type: ignore[no-any-return]
        return {k: row[k] for k in keys}

    if isinstance(row, Mapping):
        return dict(row)

    raise TypeError(f"Unsupported row type for mapping: {type(row)!r}")


def _coalesce_missing_or_empty(data: dict[str, Any], defaults: Mapping[str, Any]) -> None:
    for key, default in defaults.items():
        if key not in data or data[key] in (None, ""):
            data[key] = default


def _decode_json_fields(data: dict[str, Any], json_fields: set[str]) -> None:
    for key in json_fields:
        if key not in data:
            continue

        value = data[key]
        if value in (None, ""):
            continue

        if isinstance(value, (list, dict)):
            continue

        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")

        if not isinstance(value, str):
            raise TypeError(f"JSON field {key!r} must be str/bytes, got {type(value)!r}")

        try:
            data[key] = json.loads(value)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to decode JSON field {key!r}: {e}") from e


def row_to_model[ModelT: BaseModel](
    model_cls: type[ModelT],
    row: Any,
    *,
    defaults: Mapping[str, Any] | None = None,
    json_fields: set[str] | None = None,
    overrides: Mapping[str, Any] | None = None,
    postprocess: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> ModelT:
    """Convert a database row into a Pydantic model instance.

    Args:
        model_cls: Pydantic model class to validate into.
        row: aiosqlite.Row or mapping-like object.
        defaults: Fallbacks applied when key is missing or value is None/"".
        json_fields: Keys that should be JSON-decoded before validation.
        overrides: Values that should override row values (e.g., joined data).
        postprocess: Optional hook to transform the dict before validation.
    """
    data = row_to_dict(row)

    if defaults:
        _coalesce_missing_or_empty(data, defaults)

    if json_fields:
        _decode_json_fields(data, json_fields)

    if overrides:
        data.update(dict(overrides))

    if postprocess:
        data = postprocess(data)

    return model_cls.model_validate(data)
