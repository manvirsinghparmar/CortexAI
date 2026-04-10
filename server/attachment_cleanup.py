"""Attachment retention cleanup job logic.

This module coordinates TTL expiry and object deletion queue processing.
It is intentionally decoupled from HTTP routes so it can run from cron/workers.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from db import (
    enqueue_file_deletion_job,
    get_uploaded_file_by_id,
    list_due_file_deletion_jobs,
    list_expired_uploaded_files,
    update_file_deletion_job,
    update_uploaded_file_status,
)
from server import persistence as persistence_service
from server.object_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageOperationError,
    get_object_storage,
)
from utils.logger import get_logger

logger = get_logger(__name__)

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_db_uow = persistence_service.db_uow


@dataclass
class AttachmentCleanupStats:
    expired_scanned: int = 0
    expired_marked: int = 0
    delete_jobs_enqueued: int = 0
    delete_jobs_seen: int = 0
    delete_jobs_succeeded: int = 0
    delete_jobs_retried: int = 0
    delete_jobs_failed: int = 0
    delete_jobs_skipped: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _parse_positive_int_env(name: str, *, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except Exception:
        logger.warning("Invalid %s value '%s'; using default %s", name, raw, default)
        return default
    if value <= 0:
        logger.warning("Non-positive %s value '%s'; using default %s", name, raw, default)
        return default
    return value


def _attachments_enabled() -> bool:
    return _env_bool("ENABLE_ATTACHMENTS", default=False)


def _cleanup_batch_size() -> int:
    return _parse_positive_int_env("ATTACHMENTS_CLEANUP_BATCH_SIZE", default=200)


def _cleanup_max_attempts() -> int:
    return _parse_positive_int_env("ATTACHMENTS_CLEANUP_MAX_ATTEMPTS", default=8)


def _cleanup_retry_backoff_seconds() -> int:
    return _parse_positive_int_env("ATTACHMENTS_CLEANUP_RETRY_BACKOFF_SECONDS", default=60)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def queue_expired_files(
    *,
    now_utc: datetime | None = None,
    limit: int | None = None,
) -> AttachmentCleanupStats:
    """Mark TTL-expired uploaded files and enqueue deletion jobs."""
    stats = AttachmentCleanupStats()
    if not _attachments_enabled() or not API_DB_ENABLED:
        return stats

    now_value = now_utc or _utcnow()
    cap = int(limit or _cleanup_batch_size())
    enqueued_job_ids: set[UUID] = set()

    with _db_uow() as db_session:
        expired_rows = list_expired_uploaded_files(db_session, now_utc=now_value, limit=cap)
        stats.expired_scanned = len(expired_rows)

        for row in expired_rows:
            file_id = row.get("id")
            if not isinstance(file_id, UUID):
                file_id = UUID(str(file_id))

            current_status = str(row.get("status") or "").strip().lower()
            if current_status != "expired":
                updated = update_uploaded_file_status(
                    db_session,
                    file_id=file_id,
                    status="expired",
                    error_code="expired",
                    error_message="Attachment TTL has elapsed and cleanup is scheduled.",
                )
                if updated:
                    stats.expired_marked += 1

            job_id = enqueue_file_deletion_job(
                db_session,
                file_id=file_id,
                available_at=now_value,
                status="pending",
            )
            if job_id not in enqueued_job_ids:
                enqueued_job_ids.add(job_id)
                stats.delete_jobs_enqueued += 1

    return stats


def _retry_available_at(*, now_utc: datetime, attempt_count: int) -> datetime:
    base = _cleanup_retry_backoff_seconds()
    multiplier = 2 ** max(0, attempt_count - 1)
    return now_utc + timedelta(seconds=base * multiplier)


def process_file_deletion_queue(
    *,
    now_utc: datetime | None = None,
    limit: int | None = None,
    max_attempts: int | None = None,
) -> AttachmentCleanupStats:
    """Process pending/retry deletion queue jobs."""
    stats = AttachmentCleanupStats()
    if not _attachments_enabled() or not API_DB_ENABLED:
        return stats

    now_value = now_utc or _utcnow()
    cap = int(limit or _cleanup_batch_size())
    attempt_cap = int(max_attempts or _cleanup_max_attempts())

    try:
        storage = get_object_storage()
    except ObjectStorageConfigurationError:
        logger.exception("Attachment cleanup aborted because object storage is not configured")
        return stats

    with _db_uow() as db_session:
        jobs = list_due_file_deletion_jobs(db_session, limit=cap)
        stats.delete_jobs_seen = len(jobs)

        for job in jobs:
            job_id = job.get("id")
            file_id = job.get("file_id")
            if not isinstance(job_id, UUID):
                job_id = UUID(str(job_id))
            if not isinstance(file_id, UUID):
                file_id = UUID(str(file_id))

            attempt_count = int(job.get("attempt_count") or 0) + 1
            update_file_deletion_job(
                db_session,
                job_id=job_id,
                status="in_progress",
                attempt_count=attempt_count,
                locked_at=now_value,
                last_error=None,
            )

            row = get_uploaded_file_by_id(db_session, file_id=file_id, include_deleted=True)
            if not row:
                update_file_deletion_job(
                    db_session,
                    job_id=job_id,
                    status="succeeded",
                    attempt_count=attempt_count,
                    locked_at=now_value,
                    last_error=None,
                )
                stats.delete_jobs_skipped += 1
                continue

            status_value = str(row.get("status") or "").strip().lower()
            if status_value == "deleted" or row.get("deleted_at") is not None:
                update_file_deletion_job(
                    db_session,
                    job_id=job_id,
                    status="succeeded",
                    attempt_count=attempt_count,
                    locked_at=now_value,
                    last_error=None,
                )
                stats.delete_jobs_skipped += 1
                continue

            storage_key = str(row.get("storage_key") or "").strip()
            try:
                if storage_key:
                    storage.delete_object(key=storage_key)

                update_uploaded_file_status(
                    db_session,
                    file_id=file_id,
                    status="deleted",
                    error_code=None,
                    error_message=None,
                    deleted_at=now_value,
                )
                update_file_deletion_job(
                    db_session,
                    job_id=job_id,
                    status="succeeded",
                    attempt_count=attempt_count,
                    locked_at=now_value,
                    last_error=None,
                )
                stats.delete_jobs_succeeded += 1
            except ObjectStorageOperationError as exc:
                error_text = str(exc)
                if attempt_count >= attempt_cap:
                    update_file_deletion_job(
                        db_session,
                        job_id=job_id,
                        status="failed",
                        attempt_count=attempt_count,
                        locked_at=now_value,
                        last_error=error_text,
                    )
                    update_uploaded_file_status(
                        db_session,
                        file_id=file_id,
                        status="expired",
                        error_code="delete_failed",
                        error_message=error_text[:400],
                    )
                    stats.delete_jobs_failed += 1
                else:
                    update_file_deletion_job(
                        db_session,
                        job_id=job_id,
                        status="retry",
                        attempt_count=attempt_count,
                        locked_at=now_value,
                        available_at=_retry_available_at(
                            now_utc=now_value,
                            attempt_count=attempt_count,
                        ),
                        last_error=error_text,
                    )
                    stats.delete_jobs_retried += 1
            except Exception as exc:
                # Keep unknown failures visible but retry-able by default.
                error_text = f"Unexpected cleanup error: {exc!s}"
                update_file_deletion_job(
                    db_session,
                    job_id=job_id,
                    status="retry",
                    attempt_count=attempt_count,
                    locked_at=now_value,
                    available_at=_retry_available_at(
                        now_utc=now_value,
                        attempt_count=attempt_count,
                    ),
                    last_error=error_text[:400],
                )
                stats.delete_jobs_retried += 1

    return stats


def run_cleanup_cycle(
    *,
    now_utc: datetime | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Run one full cleanup cycle: queue expiry + process deletion jobs."""
    now_value = now_utc or _utcnow()
    queue_stats = queue_expired_files(now_utc=now_value, limit=limit)
    process_stats = process_file_deletion_queue(now_utc=now_value, limit=limit)

    merged = AttachmentCleanupStats(
        expired_scanned=queue_stats.expired_scanned,
        expired_marked=queue_stats.expired_marked,
        delete_jobs_enqueued=queue_stats.delete_jobs_enqueued,
        delete_jobs_seen=process_stats.delete_jobs_seen,
        delete_jobs_succeeded=process_stats.delete_jobs_succeeded,
        delete_jobs_retried=process_stats.delete_jobs_retried,
        delete_jobs_failed=process_stats.delete_jobs_failed,
        delete_jobs_skipped=process_stats.delete_jobs_skipped,
    )
    return merged.to_dict()
