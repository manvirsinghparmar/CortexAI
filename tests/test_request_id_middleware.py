"""Tests for request id middleware correlation behavior."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from server.middleware import REQUEST_ID_HEADER, RequestIDMiddleware
from utils.logger import get_request_id


def _build_test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestIDMiddleware)

    @app.get("/ping")
    async def ping(request: Request):
        return {
            "request_id": str(getattr(request.state, "request_id", "")),
            "context_request_id": get_request_id(),
        }

    return app


def test_request_id_middleware_preserves_valid_header():
    app = _build_test_app()
    request_id = "req-valid-123"

    with TestClient(app) as client:
        response = client.get("/ping", headers={REQUEST_ID_HEADER: request_id})

    assert response.status_code == 200
    assert response.headers.get(REQUEST_ID_HEADER) == request_id
    body = response.json()
    assert body["request_id"] == request_id
    assert body["context_request_id"] == request_id


def test_request_id_middleware_replaces_invalid_header():
    app = _build_test_app()
    invalid = "invalid header with spaces"

    with TestClient(app) as client:
        response = client.get("/ping", headers={REQUEST_ID_HEADER: invalid})

    assert response.status_code == 200
    generated = str(response.headers.get(REQUEST_ID_HEADER) or "")
    assert generated
    assert generated != invalid
    body = response.json()
    assert body["request_id"] == generated
    assert body["context_request_id"] == generated


def test_request_id_context_is_reset_after_request():
    app = _build_test_app()

    with TestClient(app) as client:
        response = client.get("/ping")

    assert response.status_code == 200
    assert get_request_id() is None

