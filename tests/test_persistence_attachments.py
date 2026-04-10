from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from server import persistence as persistence_service


def test_persist_request_attachments_creates_rows(monkeypatch):
    llm_request_id = uuid4()
    file_a = uuid4()
    file_b = uuid4()
    captured: list[dict] = []

    def _fake_create_request_attachment(db_session, **kwargs):
        _ = db_session
        captured.append(kwargs)
        return uuid4()

    monkeypatch.setattr(
        persistence_service,
        "create_request_attachment",
        _fake_create_request_attachment,
    )

    persistence_service._persist_request_attachments(
        object(),
        llm_request_id=llm_request_id,
        attachments=[
            SimpleNamespace(
                file_id=file_a,
                usage_role="primary",
                transform_mode="auto",
                order_index=0,
                resolved_artifact_meta={"a": 1},
            ),
            {
                "file_id": file_b,
                "usage_role": "reference",
                "transform_mode": "text_only",
                "order_index": 1,
            },
        ],
    )

    assert len(captured) == 2
    assert captured[0]["llm_request_id"] == llm_request_id
    assert captured[0]["file_id"] == file_a
    assert captured[0]["usage_role"] == "primary"
    assert captured[1]["file_id"] == file_b
    assert captured[1]["usage_role"] == "reference"
    assert captured[1]["transform_mode"] == "text_only"


def test_persist_request_attachments_noop_for_empty(monkeypatch):
    called = {"value": False}

    def _fake_create_request_attachment(*_args, **_kwargs):
        called["value"] = True
        return uuid4()

    monkeypatch.setattr(
        persistence_service,
        "create_request_attachment",
        _fake_create_request_attachment,
    )

    persistence_service._persist_request_attachments(
        object(),
        llm_request_id=uuid4(),
        attachments=[],
    )
    persistence_service._persist_request_attachments(
        object(),
        llm_request_id=uuid4(),
        attachments=None,
    )

    assert called["value"] is False
