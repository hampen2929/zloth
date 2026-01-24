"""Application error types for consistent API error handling.

This module defines a small exception hierarchy for domain/service errors.
These exceptions are converted to consistent HTTP responses by the global
exception handlers installed in `zloth_api.error_handling`.
"""

from __future__ import annotations

from typing import Any


class ZlothError(Exception):
    """Base exception for predictable application errors.

    Note: Avoid frozen dataclasses for exceptions; some frameworks attempt to
    mutate ``__traceback__`` and other attributes during handling, which breaks
    with frozen/slots dataclass exceptions.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "UNKNOWN",
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.message


class NotFoundError(ZlothError):
    """Resource not found (404)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "NOT_FOUND",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message=message, code=code, status_code=404, details=details)


class ValidationError(ZlothError):
    """Invalid user input / request (400)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "VALIDATION_ERROR",
        details: dict[str, Any] | None = None,
        status_code: int = 400,
    ):
        super().__init__(message=message, code=code, status_code=status_code, details=details)


class ForbiddenError(ZlothError):
    """Forbidden / permission error (403)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "FORBIDDEN",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message=message, code=code, status_code=403, details=details)


class ConflictError(ZlothError):
    """Conflict (409)."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "CONFLICT",
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message=message, code=code, status_code=409, details=details)


class ExternalServiceError(ZlothError):
    """Upstream dependency error (502)."""

    def __init__(
        self,
        message: str = "Upstream service error",
        *,
        code: str = "EXTERNAL_SERVICE_ERROR",
        details: Optional[Dict[str, Any]] = None,
        status_code: int = 502,
    ):
        super().__init__(message=message, code=code, status_code=status_code, details=details)
