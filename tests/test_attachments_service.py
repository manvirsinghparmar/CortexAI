from __future__ import annotations

from contextlib import contextmanager
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException

from server import attachments as attachments_service


@contextmanager
def _fake_uow(*, commit_on_success: bool = False):
    _ = commit_on_success
    yield object()


def test_resolve_attachments_rejects_when_feature_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "false")
    monkeypatch.setattr(attachments_service, "API_DB_ENABLED", True)

    with pytest.raises(HTTPException) as exc:
        attachments_service.resolve_request_attachments(
            user_id=uuid4(),
            attachments=[SimpleNamespace(file_id=uuid4(), usage_role="primary", transform_mode="auto")],
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "attachments_disabled"


def test_resolve_attachments_enforces_count_limit(monkeypatch):
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "true")
    monkeypatch.setenv("ATTACHMENTS_MAX_FILES_PER_REQUEST", "1")
    monkeypatch.setattr(attachments_service, "API_DB_ENABLED", True)

    with pytest.raises(HTTPException) as exc:
        attachments_service.resolve_request_attachments(
            user_id=uuid4(),
            attachments=[
                SimpleNamespace(file_id=uuid4(), usage_role="primary", transform_mode="auto"),
                SimpleNamespace(file_id=uuid4(), usage_role="primary", transform_mode="auto"),
            ],
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "too_many_attachments"


def test_resolve_attachments_returns_ready_owned_rows(monkeypatch):
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "true")
    monkeypatch.setattr(attachments_service, "API_DB_ENABLED", True)
    monkeypatch.setattr(attachments_service, "_db_uow", _fake_uow)

    file_id = uuid4()
    monkeypatch.setattr(
        attachments_service,
        "get_uploaded_file_for_user",
        lambda *_args, **_kwargs: {
            "id": file_id,
            "original_filename": "file.pdf",
            "mime_type": "application/pdf",
            "size_bytes": 2048,
            "status": "ready",
            "storage_bucket": "bucket",
            "storage_key": "attachments/key.pdf",
            "ingestion_meta": {
                "ingestion_state": "ready",
                "cached_extracted_text": "Cached document text",
            },
        },
    )

    resolved = attachments_service.resolve_request_attachments(
        user_id=uuid4(),
        attachments=[SimpleNamespace(file_id=file_id, usage_role="reference", transform_mode="auto")],
    )
    assert len(resolved) == 1
    assert resolved[0].file_id == file_id
    assert resolved[0].mime_type == "application/pdf"
    assert resolved[0].usage_role == "reference"
    assert resolved[0].storage_key == "attachments/key.pdf"
    assert resolved[0].ingestion_meta["cached_extracted_text"] == "Cached document text"


def test_model_compatibility_rejects_deepseek_for_pdf():
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="auto",
        order_index=0,
        original_filename="file.pdf",
        mime_type="application/pdf",
        size_bytes=2048,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/file.pdf",
    )

    with pytest.raises(HTTPException) as exc:
        attachments_service.enforce_model_attachment_compatibility(
            provider="deepseek",
            model="deepseek-chat",
            attachments=[attachment],
            mode="chat",
        )

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "attachment_model_incompatible"


def test_compatible_providers_include_openai_exclude_deepseek():
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="auto",
        order_index=0,
        original_filename="file.pdf",
        mime_type="application/pdf",
        size_bytes=1024,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/file.pdf",
    )
    providers = attachments_service.compatible_providers_for_attachments([attachment])
    assert "openai" in providers
    assert "deepseek" not in providers


def test_materialize_inference_attachments_reads_storage(monkeypatch):
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="auto",
        order_index=0,
        original_filename="cat.png",
        mime_type="image/png",
        size_bytes=4,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/cat.png",
    )

    class _FakeStorage:
        def get_bytes(self, *, key: str):
            assert key == "attachments/cat.png"
            return b"\x89PNG"

    monkeypatch.setattr(attachments_service, "get_object_storage", lambda: _FakeStorage())
    items = attachments_service.materialize_inference_attachments([attachment])
    assert len(items) == 1
    assert items[0]["mime_type"] == "image/png"
    assert items[0]["filename"] == "cat.png"
    assert isinstance(items[0]["data_base64"], str) and items[0]["data_base64"]


def test_materialize_inference_attachments_extracts_json_text(monkeypatch):
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="auto",
        order_index=0,
        original_filename="payload.json",
        mime_type="application/json",
        size_bytes=32,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/payload.json",
    )

    class _FakeStorage:
        def get_bytes(self, *, key: str):
            assert key == "attachments/payload.json"
            return b'{"ok":true,"count":2}'

    monkeypatch.setattr(attachments_service, "get_object_storage", lambda: _FakeStorage())
    items = attachments_service.materialize_inference_attachments([attachment])
    assert len(items) == 1
    assert items[0]["mime_type"] == "application/json"
    assert items[0]["transform_mode"] == "text_only"
    assert "extracted_text" in items[0]
    assert '"ok": true' in items[0]["extracted_text"]
    assert "data_base64" not in items[0]


def test_materialize_reuses_cached_parse_without_reading_storage(monkeypatch):
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="reference",
        transform_mode="auto",
        order_index=0,
        original_filename="brief.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=2048,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/brief.docx",
        ingestion_meta={
            "ingestion_state": "ready",
            "cached_extracted_text": "Parsed once and reused for future questions.",
        },
    )

    monkeypatch.setattr(
        attachments_service,
        "get_object_storage",
        lambda: pytest.fail("cached text should not read object storage"),
    )

    items = attachments_service.materialize_inference_attachments([attachment])

    assert items[0]["extracted_text"].endswith(
        "Parsed once and reused for future questions."
    )
    assert items[0]["artifact_meta"]["parse_cache_reused"] is True
    assert "data_base64" not in items[0]


def test_materialize_selects_query_relevant_cached_section(monkeypatch):
    monkeypatch.setenv("ATTACHMENTS_TEXT_CHUNK_CHARS", "200")
    monkeypatch.setenv("ATTACHMENTS_REFERENCE_TEXT_MAX_CHUNKS", "1")
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="reference",
        transform_mode="auto",
        order_index=0,
        original_filename="brief.docx",
        mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        size_bytes=2048,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/brief.docx",
        ingestion_meta={
            "ingestion_state": "ready",
            "cached_extracted_text": (
                ("General introduction. " * 20)
                + "\n"
                + ("Zebra migration schedule and ownership. " * 10)
            ),
        },
    )

    items = attachments_service.materialize_inference_attachments(
        [attachment],
        query_text="What is the zebra migration schedule?",
    )

    assert "Zebra migration schedule" in items[0]["extracted_text"]
    assert items[0]["artifact_meta"]["selection_strategy"] == "query_relevance"


def test_compatible_providers_include_deepseek_for_text_materialized_attachment():
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="auto",
        order_index=0,
        original_filename="readme.txt",
        mime_type="text/plain",
        size_bytes=128,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/readme.txt",
    )

    providers = attachments_service.compatible_providers_for_attachments([attachment])
    assert "deepseek" in providers


def test_model_compatibility_allows_deepseek_for_text_materialized_attachment():
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="auto",
        order_index=0,
        original_filename="notes.txt",
        mime_type="text/plain",
        size_bytes=128,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/notes.txt",
    )

    attachments_service.enforce_model_attachment_compatibility(
        provider="deepseek",
        model="deepseek-chat",
        attachments=[attachment],
        mode="chat",
    )


def test_materialize_rejects_text_only_mode_for_pdf(monkeypatch):
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="primary",
        transform_mode="text_only",
        order_index=0,
        original_filename="file.pdf",
        mime_type="application/pdf",
        size_bytes=8,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/file.pdf",
    )

    class _FakeStorage:
        def get_bytes(self, *, key: str):
            assert key == "attachments/file.pdf"
            return b"%PDF-1.7"

    monkeypatch.setattr(attachments_service, "get_object_storage", lambda: _FakeStorage())
    with pytest.raises(HTTPException) as exc:
        attachments_service.materialize_inference_attachments([attachment])

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "unsupported_transform_mode_for_mime"


def test_build_request_attachment_persistence_items_uses_inference_artifact_meta():
    attachment = attachments_service.ResolvedAttachment(
        file_id=uuid4(),
        usage_role="reference",
        transform_mode="auto",
        order_index=0,
        original_filename="notes.txt",
        mime_type="text/plain",
        size_bytes=42,
        status="ready",
        storage_bucket="bucket",
        storage_key="attachments/notes.txt",
    )

    persistence_items = attachments_service.build_request_attachment_persistence_items(
        resolved_attachments=[attachment],
        inference_attachments=[
            {
                "file_id": str(attachment.file_id),
                "transform_mode": "text_only",
                "artifact_meta": {
                    "materialization": "text",
                    "chunk_count": 2,
                },
            }
        ],
    )

    assert len(persistence_items) == 1
    item = persistence_items[0]
    assert item["file_id"] == attachment.file_id
    assert item["usage_role"] == "reference"
    assert item["transform_mode"] == "text_only"
    assert item["resolved_artifact_meta"]["materialization"] == "text"
    assert item["resolved_artifact_meta"]["chunk_count"] == 2
