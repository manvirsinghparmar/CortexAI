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


def _upload_result(file_id: uuid.UUID, filename: str, *, size_bytes: int = 5):
    return {
        "file_id": str(file_id),
        "original_filename": filename,
        "mime_type": "text/plain",
        "size_bytes": size_bytes,
        "status": "ready",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {"ingestion_state": "none"},
        "created_at": "2026-03-20T00:00:00Z",
        "updated_at": "2026-03-20T00:00:00Z",
        "expires_at": "2026-03-27T00:00:00Z",
        "deduplicated": False,
    }


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
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="free",
            max_files=1,
            max_file_bytes=10_000_000,
            platform_max_files=5,
            platform_max_file_bytes=20_000_000,
        ),
    )
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
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="free",
            max_files=1,
            max_file_bytes=10_000_000,
            platform_max_files=5,
            platform_max_file_bytes=20_000_000,
        ),
    )
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
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="free",
            max_files=1,
            max_file_bytes=10_000_000,
            platform_max_files=5,
            platform_max_file_bytes=20_000_000,
        ),
    )

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


def test_batch_upload_rejects_plan_file_count_before_storage(
    client,
    monkeypatch,
    session_cookie,
):
    from server import files_service
    from server.routes import files as files_route

    upload_calls: list[dict] = []
    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="free",
            max_files=1,
            max_file_bytes=10,
            platform_max_files=5,
            platform_max_file_bytes=20,
        ),
    )
    monkeypatch.setattr(
        files_service,
        "upload_user_file",
        lambda **kwargs: upload_calls.append(kwargs),
    )

    response = client.post(
        "/v1/files/upload-batch",
        files=[
            ("files", ("first.txt", b"one", "text/plain")),
            ("files", ("second.txt", b"two", "text/plain")),
        ],
        cookies=session_cookie,
    )

    assert response.status_code == 403
    assert response.json()["detail"] == {
        "code": "feature_not_in_plan",
        "message": "The Free plan allows up to 1 files per request and 10 bytes per file.",
        "feature": "attachment_count",
        "current_plan": "free",
        "limit": 1,
        "required": 2,
        "recommended_plan": "plus",
    }
    assert upload_calls == []


def test_batch_upload_rejects_size_and_mime_before_storage(
    client,
    monkeypatch,
    session_cookie,
):
    from server import files_service
    from server.routes import files as files_route

    upload_calls: list[dict] = []
    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="free",
            max_files=1,
            max_file_bytes=4,
            platform_max_files=5,
            platform_max_file_bytes=20,
        ),
    )
    monkeypatch.setattr(
        files_service,
        "upload_user_file",
        lambda **kwargs: upload_calls.append(kwargs),
    )

    too_large = client.post(
        "/v1/files/upload-batch",
        files=[("files", ("large.txt", b"hello", "text/plain"))],
        cookies=session_cookie,
    )
    unsupported = client.post(
        "/v1/files/upload-batch",
        files=[("files", ("demo.exe", b"x", "application/octet-stream"))],
        cookies=session_cookie,
    )

    assert too_large.status_code == 403
    assert too_large.json()["detail"]["feature"] == "attachment_size"
    assert unsupported.status_code == 415
    assert unsupported.json()["detail"]["code"] == "unsupported_file_type"
    assert upload_calls == []


def test_batch_upload_rolls_back_created_objects_after_partial_failure(
    client,
    monkeypatch,
    session_cookie,
):
    from server import files_service
    from server.routes import files as files_route

    first_file_id = uuid.uuid4()
    upload_count = 0
    rollbacks: list[uuid.UUID] = []

    def upload(**kwargs):
        nonlocal upload_count
        upload_count += 1
        if upload_count == 2:
            raise HTTPException(
                status_code=502,
                detail={"code": "storage_upload_failed", "message": "Upload failed."},
            )
        return _upload_result(first_file_id, kwargs["filename"], size_bytes=len(kwargs["payload"]))

    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="plus",
            max_files=3,
            max_file_bytes=20,
            platform_max_files=5,
            platform_max_file_bytes=20,
        ),
    )
    monkeypatch.setattr(files_service, "upload_user_file", upload)
    monkeypatch.setattr(
        files_service,
        "rollback_batch_upload",
        lambda **kwargs: rollbacks.append(kwargs["file_id"]),
    )

    response = client.post(
        "/v1/files/upload-batch",
        files=[
            ("files", ("first.txt", b"one", "text/plain")),
            ("files", ("second.txt", b"two", "text/plain")),
        ],
        cookies=session_cookie,
    )

    assert response.status_code == 502
    assert rollbacks == [first_file_id]


def test_batch_upload_returns_every_validated_file(client, monkeypatch, session_cookie):
    from server import files_service
    from server.routes import files as files_route

    monkeypatch.setattr(files_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=uuid.uuid4(),
            plan_code="plus",
            max_files=3,
            max_file_bytes=20,
            platform_max_files=5,
            platform_max_file_bytes=20,
        ),
    )
    monkeypatch.setattr(
        files_service,
        "upload_user_file",
        lambda **kwargs: _upload_result(
            uuid.uuid4(),
            kwargs["filename"],
            size_bytes=len(kwargs["payload"]),
        ),
    )

    response = client.post(
        "/v1/files/upload-batch",
        files=[
            ("files", ("first.txt", b"one", "text/plain")),
            ("files", ("second.txt", b"two", "text/plain")),
        ],
        cookies=session_cookie,
    )

    assert response.status_code == 200
    assert [item["original_filename"] for item in response.json()["files"]] == [
        "first.txt",
        "second.txt",
    ]
