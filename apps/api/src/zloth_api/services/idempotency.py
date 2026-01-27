"""Idempotency service for duplicate request prevention.

This module provides utilities for generating and checking idempotency keys
to prevent duplicate resource creation from retried HTTP requests.

Usage:
    1. Client provides `idempotency_key` in request body (optional but recommended)
    2. If not provided, server generates a content-based key
    3. Before creating a resource, check if the key already exists
    4. If exists, return 409 Conflict with the existing resource ID
    5. If not exists, create the resource and store the key
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from zloth_api.errors import ConflictError

if TYPE_CHECKING:
    from zloth_api.storage.dao import IdempotencyKeyDAO


@dataclass
class IdempotencyResult:
    """Result of idempotency check."""

    is_duplicate: bool
    resource_id: str | None = None
    operation: str | None = None


def generate_idempotency_key(
    operation: str,
    *,
    context_id: str | None = None,
    content: dict[str, Any] | None = None,
    client_key: str | None = None,
) -> str:
    """Generate an idempotency key from request content.

    The key is generated using SHA256 hash of the operation and content.
    If a client-provided key is given, it's used directly (with operation prefix).

    Args:
        operation: Operation type (e.g., 'run.create', 'task.create').
        context_id: Optional context ID (e.g., task_id for run creation).
        content: Dict of request content to hash.
        client_key: Optional client-provided idempotency key.

    Returns:
        32-character hex string idempotency key.

    Examples:
        # Server-generated key from content
        key = generate_idempotency_key(
            "run.create",
            context_id="task-123",
            content={"instruction": "Fix the bug", "model_ids": ["model-1"]}
        )

        # Client-provided key
        key = generate_idempotency_key(
            "run.create",
            client_key="my-unique-request-id"
        )
    """
    if client_key:
        # Use client-provided key with operation prefix for namespace isolation
        to_hash = f"{operation}:{client_key}"
    else:
        # Generate from content
        parts = [operation]
        if context_id:
            parts.append(context_id)
        if content:
            # Sort keys for consistent hashing
            sorted_content = json.dumps(content, sort_keys=True, default=str)
            parts.append(sorted_content)
        to_hash = ":".join(parts)

    return hashlib.sha256(to_hash.encode()).hexdigest()[:32]


class IdempotencyService:
    """Service for managing idempotency checks.

    This service provides a simple API for checking and storing idempotency keys.
    It's designed to be used as a context manager or with explicit check/store calls.
    """

    def __init__(self, dao: IdempotencyKeyDAO):
        """Initialize the service.

        Args:
            dao: IdempotencyKeyDAO instance for database operations.
        """
        self.dao = dao

    async def check(self, key: str) -> IdempotencyResult:
        """Check if an idempotency key already exists.

        Args:
            key: The idempotency key to check.

        Returns:
            IdempotencyResult with is_duplicate=True if exists,
            False otherwise.
        """
        existing = await self.dao.get(key)
        if existing:
            return IdempotencyResult(
                is_duplicate=True,
                resource_id=existing["resource_id"],
                operation=existing["operation"],
            )
        return IdempotencyResult(is_duplicate=False)

    async def check_and_raise(
        self,
        key: str,
        operation: str,
    ) -> None:
        """Check idempotency key and raise ConflictError if duplicate.

        Args:
            key: The idempotency key to check.
            operation: Human-readable operation name for error message.

        Raises:
            ConflictError: If the key already exists (duplicate request).
        """
        result = await self.check(key)
        if result.is_duplicate:
            raise ConflictError(
                f"Duplicate {operation} request detected",
                code="DUPLICATE_REQUEST",
                details={
                    "idempotency_key": key,
                    "existing_resource_id": result.resource_id,
                },
            )

    async def store(
        self,
        key: str,
        operation: str,
        resource_id: str,
        response_hash: str | None = None,
        ttl_seconds: int | None = None,
    ) -> bool:
        """Store an idempotency key after successful resource creation.

        Args:
            key: The idempotency key.
            operation: Operation type (e.g., 'run.create').
            resource_id: ID of the created resource.
            response_hash: Optional hash of the response.
            ttl_seconds: Time-to-live in seconds (default: 24 hours).

        Returns:
            True if stored, False if key already exists.
        """
        return await self.dao.create(
            key=key,
            operation=operation,
            resource_id=resource_id,
            response_hash=response_hash,
            ttl_seconds=ttl_seconds,
        )

    async def cleanup_expired(self) -> int:
        """Remove expired idempotency keys.

        Returns:
            Number of deleted records.
        """
        return await self.dao.cleanup_expired()


# Operation constants for consistency
class IdempotencyOperation:
    """Constants for idempotency operation types."""

    RUN_CREATE = "run.create"
    TASK_CREATE = "task.create"
    PR_CREATE = "pr.create"
    PR_CREATE_AUTO = "pr.create_auto"
    MODEL_CREATE = "model.create"
    REPO_CLONE = "repo.clone"
    REPO_SELECT = "repo.select"
