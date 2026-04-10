from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4

from server import attachment_cleanup
from server.object_storage import ObjectStorageOperationError


@contextmanager
def _fake_uow(*, commit_on_success: bool = True):
    _ = commit_on_success
    yield object()


def _configure_enabled_db(monkeypatch):
    monkeypatch.setenv("ENABLE_ATTACHMENTS", "true")
    monkeypatch.setattr(attachment_cleanup, "API_DB_ENABLED", True)
    monkeypatch.setattr(attachment_cleanup, "_db_uow", _fake_uow)


def test_queue_expired_files_marks_and_enqueues(monkeypatch):
    _configure_enabled_db(monkeypatch)
    now_utc = datetime(2026, 3, 20, tzinfo=timezone.utc)
    file_a = uuid4()
    file_b = uuid4()

    monkeypatch.setattr(
        attachment_cleanup,
        "list_expired_uploaded_files",
        lambda *_args, **_kwargs: [
            {"id": file_a, "status": "uploaded"},
            {"id": file_b, "status": "expired"},
        ],
    )

    updated_rows: list[dict] = []
    enqueued: list[dict] = []

    def _fake_update_uploaded_file_status(_db_session, **kwargs):
        updated_rows.append(kwargs)
        return True

    def _fake_enqueue_file_deletion_job(_db_session, **kwargs):
        enqueued.append(kwargs)
        return UUID(str(kwargs["file_id"]))

    monkeypatch.setattr(
        attachment_cleanup,
        "update_uploaded_file_status",
        _fake_update_uploaded_file_status,
    )
    monkeypatch.setattr(
        attachment_cleanup,
        "enqueue_file_deletion_job",
        _fake_enqueue_file_deletion_job,
    )

    stats = attachment_cleanup.queue_expired_files(now_utc=now_utc, limit=25)

    assert stats.expired_scanned == 2
    assert stats.expired_marked == 1
    assert stats.delete_jobs_enqueued == 2
    assert updated_rows[0]["file_id"] == file_a
    assert updated_rows[0]["status"] == "expired"
    assert len(enqueued) == 2


def test_process_file_deletion_queue_succeeds(monkeypatch):
    _configure_enabled_db(monkeypatch)
    now_utc = datetime(2026, 3, 20, tzinfo=timezone.utc)
    job_id = uuid4()
    file_id = uuid4()

    deleted_keys: list[str] = []

    class _FakeStorage:
        def delete_object(self, *, key: str):
            deleted_keys.append(key)

    monkeypatch.setattr(attachment_cleanup, "get_object_storage", lambda: _FakeStorage())
    monkeypatch.setattr(
        attachment_cleanup,
        "list_due_file_deletion_jobs",
        lambda *_args, **_kwargs: [
            {"id": job_id, "file_id": file_id, "attempt_count": 0, "status": "pending"}
        ],
    )
    monkeypatch.setattr(
        attachment_cleanup,
        "get_uploaded_file_by_id",
        lambda *_args, **_kwargs: {
            "id": file_id,
            "status": "expired",
            "deleted_at": None,
            "storage_key": "attachments/file-a",
        },
    )

    job_updates: list[dict] = []
    file_updates: list[dict] = []
    monkeypatch.setattr(
        attachment_cleanup,
        "update_file_deletion_job",
        lambda _db_session, **kwargs: job_updates.append(kwargs) or True,
    )
    monkeypatch.setattr(
        attachment_cleanup,
        "update_uploaded_file_status",
        lambda _db_session, **kwargs: file_updates.append(kwargs) or True,
    )

    stats = attachment_cleanup.process_file_deletion_queue(now_utc=now_utc, limit=10, max_attempts=3)

    assert stats.delete_jobs_seen == 1
    assert stats.delete_jobs_succeeded == 1
    assert stats.delete_jobs_retried == 0
    assert deleted_keys == ["attachments/file-a"]
    assert any(item["status"] == "succeeded" for item in job_updates)
    assert any(item["status"] == "deleted" for item in file_updates)


def test_process_file_deletion_queue_marks_failed_when_attempt_cap_reached(monkeypatch):
    _configure_enabled_db(monkeypatch)
    now_utc = datetime(2026, 3, 20, tzinfo=timezone.utc)
    job_id = uuid4()
    file_id = uuid4()

    class _FakeStorage:
        def delete_object(self, *, key: str):
            raise ObjectStorageOperationError(f"boom: {key}")

    monkeypatch.setattr(attachment_cleanup, "get_object_storage", lambda: _FakeStorage())
    monkeypatch.setattr(
        attachment_cleanup,
        "list_due_file_deletion_jobs",
        lambda *_args, **_kwargs: [
            {"id": job_id, "file_id": file_id, "attempt_count": 0, "status": "pending"}
        ],
    )
    monkeypatch.setattr(
        attachment_cleanup,
        "get_uploaded_file_by_id",
        lambda *_args, **_kwargs: {
            "id": file_id,
            "status": "expired",
            "deleted_at": None,
            "storage_key": "attachments/file-b",
        },
    )

    job_updates: list[dict] = []
    file_updates: list[dict] = []
    monkeypatch.setattr(
        attachment_cleanup,
        "update_file_deletion_job",
        lambda _db_session, **kwargs: job_updates.append(kwargs) or True,
    )
    monkeypatch.setattr(
        attachment_cleanup,
        "update_uploaded_file_status",
        lambda _db_session, **kwargs: file_updates.append(kwargs) or True,
    )

    stats = attachment_cleanup.process_file_deletion_queue(now_utc=now_utc, limit=10, max_attempts=1)

    assert stats.delete_jobs_seen == 1
    assert stats.delete_jobs_failed == 1
    assert stats.delete_jobs_retried == 0
    assert any(item["status"] == "failed" for item in job_updates)
    assert any(item["status"] == "expired" for item in file_updates)
    assert any(item.get("error_code") == "delete_failed" for item in file_updates)
