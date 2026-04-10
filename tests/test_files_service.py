from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from server import files_service
from server.object_storage import ObjectStorageOperationError


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
    monkeypatch.setattr(files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None)

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
    assert exc.value.detail["message"] == "This file could not be uploaded right now. Please try again in a moment."
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

    assert payload["error_message"] == "This file could not be uploaded right now. Please try again in a moment."
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
    monkeypatch.setattr(files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: existing_row)
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
    monkeypatch.setattr(files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None)
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
    monkeypatch.setattr(files_service, "create_uploaded_file", lambda *_args, **_kwargs: created_file_id)
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
    monkeypatch.setattr(files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None)
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
    monkeypatch.setattr(files_service, "update_uploaded_file_status", _fake_update_uploaded_file_status)
    monkeypatch.setattr(files_service, "get_uploaded_file_for_user", lambda *_args, **_kwargs: dict(row_state))
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


def test_upload_docx_large_defers_processing(monkeypatch):
    _configure_enabled_db(monkeypatch)
    monkeypatch.setenv("ATTACHMENTS_SYNC_INGEST_MAX_BYTES", "8")

    user_id = uuid4()
    monkeypatch.setattr(
        files_service,
        "_resolve_api_key_for_request",
        lambda **_kwargs: SimpleNamespace(user_id=user_id, api_key_id=uuid4()),
    )
    monkeypatch.setattr(files_service, "find_active_uploaded_file_by_hash", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(files_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        files_service.attachments_service,
        "extract_text_attachment_artifact",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("sync extraction should be deferred")),
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
    monkeypatch.setattr(files_service, "update_uploaded_file_status", _fake_update_uploaded_file_status)
    monkeypatch.setattr(files_service, "get_uploaded_file_for_user", lambda *_args, **_kwargs: dict(row_state))

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
    monkeypatch.setattr(files_service, "get_uploaded_file_for_user", lambda *_args, **_kwargs: dict(row_state))
    monkeypatch.setattr(files_service, "get_uploaded_file_by_id", lambda *_args, **_kwargs: dict(row_state))

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

    monkeypatch.setattr(files_service, "update_uploaded_file_status", _fake_update_uploaded_file_status)

    result = files_service.get_user_file(
        api_key="dev-key-1",
        request_id="req-status",
        file_id=file_id,
    )

    assert result["status"] == "ready"
    assert result["ingestion_meta"]["ingestion_state"] == "ready"
    assert result["ingestion_meta"]["artifact_meta"]["materialization"] == "text"
