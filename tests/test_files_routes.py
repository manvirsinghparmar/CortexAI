import uuid
import logging

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
    session_user_id = uuid.uuid4()

    from server import dependencies

    monkeypatch.setattr(
        dependencies,
        "parse_session",
        lambda cookie: session_user_id if cookie else None,
    )

    app = create_app()

    # Keep existing route modules deterministic in these contract tests.
    from server.routes import chat as chat_route
    from server.routes import compare as compare_route
    from server.routes import files as files_route
    from server.routes import history as history_route

    chat_route.API_DB_ENABLED = False
    compare_route.API_DB_ENABLED = False
    files_route.API_DB_ENABLED = False
    history_route.API_DB_ENABLED = False

    return app


@pytest.fixture()
def client(app):
    return TestClient(app)


@pytest.fixture()
def session_cookie():
    return {"cortex_session": "test-session-cookie"}


def test_files_upload_requires_auth(client):
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


def test_files_upload_uses_service_result(client, monkeypatch, session_cookie):
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
            "Content-Type": "text/plain",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
        },
        cookies=session_cookie,
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
    assert captured["auth"].user_id is not None
    assert captured["auth"].api_key is None


def test_files_upload_is_free_and_does_not_meter_bytes(client, monkeypatch, session_cookie):
    from server import files_service
    from server.routes import files as files_route

    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        files_service,
        "upload_user_file",
        lambda **_kwargs: {
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
        },
    )

    response = client.post(
        "/v1/files/upload",
        data=b"hello",
        headers={
            "Content-Type": "text/plain",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
        },
        cookies=session_cookie,
    )

    assert response.status_code == 200
    assert not hasattr(files_route, "_reserve_subscription_usage")
    assert not hasattr(files_route, "_finalize_subscription_usage")


def test_files_upload_relies_on_file_service_for_validation(
    client,
    monkeypatch,
    session_cookie,
):
    from server import files_service
    from server.routes import files as files_route

    def reject_upload(**_kwargs):
        raise HTTPException(
            status_code=413,
            detail={"code": "file_too_large", "message": "The file is too large."},
        )

    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(files_service, "upload_user_file", reject_upload)

    response = client.post(
        "/v1/files/upload",
        data=b"hello",
        headers={
            "Content-Type": "text/plain",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
        },
        cookies=session_cookie,
    )

    assert response.status_code == 413
    assert response.json()["detail"]["code"] == "file_too_large"


def test_files_upload_failure_does_not_attempt_credit_release(client, monkeypatch, session_cookie):
    from server import files_service
    from server.routes import files as files_route

    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)

    def fail_upload(**_kwargs):
        raise HTTPException(
            status_code=502,
            detail={"code": "storage_upload_failed", "message": "Upload failed."},
        )

    monkeypatch.setattr(files_service, "upload_user_file", fail_upload)

    response = client.post(
        "/v1/files/upload",
        data=b"hello",
        headers={
            "Content-Type": "text/plain",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
        },
        cookies=session_cookie,
    )

    assert response.status_code == 502
    assert not hasattr(files_route, "_release_subscription_usage")


def test_files_upload_propagates_http_errors(client, monkeypatch, session_cookie):
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
            "Content-Type": "application/octet-stream",
            "X-File-Name": "demo.exe",
            "X-File-Content-Type": "application/octet-stream",
        },
        cookies=session_cookie,
    )
    assert response.status_code == 415
    assert response.json()["detail"]["code"] == "unsupported_file_type"


def test_files_upload_emits_route_logging_events(client, monkeypatch, caplog, session_cookie):
    from server import files_service

    def _fake_upload_user_file(**_kwargs):
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

    caplog.set_level(logging.INFO)
    response = client.post(
        "/v1/files/upload",
        data=b"hello",
        headers={
            "Content-Type": "text/plain",
            "Content-Length": "5",
            "X-File-Name": "demo.txt",
            "X-File-Content-Type": "text/plain",
            "X-Amz-Cf-Id": "edge-id-123",
            "X-Forwarded-For": "1.1.1.1,2.2.2.2",
            "Host": "kudlo.triobrain.com",
        },
        cookies=session_cookie,
    )
    assert response.status_code == 200

    events = [getattr(record, "extra_fields", {}).get("event") for record in caplog.records]
    assert "upload.route.received" in events
    assert "upload.route.payload.read" in events
    assert "upload.route.success" in events

    received = next(
        record
        for record in caplog.records
        if getattr(record, "extra_fields", {}).get("event") == "upload.route.received"
    )
    assert received.extra_fields["has_x_api_key_header"] is False
    assert received.extra_fields["x_forwarded_for_first"] == "1.1.1.1"
    assert received.extra_fields["x_forwarded_for_hops"] == 2
    assert received.extra_fields["edge_headers"]["x_amz_cf_id"] == "edge-id-123"


def test_files_upload_logs_route_rejection(client, monkeypatch, caplog, session_cookie):
    from server import files_service

    def _fake_upload_user_file(**_kwargs):
        raise HTTPException(
            status_code=415,
            detail={"code": "unsupported_file_type", "message": "Unsupported file type"},
        )

    monkeypatch.setattr(files_service, "upload_user_file", _fake_upload_user_file)

    caplog.set_level(logging.INFO)
    response = client.post(
        "/v1/files/upload",
        data=b"\x01\x02",
        headers={
            "Content-Type": "application/octet-stream",
            "X-File-Name": "demo.exe",
            "X-File-Content-Type": "application/octet-stream",
        },
        cookies=session_cookie,
    )
    assert response.status_code == 415

    rejected = next(
        record
        for record in caplog.records
        if getattr(record, "extra_fields", {}).get("event") == "upload.route.rejected"
    )
    assert rejected.extra_fields["status_code"] == 415
    assert rejected.extra_fields["error_code"] == "unsupported_file_type"


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
        cookies={"cortex_session": "test-session-cookie"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["file_id"] == str(file_id)
    assert body["status"] == "ready"
    assert body["original_filename"] == "demo.txt"


def test_files_routes_reject_api_key_auth(client):
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
    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "session_auth_required"
