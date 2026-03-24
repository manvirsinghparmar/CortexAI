import uuid

from fastapi import HTTPException
from fastapi.testclient import TestClient
import pytest

from server.app import create_app


@pytest.fixture()
def app(monkeypatch):
    monkeypatch.setenv("API_KEYS", "dev-key-1")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("ALLOW_NON_POSTGRES_DATABASE_URL", "true")
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "true")

    app = create_app()

    # Keep existing route modules deterministic in these contract tests.
    from server.routes import chat as chat_route
    from server.routes import compare as compare_route
    from server.routes import history as history_route

    chat_route.API_DB_ENABLED = False
    compare_route.API_DB_ENABLED = False
    history_route.API_DB_ENABLED = False

    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


def test_files_upload_requires_api_key(client):
    response = client.post(
        "/v1/files/upload",
        data=b"hello",
        headers={
            "Content-Type": "text/plain",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
        },
    )
    assert response.status_code in (401, 403)


def test_files_upload_uses_service_result(client, monkeypatch):
    from server import files_service

    captured: dict[str, object] = {}

    def _fake_upload_user_file(**kwargs):
        captured.update(kwargs)
        return {
            "file_id": "7f8bb1b7-e5ef-4d6d-b8a8-43d14d6fd7bb",
            "original_filename": "demo.txt",
            "mime_type": "text/plain",
            "size_bytes": 5,
            "status": "ready",
            "error_code": None,
            "error_message": None,
            "ingestion_meta": {"ingestion_state": "none"},
            "created_at": "2026-03-20T00:00:00Z",
            "updated_at": "2026-03-20T00:00:00Z",
            "expires_at": "2026-03-27T00:00:00Z",
            "deduplicated": False,
        }

    monkeypatch.setattr(files_service, "upload_user_file", _fake_upload_user_file)

    response = client.post(
        "/v1/files/upload",
        data=b"hello",
        headers={
            "X-API-Key": "dev-key-1",
            "Content-Type": "text/plain",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == "7f8bb1b7-e5ef-4d6d-b8a8-43d14d6fd7bb"
    assert body["status"] == "ready"
    assert body["mime_type"] == "text/plain"
    assert body["size_bytes"] == 5
    assert captured["filename"] == "demo.txt"
    assert captured["mime_type"] == "text/plain"
    assert captured["payload"] == b"hello"
    assert captured["api_key"] == "dev-key-1"


def test_files_upload_propagates_http_errors(client, monkeypatch):
    from server import files_service

    def _fake_upload_user_file(**_kwargs):
        raise HTTPException(
            status_code=415,
            detail={"code": "unsupported_file_type", "message": "Unsupported file type"},
        )

    monkeypatch.setattr(files_service, "upload_user_file", _fake_upload_user_file)

    response = client.post(
        "/v1/files/upload",
        data=b"\x01\x02",
        headers={
            "X-API-Key": "dev-key-1",
            "Content-Type": "application/octet-stream",
            "X-File-Name": "demo.exe",
            "X-File-Content-Type": "application/octet-stream",
        },
    )
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_files_get_status_uses_service_result(client, monkeypatch):
    from server import files_service

    file_id = uuid.uuid4()

    def _fake_get_user_file(**kwargs):
        assert kwargs["file_id"] == file_id
        return {
            "file_id": str(file_id),
            "original_filename": "demo.txt",
            "mime_type": "text/plain",
            "size_bytes": 5,
            "status": "ready",
            "error_code": None,
            "error_message": None,
            "ingestion_meta": {"ingestion_state": "none"},
            "created_at": "2026-03-20T00:00:00Z",
            "updated_at": "2026-03-20T00:00:00Z",
            "expires_at": "2026-03-27T00:00:00Z",
            "deduplicated": False,
        }

    monkeypatch.setattr(files_service, "get_user_file", _fake_get_user_file)

    response = client.get(
        f"/v1/files/{file_id}",
        headers={"X-API-Key": "dev-key-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == str(file_id)
    assert body["status"] == "ready"
    assert body["original_filename"] == "demo.txt"
