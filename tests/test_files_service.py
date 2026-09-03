from __future__ import annotations

import logging
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from server import files_service
from server.billing.plan_catalog import get_plan_catalog
from server.dependencies import AuthResult
from server.object_storage import (
    ObjectMetadata,
    ObjectStorageNotFoundError,
    ObjectStorageOperationError,
)


@contextmanager
def _fake_uow(*, commit_on_success: bool = True):
    _ = commit_on_success
    yield object()


def _configure_enabled_db(monkeypatch):
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "true")
    monkeypatch.setattr(files_service, "API_DB_ENABLED", True)
    monkeypatch.setattr(files_service, "_db_uow", _fake_uow)
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=uuid4(), api_key_id=uuid4()),
    )


def _configure_policy_resolution(monkeypatch, plan_code: str) -> AuthResult:
    user_id = uuid4()
    _configure_enabled_db(monkeypatch)
    monkeypatch.setattr(
        files_service,
        "_resolve_identity",
        lambda **_kwargs: SimpleNamespace(user_id=user_id),
    )
    monkeypatch.setattr(
        files_service,
        "resolve_effective_subscription",
        lambda *_args, **_kwargs: SimpleNamespace(plan=get_plan_catalog().require(plan_code)),
    )
    return AuthResult(api_key=None, cognito_claims=None, user_id=user_id)


def _configure_direct_upload(monkeypatch):
    _configure_enabled_db(monkeypatch)
    monkeypatch.setenv("ATTACHMENTS_DIRECT_UPLOAD_ENABLED", "true")
    user_id = uuid4()
    auth = AuthResult(api_key=None, cognito_claims=None, user_id=user_id)
    monkeypatch.setattr(
        files_service,
        "_resolve_identity",
        lambda **_kwargs: SimpleNamespace(user_id=user_id, api_key_id=None),
    )
    monkeypatch.setattr(
        files_service,
        "resolve_upload_policy",
        lambda **_kwargs: files_service.UploadPolicy(
            user_id=user_id,
            plan_code="plus",
            max_files=3,
            max_file_bytes=20_000_000,
            platform_max_files=5,
            platform_max_file_bytes=20_000_000,
        ),
    )
    return auth, user_id


@pytest.mark.parametrize(
    ("plan_code", "expected_files", "expected_bytes"),
    [
        ("free", 1, 10_000_000),
        ("plus", 3, 20_000_000),
        ("pro", 5, 20_000_000),
    ],
)
def test_upload_policy_uses_exact_plan_file_limits(
    monkeypatch,
    plan_code,
    expected_files,
    expected_bytes,
):
    auth = _configure_policy_resolution(monkeypatch, plan_code)
    monkeypatch.setenv("ATTACHMENTS_MAX_FILES_PER_REQUEST", "10")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILE_BYTES", "25000000")

    policy = files_service.resolve_upload_policy(
        auth=auth,
        request_id=f"policy-{plan_code}",
    )

    assert policy.plan_code == plan_code
    assert policy.max_files == expected_files
    assert policy.max_file_bytes == expected_bytes


def test_upload_policy_applies_stricter_platform_and_provider_limits(monkeypatch):
    auth = _configure_policy_resolution(monkeypatch, "pro")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILES_PER_REQUEST", "2")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILE_BYTES", "5000000")

    platform_policy = files_service.resolve_upload_policy(
        auth=auth,
        request_id="policy-platform",
    )
    assert platform_policy.max_files == 2
    assert platform_policy.max_file_bytes == 5_000_000

    monkeypatch.setenv("ATTACHMENTS_MAX_FILES_PER_REQUEST", "10")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILE_BYTES", "25000000")
    provider_policy = files_service.resolve_upload_policy(
        auth=auth,
        request_id="policy-provider",
        provider="grok",
        model="grok-4-1-fast-reasoning",
    )
    assert provider_policy.max_files == 5
    assert provider_policy.max_file_bytes == 10_485_760


def test_no_attachment_model_reports_compatibility_instead_of_zero_plan_limit(monkeypatch):
    auth = _configure_policy_resolution(monkeypatch, "pro")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILES_PER_REQUEST", "5")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILE_BYTES", "20000000")

    policy = files_service.resolve_upload_policy(
        auth=auth,
        request_id="policy-deepseek-image",
        provider="deepseek",
        model="deepseek-v4-flash",
    )

    assert policy.max_files == 5
    assert policy.max_file_bytes == 20_000_000
    with pytest.raises(HTTPException) as exc:
        files_service.validate_upload_batch_metadata(
            files=[{"filename": "pixel.png", "mime_type": "image/png", "size_bytes": 67}],
            policy=policy,
            provider="deepseek",
            model="deepseek-v4-flash",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "attachment_model_incompatible"


def test_upload_rejects_when_attachments_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "false")
    monkeypatch.setattr(files_service, "API_DB_ENABLED", True)

    with pytest.raises(HTTPException) as exc:
        files_service.upload_user_file(
            api_key="dev-key-1",
            request_id="req-1",
            filename="demo.txt",
            mime_type="text/plain",
            payload=b"hello",
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "attachments_disabled"


def test_upload_rejects_unsupported_mime(monkeypatch):
    _configure_enabled_db(monkeypatch)

    with pytest.raises(HTTPException) as exc:
        files_service.upload_user_file(
            api_key="dev-key-1",
            request_id="req-2",
            filename="demo.exe",
            mime_type="application/octet-stream",
            payload=b"\x01\x02",
        )

    assert exc.value.status_code == 415
    assert exc.value.detail["code"] == "unsupported_file_type"


def test_upload_rejects_too_large(monkeypatch):
    _configure_enabled_db(monkeypatch)
    monkeypatch.setenv("ATTACHMENTS_MAX_FILE_BYTES", "3")

    with pytest.raises(HTTPException) as exc:
        files_service.upload_user_file(
            api_key="dev-key-1",
            request_id="req-3",
            filename="demo.txt",
            mime_type="text/plain",
            payload=b"hello",
        )

    assert exc.value.status_code == 413
    assert exc.value.detail["code"] == "file_too_large"


def test_upload_storage_operation_error_is_sanitized(monkeypatch):
    _configure_enabled_db(monkeypatch)
    monkeypatch.setattr(
        files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None
    )

    class _FailingStorage:
        bucket = "cortex-attachments"
        key_prefix = "attachments"

        def put_bytes(self, **_kwargs):
            raise ObjectStorageOperationError(
                "Failed to upload object to bucket 'cortex-attachments' key 'attachments/users/abc/private.pdf'"
            )

        def delete_object(self, **_kwargs):
            return None

    monkeypatch.setattr(files_service, "get_object_storage", lambda: _FailingStorage())

    with pytest.raises(HTTPException) as exc:
        files_service.upload_user_file(
            api_key="dev-key-1",
            request_id="req-storage-error",
            filename="demo.txt",
            mime_type="text/plain",
            payload=b"hello",
        )

    assert exc.value.status_code == 502
    assert exc.value.detail["code"] == "storage_upload_failed"
    assert (
        exc.value.detail["message"]
        == "This file could not be uploaded right now. Please try again in a moment."
    )
    assert "bucket" not in exc.value.detail["message"].lower()


def test_serialize_uploaded_row_hides_sensitive_error_details():
    row = {
        "id": uuid4(),
        "original_filename": "demo.txt",
        "mime_type": "text/plain",
        "size_bytes": 5,
        "status": "failed",
        "error_code": "storage_upload_failed",
        "error_message": "Failed to upload object to bucket 'cortex-attachments' key 'attachments/users/abc/private.pdf'",
        "ingestion_meta": {
            "ingestion_required": True,
            "ingestion_state": "failed",
            "last_error": "Failed to read object key attachments/users/abc/private.pdf",
            "artifact_meta": {"materialization": "text"},
        },
        "created_at": "2026-03-20T00:00:00Z",
        "updated_at": "2026-03-20T00:00:00Z",
        "expires_at": "2026-03-27T00:00:00Z",
    }

    payload = files_service._serialize_uploaded_file_row(row, deduplicated=False)

    assert (
        payload["error_message"]
        == "This file could not be uploaded right now. Please try again in a moment."
    )
    assert payload["ingestion_meta"]["ingestion_state"] == "failed"
    assert payload["ingestion_meta"]["artifact_meta"]["materialization"] == "text"
    assert "last_error" not in payload["ingestion_meta"]


def test_upload_returns_dedup_row_when_hash_exists(monkeypatch):
    _configure_enabled_db(monkeypatch)

    existing_user_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=existing_user_id, api_key_id=uuid4()),
    )

    existing_row = {
        "id": uuid4(),
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
    }
    monkeypatch.setattr(
        files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: existing_row
    )
    monkeypatch.setattr(files_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        files_service,
        "get_object_storage",
        lambda: (_ for _ in ()).throw(AssertionError("storage should not be used for dedup")),
    )

    payload = files_service.upload_user_file(
        api_key="dev-key-1",
        request_id="req-4",
        filename="demo.txt",
        mime_type="text/plain",
        payload=b"hello",
    )

    assert payload["deduplicated"] is True
    assert payload["status"] == "ready"
    assert payload["mime_type"] == "text/plain"


def test_upload_stores_object_and_metadata(monkeypatch):
    _configure_enabled_db(monkeypatch)

    user_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=user_id, api_key_id=uuid4()),
    )
    monkeypatch.setattr(
        files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(files_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)

    storage_calls: dict[str, object] = {}

    class _FakeStorage:
        bucket = "cortex-attachments"
        key_prefix = "attachments"

        def put_bytes(self, *, key, payload, content_type, metadata=None):
            storage_calls["key"] = key
            storage_calls["payload"] = payload
            storage_calls["content_type"] = content_type
            storage_calls["metadata"] = metadata or {}

        def delete_object(self, *, key):
            storage_calls["deleted"] = key

    monkeypatch.setattr(files_service, "get_object_storage", lambda: _FakeStorage())

    created_file_id = uuid4()
    monkeypatch.setattr(
        files_service, "create_uploaded_file", lambda *_args, **_kwargs: created_file_id
    )
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: {
            "id": created_file_id,
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
        },
    )

    result = files_service.upload_user_file(
        api_key="dev-key-1",
        request_id="req-5",
        filename="demo.txt",
        mime_type="text/plain",
        payload=b"hello",
    )

    assert result["file_id"] == str(created_file_id)
    assert result["deduplicated"] is False
    assert storage_calls["payload"] == b"hello"
    assert storage_calls["content_type"] == "text/plain"
    assert str(user_id) in str(storage_calls["key"])


def test_upload_docx_runs_sync_ingestion_when_small(monkeypatch):
    _configure_enabled_db(monkeypatch)

    user_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=user_id, api_key_id=uuid4()),
    )
    monkeypatch.setattr(
        files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(files_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)

    class _FakeStorage:
        bucket = "cortex-attachments"
        key_prefix = "attachments"

        def put_bytes(self, *, key, payload, content_type, metadata=None):
            _ = (key, payload, content_type, metadata)

        def delete_object(self, *, key):
            _ = key

    monkeypatch.setattr(files_service, "get_object_storage", lambda: _FakeStorage())

    created_file_id = uuid4()
    row_state = {
        "id": created_file_id,
        "original_filename": "brief.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 24,
        "status": "processing",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {"ingestion_state": "processing", "ingestion_required": True},
        "created_at": "2026-03-20T00:00:00Z",
        "updated_at": "2026-03-20T00:00:00Z",
        "expires_at": "2026-03-27T00:00:00Z",
    }

    def _fake_create_uploaded_file(_db_session, **kwargs):
        row_state.update(
            {
                "status": kwargs.get("status"),
                "ingestion_meta": kwargs.get("ingestion_meta", {}),
            }
        )
        return created_file_id

    def _fake_update_uploaded_file_status(_db_session, **kwargs):
        row_state.update(
            {
                "status": kwargs.get("status", row_state["status"]),
                "error_code": kwargs.get("error_code"),
                "error_message": kwargs.get("error_message"),
                "ingestion_meta": kwargs.get("ingestion_meta", row_state.get("ingestion_meta", {})),
            }
        )
        return True

    monkeypatch.setattr(files_service, "create_uploaded_file", _fake_create_uploaded_file)
    monkeypatch.setattr(
        files_service, "update_uploaded_file_status", _fake_update_uploaded_file_status
    )
    monkeypatch.setattr(
        files_service, "get_uploaded_file_for_user", lambda *_args, **_kwargs: dict(row_state)
    )
    monkeypatch.setattr(
        files_service.attachments_service,
        "extract_text_attachment_artifact",
        lambda **_kwargs: {
            "effective_transform_mode": "text_only",
            "extracted_text": "Document text.",
            "artifact_meta": {"chunk_count": 1, "materialization": "text"},
        },
    )

    result = files_service.upload_user_file(
        api_key="dev-key-1",
        request_id="req-docx-small",
        filename="brief.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        payload=b"PK\x03\x04....",
    )

    assert result["status"] == "ready"
    assert result["ingestion_meta"]["ingestion_state"] == "ready"
    assert result["ingestion_meta"]["ingestion_required"] is True
    assert result["ingestion_meta"]["artifact_meta"]["materialization"] == "text"
    assert row_state["ingestion_meta"]["cached_extracted_text"] == "Document text."
    assert "cached_extracted_text" not in result["ingestion_meta"]


def test_upload_docx_large_defers_processing(monkeypatch):
    _configure_enabled_db(monkeypatch)
    monkeypatch.setenv("ATTACHMENTS_SYNC_INGEST_MAX_BYTES", "8")

    user_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=user_id, api_key_id=uuid4()),
    )
    monkeypatch.setattr(
        files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None
    )
    monkeypatch.setattr(files_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        files_service.attachments_service,
        "extract_text_attachment_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("sync extraction should be deferred")
        ),
    )

    class _FakeStorage:
        bucket = "cortex-attachments"
        key_prefix = "attachments"

        def put_bytes(self, *, key, payload, content_type, metadata=None):
            _ = (key, payload, content_type, metadata)

        def delete_object(self, *, key):
            _ = key

    monkeypatch.setattr(files_service, "get_object_storage", lambda: _FakeStorage())

    created_file_id = uuid4()
    row_state = {
        "id": created_file_id,
        "original_filename": "heavy.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 64,
        "status": "processing",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {"ingestion_state": "processing", "ingestion_required": True},
        "created_at": "2026-03-20T00:00:00Z",
        "updated_at": "2026-03-20T00:00:00Z",
        "expires_at": "2026-03-27T00:00:00Z",
    }

    def _fake_create_uploaded_file(_db_session, **kwargs):
        row_state.update(
            {
                "status": kwargs.get("status"),
                "ingestion_meta": kwargs.get("ingestion_meta", {}),
            }
        )
        return created_file_id

    def _fake_update_uploaded_file_status(_db_session, **kwargs):
        row_state.update(
            {
                "status": kwargs.get("status", row_state["status"]),
                "error_code": kwargs.get("error_code"),
                "error_message": kwargs.get("error_message"),
                "ingestion_meta": kwargs.get("ingestion_meta", row_state.get("ingestion_meta", {})),
            }
        )
        return True

    monkeypatch.setattr(files_service, "create_uploaded_file", _fake_create_uploaded_file)
    monkeypatch.setattr(
        files_service, "update_uploaded_file_status", _fake_update_uploaded_file_status
    )
    monkeypatch.setattr(
        files_service, "get_uploaded_file_for_user", lambda *_args, **_kwargs: dict(row_state)
    )

    result = files_service.upload_user_file(
        api_key="dev-key-1",
        request_id="req-docx-large",
        filename="heavy.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        payload=b"x" * 64,
    )

    assert result["status"] == "processing"
    assert result["ingestion_meta"]["ingestion_required"] is True
    assert result["ingestion_meta"]["ingestion_state"] == "processing"
    assert result["ingestion_meta"]["deferred_reason"] == "size_exceeds_sync_inline_limit"


def test_get_user_file_finalizes_processing_file(monkeypatch):
    _configure_enabled_db(monkeypatch)

    user_id = uuid4()
    file_id = uuid4()
    row_state = {
        "id": file_id,
        "original_filename": "deferred.docx",
        "mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "size_bytes": 24,
        "status": "processing",
        "storage_key": "attachments/deferred.docx",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {"ingestion_state": "processing", "ingestion_required": True},
        "created_at": "2026-03-20T00:00:00Z",
        "updated_at": "2026-03-20T00:00:00Z",
        "expires_at": "2026-03-27T00:00:00Z",
    }

    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=user_id, api_key_id=uuid4()),
    )
    monkeypatch.setattr(
        files_service, "get_uploaded_file_for_user", lambda *_args, **_kwargs: dict(row_state)
    )
    monkeypatch.setattr(
        files_service, "get_uploaded_file_by_id", lambda *_args, **_kwargs: dict(row_state)
    )

    class _FakeStorage:
        def get_bytes(self, *, key):
            assert key == "attachments/deferred.docx"
            return b"PK\x03\x04...."

    monkeypatch.setattr(files_service, "get_object_storage", lambda: _FakeStorage())
    monkeypatch.setattr(
        files_service.attachments_service,
        "extract_text_attachment_artifact",
        lambda **_kwargs: {
            "effective_transform_mode": "text_only",
            "extracted_text": "Finalized text",
            "artifact_meta": {"chunk_count": 1, "materialization": "text"},
        },
    )

    def _fake_update_uploaded_file_status(_db_session, **kwargs):
        row_state.update(
            {
                "status": kwargs.get("status", row_state["status"]),
                "error_code": kwargs.get("error_code"),
                "error_message": kwargs.get("error_message"),
                "ingestion_meta": kwargs.get("ingestion_meta", row_state.get("ingestion_meta", {})),
            }
        )
        return True

    monkeypatch.setattr(
        files_service, "update_uploaded_file_status", _fake_update_uploaded_file_status
    )

    result = files_service.get_user_file(
        api_key="dev-key-1",
        request_id="req-status",
        file_id=file_id,
    )

    assert result["status"] == "ready"
    assert result["ingestion_meta"]["ingestion_state"] == "ready"
    assert result["ingestion_meta"]["artifact_meta"]["materialization"] == "text"


def test_upload_resolves_identity_from_session_auth(monkeypatch):
    _configure_enabled_db(monkeypatch)

    session_user_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_identity",
        lambda **_kwargs: SimpleNamespace(user_id=session_user_id, api_key_id=None),
    )
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("API-key-only resolver should not be used")
        ),
    )

    existing_row = {
        "id": uuid4(),
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
    }
    monkeypatch.setattr(
        files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: existing_row
    )

    payload = files_service.upload_user_file(
        auth=AuthResult(api_key=None, cognito_claims=None, user_id=session_user_id),
        request_id="req-session-auth",
        filename="demo.txt",
        mime_type="text/plain",
        payload=b"hello",
    )

    assert payload["deduplicated"] is True
    assert payload["status"] == "ready"


def test_get_user_file_resolves_identity_from_session_auth(monkeypatch):
    _configure_enabled_db(monkeypatch)

    session_user_id = uuid4()
    file_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_identity",
        lambda **_kwargs: SimpleNamespace(user_id=session_user_id, api_key_id=None),
    )
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("API-key-only resolver should not be used")
        ),
    )
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: {
            "id": file_id,
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
        },
    )

    result = files_service.get_user_file(
        auth=AuthResult(api_key=None, cognito_claims=None, user_id=session_user_id),
        request_id="req-session-status",
        file_id=file_id,
    )

    assert result["file_id"] == str(file_id)
    assert result["status"] == "ready"


def test_direct_upload_intent_persists_server_owned_key_and_presigned_post(monkeypatch):
    auth, user_id = _configure_direct_upload(monkeypatch)
    rows: dict[object, dict] = {}
    presign_calls: list[dict] = []

    class Storage:
        bucket = "cortex-files"
        key_prefix = "attachments"

        def create_presigned_post(self, **kwargs):
            presign_calls.append(kwargs)
            return SimpleNamespace(
                url="https://cortex-files.s3.amazonaws.com",
                fields={
                    "key": kwargs["key"],
                    "Content-Type": kwargs["content_type"],
                    "x-amz-meta-cortex-file-id": kwargs["file_id"],
                    "policy": "opaque",
                },
            )

    monkeypatch.setattr(files_service, "get_object_storage", lambda: Storage())

    def create(_db, **kwargs):
        rows[kwargs["file_id"]] = {
            "id": kwargs["file_id"],
            "original_filename": kwargs["original_filename"],
            "mime_type": kwargs["mime_type"],
            "size_bytes": kwargs["size_bytes"],
            "status": kwargs["status"],
            "error_code": None,
            "error_message": None,
            "ingestion_meta": kwargs["ingestion_meta"],
            "storage_bucket": kwargs["storage_bucket"],
            "storage_key": kwargs["storage_key"],
            "sha256": kwargs["sha256"],
            "created_at": datetime.now(timezone.utc),
            "updated_at": None,
            "expires_at": kwargs["expires_at"],
        }
        return kwargs["file_id"]

    monkeypatch.setattr(files_service, "create_uploaded_file", create)
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda _db, **kwargs: dict(rows[kwargs["file_id"]]),
    )

    result = files_service.create_direct_upload_intents(
        auth=auth,
        request_id="intent-1",
        files=[
            {"filename": "Quarterly report.pdf", "mime_type": "application/pdf", "size_bytes": 500}
        ],
    )

    assert len(result) == 1
    file_id = result[0]["file_id"]
    row = rows[next(iter(rows))]
    assert row["status"] == "uploading"
    assert row["sha256"] is None
    assert row["storage_key"].startswith(f"attachments/users/{user_id}/")
    assert row["storage_key"].endswith(f"{file_id}-Quarterly_report.pdf")
    assert presign_calls[0]["max_size_bytes"] == 500
    assert presign_calls[0]["file_id"] == file_id
    assert result[0]["upload"]["fields"]["policy"] == "opaque"


def test_direct_upload_validates_entire_batch_before_creating_rows(monkeypatch):
    auth, _user_id = _configure_direct_upload(monkeypatch)
    create_calls: list[dict] = []
    monkeypatch.setattr(
        files_service,
        "create_uploaded_file",
        lambda _db, **kwargs: create_calls.append(kwargs),
    )

    with pytest.raises(HTTPException) as exc:
        files_service.create_direct_upload_intents(
            auth=auth,
            request_id="intent-invalid",
            files=[
                {"filename": "ok.txt", "mime_type": "text/plain", "size_bytes": 5},
                {
                    "filename": "too-large.txt",
                    "mime_type": "text/plain",
                    "size_bytes": 20_000_001,
                },
            ],
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "feature_not_in_plan"
    assert create_calls == []


def test_direct_upload_rejects_model_mime_incompatibility_before_insert(monkeypatch):
    auth, _user_id = _configure_direct_upload(monkeypatch)
    create_calls: list[dict] = []
    monkeypatch.setattr(
        files_service,
        "create_uploaded_file",
        lambda _db, **kwargs: create_calls.append(kwargs),
    )

    with pytest.raises(HTTPException) as exc:
        files_service.create_direct_upload_intents(
            auth=auth,
            request_id="intent-incompatible",
            provider="grok",
            model="grok-4-1-fast-reasoning",
            files=[{"filename": "contract.pdf", "mime_type": "application/pdf", "size_bytes": 500}],
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "attachment_mime_type_incompatible"
    assert create_calls == []


def test_complete_direct_upload_verifies_object_and_is_idempotent(monkeypatch, caplog):
    auth, user_id = _configure_direct_upload(monkeypatch)
    file_id = uuid4()
    row = {
        "id": file_id,
        "user_id": user_id,
        "original_filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 5,
        "status": "uploading",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {"ingestion_state": "awaiting_upload"},
        "storage_bucket": "cortex-files",
        "storage_key": f"attachments/users/{user_id}/{file_id}-notes.txt",
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
    }
    head_calls = 0

    class Storage:
        bucket = "cortex-files"

        def head_object(self, *, key):
            nonlocal head_calls
            head_calls += 1
            assert key == row["storage_key"]
            return ObjectMetadata(
                content_length=5,
                content_type="text/plain",
                metadata={"cortex-file-id": str(file_id)},
            )

    monkeypatch.setattr(files_service, "get_object_storage", lambda: Storage())
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: dict(row),
    )

    def update(_db, **kwargs):
        row.update(kwargs)
        return True

    monkeypatch.setattr(files_service, "update_uploaded_file_status", update)

    with caplog.at_level(logging.INFO, logger=files_service.logger.name):
        first = files_service.complete_direct_upload(
            auth=auth,
            request_id="complete-1",
            file_id=file_id,
        )
        second = files_service.complete_direct_upload(
            auth=auth,
            request_id="complete-2",
            file_id=file_id,
        )

    assert first["status"] == "ready"
    assert second["status"] == "ready"
    assert head_calls == 1
    assert row["expires_at"] > datetime.now(timezone.utc) + timedelta(days=6)
    events = [getattr(record, "extra_fields", {}).get("event") for record in caplog.records]
    assert "upload.completion.verified" in events
    assert "upload.completion.idempotent" in events


def test_complete_direct_upload_rejects_object_metadata_mismatch(monkeypatch):
    auth, user_id = _configure_direct_upload(monkeypatch)
    file_id = uuid4()
    row = {
        "id": file_id,
        "user_id": user_id,
        "original_filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 5,
        "status": "uploading",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {},
        "storage_bucket": "cortex-files",
        "storage_key": "attachments/notes.txt",
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
    }

    class Storage:
        bucket = "cortex-files"

        def head_object(self, *, key):
            return ObjectMetadata(
                content_length=4,
                content_type="text/plain",
                metadata={"cortex-file-id": str(file_id)},
            )

    monkeypatch.setattr(files_service, "get_object_storage", lambda: Storage())
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: dict(row),
    )

    def update(_db, **kwargs):
        row.update(kwargs)
        return True

    monkeypatch.setattr(files_service, "update_uploaded_file_status", update)

    with pytest.raises(HTTPException) as exc:
        files_service.complete_direct_upload(
            auth=auth,
            request_id="complete-mismatch",
            file_id=file_id,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "attachment_upload_mismatch"
    assert row["status"] == "failed"


def test_complete_direct_upload_reports_missing_s3_object_without_failing_intent(monkeypatch):
    auth, user_id = _configure_direct_upload(monkeypatch)
    file_id = uuid4()
    row = {
        "id": file_id,
        "user_id": user_id,
        "original_filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 5,
        "status": "uploading",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {},
        "storage_bucket": "cortex-files",
        "storage_key": "attachments/notes.txt",
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(minutes=30),
    }

    class Storage:
        bucket = "cortex-files"

        def head_object(self, *, key):
            raise ObjectStorageNotFoundError("missing")

    monkeypatch.setattr(files_service, "get_object_storage", lambda: Storage())
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: dict(row),
    )

    with pytest.raises(HTTPException) as exc:
        files_service.complete_direct_upload(
            auth=auth,
            request_id="complete-missing",
            file_id=file_id,
        )

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "attachment_upload_not_complete"
    assert row["status"] == "uploading"


def test_complete_direct_upload_expires_and_queues_stale_intent(monkeypatch):
    auth, user_id = _configure_direct_upload(monkeypatch)
    file_id = uuid4()
    row = {
        "id": file_id,
        "user_id": user_id,
        "original_filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 5,
        "status": "uploading",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {},
        "storage_bucket": "cortex-files",
        "storage_key": "attachments/notes.txt",
        "created_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "updated_at": None,
        "expires_at": datetime.now(timezone.utc) - timedelta(minutes=1),
    }
    queued: list[object] = []
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: dict(row),
    )
    monkeypatch.setattr(
        files_service,
        "update_uploaded_file_status",
        lambda _db, **kwargs: row.update(kwargs) or True,
    )
    monkeypatch.setattr(
        files_service,
        "enqueue_file_deletion_job",
        lambda _db, **kwargs: queued.append(kwargs["file_id"]) or uuid4(),
    )

    with pytest.raises(HTTPException) as exc:
        files_service.complete_direct_upload(
            auth=auth,
            request_id="complete-expired",
            file_id=file_id,
        )

    assert exc.value.status_code == 410
    assert exc.value.detail["code"] == "attachment_upload_expired"
    assert row["status"] == "expired"
    assert queued == [file_id]


def test_delete_user_file_queues_once_and_returns_deleting(monkeypatch):
    auth, user_id = _configure_direct_upload(monkeypatch)
    file_id = uuid4()
    row = {
        "id": file_id,
        "user_id": user_id,
        "original_filename": "notes.txt",
        "mime_type": "text/plain",
        "size_bytes": 5,
        "status": "ready",
        "error_code": None,
        "error_message": None,
        "ingestion_meta": {},
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "expires_at": datetime.now(timezone.utc) + timedelta(days=7),
    }
    queued: list[object] = []
    monkeypatch.setattr(
        files_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: dict(row),
    )
    monkeypatch.setattr(
        files_service,
        "update_uploaded_file_status",
        lambda _db, **kwargs: row.update(kwargs) or True,
    )
    monkeypatch.setattr(
        files_service,
        "enqueue_file_deletion_job",
        lambda _db, **kwargs: queued.append(kwargs["file_id"]) or uuid4(),
    )

    first = files_service.delete_user_file(
        auth=auth,
        request_id="delete-1",
        file_id=file_id,
    )
    second = files_service.delete_user_file(
        auth=auth,
        request_id="delete-2",
        file_id=file_id,
    )

    assert first["status"] == "deleting"
    assert second["status"] == "deleting"
    assert queued == [file_id]


def test_direct_upload_migration_allows_null_hash_and_new_lifecycle_states():
    migration = (
        Path("db/migrations/20260811_add_direct_s3_attachment_upload.sql")
        .read_text(encoding="utf-8")
        .lower()
    )

    assert "alter column sha256 drop not null" in migration
    assert "'uploading'::text" in migration
    assert "'deleting'::text" in migration
    assert "'ready'::text" in migration
    assert migration.lstrip().startswith("-- direct-to-s3")
    assert migration.rstrip().endswith("commit;")
