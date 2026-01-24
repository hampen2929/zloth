"""FastAPI error handling and request correlation utilities."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from zloth_api.errors import ZlothError

logger = logging.getLogger(__name__)


def _get_or_create_request_id(request: Request) -> str:
    existing = request.headers.get("X-Request-ID")
    if existing:
        return existing
    return str(uuid.uuid4())


def _http_status_to_code(status_code: int) -> str:
    # Keep this mapping small and stable; clients can branch on it.
    return {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        500: "INTERNAL_ERROR",
        502: "EXTERNAL_SERVICE_ERROR",
        503: "SERVICE_UNAVAILABLE",
    }.get(status_code, "HTTP_ERROR")


def _build_error_body(
    *,
    detail: str,
    code: str,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    # Backward compatibility: the web client expects `detail`.
    body: dict[str, Any] = {"detail": detail, "error": {"code": code, "request_id": request_id}}
    if details:
        body["error"]["details"] = details
    return body


def install_error_handling(app: FastAPI) -> None:
    """Install request-id middleware and global exception handlers."""

    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = _get_or_create_request_id(request)
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response

    @app.exception_handler(ZlothError)
    async def zloth_error_handler(request: Request, exc: ZlothError) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _get_or_create_request_id(request))
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_body(
                detail=exc.message,
                code=exc.code,
                request_id=request_id,
                details=exc.details,
            ),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        # Incremental migration helper: many services still raise ValueError.
        request_id = getattr(request.state, "request_id", _get_or_create_request_id(request))
        return JSONResponse(
            status_code=400,
            content=_build_error_body(
                detail=str(exc),
                code="VALIDATION_ERROR",
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _get_or_create_request_id(request))
        detail_str = exc.detail if isinstance(exc.detail, str) else str(exc.detail)
        return JSONResponse(
            status_code=exc.status_code,
            content=_build_error_body(
                detail=detail_str,
                code=_http_status_to_code(exc.status_code),
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _get_or_create_request_id(request))
        return JSONResponse(
            status_code=422,
            content=_build_error_body(
                detail="Validation error",
                code="VALIDATION_ERROR",
                request_id=request_id,
                details={"errors": exc.errors()},
            ),
            headers={"X-Request-ID": request_id},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        request_id = getattr(request.state, "request_id", _get_or_create_request_id(request))
        logger.exception("Unhandled exception (request_id=%s): %s", request_id, exc)
        return JSONResponse(
            status_code=500,
            content=_build_error_body(
                detail="Internal server error",
                code="INTERNAL_ERROR",
                request_id=request_id,
            ),
            headers={"X-Request-ID": request_id},
        )
