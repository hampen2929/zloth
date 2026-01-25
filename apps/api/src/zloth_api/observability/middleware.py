"""Observability middleware for FastAPI.

This module provides middleware for request timing, metrics collection,
and structured logging context.
"""

import time

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from zloth_api.observability.metrics import HTTP_REQUEST_DURATION, HTTP_REQUESTS_TOTAL


def _normalize_path(path: str) -> str:
    """Normalize path to avoid high-cardinality metrics.

    Replaces dynamic path segments (UUIDs, IDs) with placeholders.
    """
    parts = path.strip("/").split("/")
    normalized_parts: list[str] = []

    for part in parts:
        # Check if it looks like a UUID or ID (alphanumeric with dashes, >8 chars)
        if len(part) > 8 and (part.replace("-", "").isalnum() or part.isdigit()):
            normalized_parts.append("{id}")
        else:
            normalized_parts.append(part)

    return "/" + "/".join(normalized_parts) if normalized_parts else "/"


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware to collect HTTP request metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and collect metrics."""
        # Skip metrics endpoint to avoid self-referential metrics
        if request.url.path == "/metrics":
            return await call_next(request)

        start_time = time.monotonic()
        response: Response | None = None
        status_code = 500  # Default to error if exception occurs

        try:
            response = await call_next(request)
            status_code = response.status_code
            return response
        finally:
            duration = time.monotonic() - start_time
            method = request.method
            endpoint = _normalize_path(request.url.path)

            # Record metrics
            HTTP_REQUEST_DURATION.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).observe(duration)

            HTTP_REQUESTS_TOTAL.labels(
                method=method,
                endpoint=endpoint,
                status_code=str(status_code),
            ).inc()
