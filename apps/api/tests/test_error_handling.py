"""Tests for global error handling and request correlation."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from zloth_api.error_handling import install_error_handling
from zloth_api.errors import NotFoundError


def create_app() -> FastAPI:
    app = FastAPI()
    install_error_handling(app)

    @app.get("/boom-http")
    async def boom_http() -> None:
        raise HTTPException(status_code=404, detail="Missing")

    @app.get("/boom-domain")
    async def boom_domain() -> None:
        raise NotFoundError("Thing not found", details={"thing_id": "t-1"})

    return app


def test_http_exception_is_wrapped_with_request_id() -> None:
    client = TestClient(create_app())
    resp = client.get("/boom-http")
    assert resp.status_code == 404
    assert resp.headers.get("X-Request-ID")
    body = resp.json()
    assert body["detail"] == "Missing"
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"] == resp.headers["X-Request-ID"]


def test_domain_exception_is_wrapped_with_details() -> None:
    client = TestClient(create_app())
    resp = client.get("/boom-domain", headers={"X-Request-ID": "rid-123"})
    assert resp.status_code == 404
    assert resp.headers["X-Request-ID"] == "rid-123"
    body = resp.json()
    assert body["detail"] == "Thing not found"
    assert body["error"]["code"] == "NOT_FOUND"
    assert body["error"]["request_id"] == "rid-123"
    assert body["error"]["details"]["thing_id"] == "t-1"
