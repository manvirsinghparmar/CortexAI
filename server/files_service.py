"""Attachment file service logic for upload/status operations."""

from __future__ import annotations

import hashlib
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from fastapi import HTTPException, status

from db import (
    create_uploaded_file,
    find_active_uploaded_file_by_hash,
    get_uploaded_file_by_id,
    get_uploaded_file_for_user,
    update_api_key_last_used,
    update_uploaded_file_status,
)
from server import attachments as attachments_service
from server.dependencies import AuthResult
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
_resolve_api_key_for_request = persistence_service.resolve_api_key_for_request
_resolve_identity = persistence_service.resolve_identity

DEFAULT_ALLOWED_MIME_TYPES = (
    "image/jpeg",
    "image/jpg",
    "image/png",
    "image/webp",
    "image/gif",
    "application/pdf",
    "text/plain",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

SYNC_INGEST_REQUIRED_MIME_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}

CLIENT_SAFE_UPLOAD_ERROR_MESSAGES_BY_CODE = {
    "invalid_mime_type": "Upload failed. This file type is not supported.",
    "unsupported_file_type": "Upload failed. This file type is not supported.",
    "empty_file": "Upload failed. The selected file is empty.",
    "file_too_large": "Upload failed. This file is too large.",
    "storage_not_configured": "This file could not be uploaded right now. Please try again in a moment.",
    "storage_upload_failed": "This file could not be uploaded right now. Please try again in a moment.",
    "ingestion_failed": "This file could not be uploaded right now. Please try again in a moment.",
    "ingestion_read_failed": "This file could not be uploaded right now. Please try again in a moment.",
}

SENSITIVE_UPLOAD_ERROR_TOKENS = (
    "bucket",
    "object key",
    "storage key",
    "attachments/users/",
    "s3://",
    "request_id",
    "request id",
    "traceback",
    "stack trace",
)


def _env_bool(name: str, *, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def attachments_enabled() -> bool:
    return _env_bool("ENABLE_ATTACHMENTS", default=False)


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


def _allowed_mime_types() -> set[str]:
    raw = str(os.getenv("ATTACHMENTS_ALLOWED_MIME_TYPES", "") or "").strip()
    if not raw:
        return set(DEFAULT_ALLOWED_MIME_TYPES)
    parsed = {
        part.strip().lower()
        for part in raw.split(",")
        if part and part.strip()
    }
    return parsed or set(DEFAULT_ALLOWED_MIME_TYPES)


def _normalize_filename(filename: str | None) -> str:
    name = Path(str(filename or "").strip()).name or "file"
    # Keep keys URL-safe and deterministic enough for debugging.
    safe = re.sub(r"[^A-Za-z0-9._-]", "_", name)
    return safe[:180] or "file"


def _hash_for_logs(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _build_storage_key(
    *,
    key_prefix: str,
    user_id: UUID,
    sha256: str,
    filename: str,
) -> str:
    date_folder = datetime.now(timezone.utc).strftime("%Y/%m/%d")
    key_parts = [
        key_prefix.strip("/"),
        "users",
        str(user_id),
        date_folder,
        f"{sha256[:16]}-{uuid4().hex}-{filename}",
    ]
    # Drop empty fragments so blank prefix still works.
    return "/".join([part for part in key_parts if part])


def _iso_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return str(value)


def _serialize_uploaded_file_row(
    row: dict[str, Any],
    *,
    deduplicated: bool = False,
) -> dict[str, Any]:
    status_value = str(row.get("status") or "uploaded")
    error_code = row.get("error_code")
    safe_error_message = _get_client_safe_upload_error_message(
        error_code=error_code,
        raw_message=row.get("error_message"),
        status_value=status_value,
    )
    return {
        "file_id": str(row.get("id")),
        "original_filename": str(row.get("original_filename") or "file"),
        "mime_type": str(row.get("mime_type") or ""),
        "size_bytes": int(row.get("size_bytes") or 0),
        "status": status_value,
        "error_code": error_code,
        "error_message": safe_error_message,
        "ingestion_meta": _sanitize_ingestion_meta_for_client(row.get("ingestion_meta")),
        "created_at": _iso_or_none(row.get("created_at")) or "",
        "updated_at": _iso_or_none(row.get("updated_at")),
        "expires_at": _iso_or_none(row.get("expires_at")),
        "deduplicated": deduplicated,
    }


def _contains_sensitive_upload_error(raw_message: str | None) -> bool:
    text = str(raw_message or "").strip().lower()
    if not text:
        return False
    return any(token in text for token in SENSITIVE_UPLOAD_ERROR_TOKENS)


def _get_client_safe_upload_error_message(
    *,
    error_code: str | None,
    raw_message: str | None,
    status_value: str | None = None,
) -> str | None:
    code = str(error_code or "").strip().lower()
    if code in CLIENT_SAFE_UPLOAD_ERROR_MESSAGES_BY_CODE:
        return CLIENT_SAFE_UPLOAD_ERROR_MESSAGES_BY_CODE[code]

    raw = str(raw_message or "").strip()
    if not raw:
        if str(status_value or "").strip().lower() in {"failed", "error"}:
            return "Upload failed. Please try again."
        return None

    lowered = raw.lower()
    if "payload too large" in lowered or "request entity too large" in lowered or "too large" in lowered:
        return "Upload failed. This file is too large."
    if "unsupported" in lowered or "mime type" in lowered or "file type" in lowered or "media type" in lowered:
        return "Upload failed. This file type is not supported."
    if "timeout" in lowered or "timed out" in lowered:
        return "Upload failed because the request timed out. Please try again."
    if _contains_sensitive_upload_error(raw):
        return "Upload failed. Please try again."

    return "Upload failed. Please try again."


def _sanitize_ingestion_meta_for_client(ingestion_meta: Any) -> dict[str, Any]:
    if not isinstance(ingestion_meta, dict):
        return {}

    sanitized: dict[str, Any] = {}
    blocked_keys = {
        "last_error",
        "error",
        "error_message",
        "storage_key",
        "storage_bucket",
        "bucket",
        "object_key",
        "object_path",
        "request_id",
        "traceback",
        "stack",
    }
    for key, value in ingestion_meta.items():
        key_text = str(key or "").strip().lower()
        if key_text in blocked_keys:
            continue
        if isinstance(value, dict):
            sanitized[key] = _sanitize_ingestion_meta_for_client(value)
        else:
            sanitized[key] = value
    return sanitized


def _attachment_ttl_hours() -> int:
    return _parse_positive_int_env("ATTACHMENTS_FILE_TTL_HOURS", default=24 * 7)


def _max_upload_bytes() -> int:
    return _parse_positive_int_env("ATTACHMENTS_MAX_FILE_BYTES", default=20 * 1024 * 1024)


def _sync_ingest_timeout_seconds() -> int:
    return _parse_positive_int_env("ATTACHMENTS_SYNC_INGEST_TIMEOUT_SECONDS", default=10)


def _sync_ingest_inline_max_bytes() -> int:
    return _parse_positive_int_env("ATTACHMENTS_SYNC_INGEST_MAX_BYTES", default=2 * 1024 * 1024)


def _requires_sync_ingestion(mime_type: str) -> bool:
    return str(mime_type or "").strip().lower() in SYNC_INGEST_REQUIRED_MIME_TYPES


def _build_ingestion_meta_base(
    *,
    normalized_mime: str,
    size_bytes: int,
) -> dict[str, Any]:
    required = _requires_sync_ingestion(normalized_mime)
    return {
        "ingestion_required": required,
        "ingestion_state": "processing" if required else "none",
        "ingestion_method": "sync_extract" if required else "none",
        "sync_timeout_seconds": _sync_ingest_timeout_seconds(),
        "sync_inline_max_bytes": _sync_ingest_inline_max_bytes(),
        "mime_type": normalized_mime,
        "size_bytes": int(size_bytes),
    }


def _merge_ingestion_meta(
    existing: dict[str, Any] | None,
    updates: dict[str, Any] | None,
) -> dict[str, Any]:
    merged = dict(existing) if isinstance(existing, dict) else {}
    if isinstance(updates, dict):
        merged.update(updates)
    return merged


def _run_sync_ingestion(
    *,
    payload: bytes,
    normalized_mime: str,
    filename: str,
    base_meta: dict[str, Any],
    request_id: str | None = None,
    file_id: UUID | None = None,
) -> tuple[str, dict[str, Any], str | None, str | None]:
    started_at = datetime.now(timezone.utc)
    started = time.perf_counter()
    logger.info(
        "Attachment ingestion started",
        extra={
            "extra_fields": {
                "event": "upload.ingestion.start",
                "request_id": request_id,
                "file_id": str(file_id) if file_id else None,
                "mime_type": normalized_mime,
                "filename_hash": _hash_for_logs(filename),
                "size_bytes": len(payload or b""),
            }
        },
    )
    try:
        artifact = attachments_service.extract_text_attachment_artifact(
            payload=payload,
            mime_type=normalized_mime,
            filename=filename,
            transform_mode="auto",
            usage_role="primary",
        )
        finished_at = datetime.now(timezone.utc)
        elapsed_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        artifact_meta = artifact.get("artifact_meta")
        merged_meta = _merge_ingestion_meta(
            base_meta,
            {
                "ingestion_state": "ready",
                "ingested_at": finished_at.isoformat().replace("+00:00", "Z"),
                "ingestion_latency_ms": elapsed_ms,
                "effective_transform_mode": str(
                    artifact.get("effective_transform_mode") or "text_only"
                ),
                "artifact_meta": dict(artifact_meta) if isinstance(artifact_meta, dict) else {},
            },
        )
        logger.info(
            "Attachment ingestion succeeded",
            extra={
                "extra_fields": {
                    "event": "upload.ingestion.success",
                    "request_id": request_id,
                    "file_id": str(file_id) if file_id else None,
                    "mime_type": normalized_mime,
                    "filename_hash": _hash_for_logs(filename),
                    "latency_ms": elapsed_ms,
                    "wall_latency_ms": int((time.perf_counter() - started) * 1000),
                    "effective_transform_mode": str(
                        artifact.get("effective_transform_mode") or "text_only"
                    ),
                    "chunk_count": int((artifact_meta or {}).get("chunk_count") or 0)
                    if isinstance(artifact_meta, dict)
                    else 0,
                }
            },
        )
        return "ready", merged_meta, None, None
    except Exception as exc:
        logger.exception(
            "Attachment ingestion failed",
            extra={
                "extra_fields": {
                    "event": "upload.ingestion.failure",
                    "request_id": request_id,
                    "file_id": str(file_id) if file_id else None,
                    "mime_type": normalized_mime,
                    "filename_hash": _hash_for_logs(filename),
                    "error_type": type(exc).__name__,
                    "wall_latency_ms": int((time.perf_counter() - started) * 1000),
                }
            },
        )
        finished_at = datetime.now(timezone.utc)
        elapsed_ms = max(0, int((finished_at - started_at).total_seconds() * 1000))
        merged_meta = _merge_ingestion_meta(
            base_meta,
            {
                "ingestion_state": "failed",
                "ingested_at": finished_at.isoformat().replace("+00:00", "Z"),
                "ingestion_latency_ms": elapsed_ms,
                "artifact_meta": {},
            },
        )
        return "failed", merged_meta, "ingestion_failed", str(exc)


def _maybe_finalize_processing_file(
    *,
    db_session,
    row: dict[str, Any],
    request_id: str | None = None,
) -> dict[str, Any]:
    status_value = str(row.get("status") or "").strip().lower()
    if status_value not in {"uploaded", "processing"}:
        return row

    ingestion_meta = row.get("ingestion_meta")
    if not isinstance(ingestion_meta, dict) or not bool(ingestion_meta.get("ingestion_required")):
        return row

    normalized_mime = str(row.get("mime_type") or "").strip().lower()
    if not _requires_sync_ingestion(normalized_mime):
        return row

    storage_key = str(row.get("storage_key") or "").strip()
    if not storage_key:
        return row
    file_id = row.get("id")
    logger.info(
        "Attachment deferred ingestion fetch started",
        extra={
            "extra_fields": {
                "event": "upload.ingestion.deferred.start",
                "request_id": request_id,
                "file_id": str(file_id) if file_id else None,
                "mime_type": normalized_mime,
                "storage_key_hash": _hash_for_logs(storage_key),
            }
        },
    )

    try:
        storage = get_object_storage()
        payload = storage.get_bytes(key=storage_key)
    except Exception as exc:
        logger.exception(
            "Attachment deferred ingestion read failed",
            extra={
                "extra_fields": {
                    "event": "upload.ingestion.deferred.read_failure",
                    "request_id": request_id,
                    "file_id": str(file_id) if file_id else None,
                    "mime_type": normalized_mime,
                    "storage_key_hash": _hash_for_logs(storage_key),
                    "error_type": type(exc).__name__,
                }
            },
        )
        error_text = str(exc)
        update_uploaded_file_status(
            db_session,
            file_id=row["id"],
            status="failed",
            error_code="ingestion_read_failed",
            error_message=error_text[:400],
            ingestion_meta=_merge_ingestion_meta(
                ingestion_meta,
                {"ingestion_state": "failed", "last_error": error_text[:400]},
            ),
        )
        refreshed = get_uploaded_file_by_id(
            db_session,
            file_id=row["id"],
            include_deleted=False,
        )
        return refreshed or row

    sync_status, sync_meta, sync_error_code, sync_error_message = _run_sync_ingestion(
        payload=payload,
        normalized_mime=normalized_mime,
        filename=str(row.get("original_filename") or "file"),
        base_meta=ingestion_meta,
        request_id=request_id,
        file_id=(file_id if isinstance(file_id, UUID) else None),
    )
    update_uploaded_file_status(
        db_session,
        file_id=row["id"],
        status=sync_status,
        error_code=sync_error_code,
        error_message=(sync_error_message[:400] if sync_error_message else None),
        ingestion_meta=sync_meta,
    )
    refreshed = get_uploaded_file_by_id(
        db_session,
        file_id=row["id"],
        include_deleted=False,
    )
    logger.info(
        "Attachment deferred ingestion finalized",
        extra={
            "extra_fields": {
                "event": "upload.ingestion.deferred.finalized",
                "request_id": request_id,
                "file_id": str(file_id) if file_id else None,
                "status": sync_status,
                "error_code": sync_error_code,
            }
        },
    )
    return refreshed or row


def _assert_feature_enabled(*, request_id: str | None = None) -> None:
    if attachments_enabled():
        return
    logger.warning(
        "Attachment request rejected because feature is disabled",
        extra={
            "extra_fields": {
                "event": "upload.feature.disabled",
                "request_id": request_id,
                "env_enable_attachments": str(os.getenv("ENABLE_ATTACHMENTS", "")),
            }
        },
    )
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "attachments_disabled",
            "message": "Attachments are disabled. Enable ENABLE_ATTACHMENTS=true.",
        },
    )


def _assert_db_enabled(*, request_id: str | None = None) -> None:
    if API_DB_ENABLED:
        return
    logger.warning(
        "Attachment request rejected because DB mode is disabled",
        extra={
            "extra_fields": {
                "event": "upload.db.disabled",
                "request_id": request_id,
                "api_db_enabled": bool(API_DB_ENABLED),
                "database_url_configured": bool(str(os.getenv("DATABASE_URL") or "").strip()),
            }
        },
    )
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail={
            "code": "attachments_require_db",
            "message": "Attachments require DATABASE_URL (DB mode).",
        },
    )


def upload_user_file(
    *,
    api_key: str | None = None,
    auth: AuthResult | None = None,
    request_id: str,
    filename: str,
    mime_type: str,
    payload: bytes,
) -> dict[str, Any]:
    """Validate, store, and persist attachment metadata for one authenticated user file."""
    _assert_feature_enabled(request_id=request_id)
    _assert_db_enabled(request_id=request_id)

    logger.info(
        "Attachment upload received",
        extra={
            "extra_fields": {
                "event": "upload.received",
                "request_id": request_id,
                "filename_hash": _hash_for_logs(filename),
                "mime_type": str(mime_type or "").strip().lower(),
                "size_bytes": len(payload or b""),
            }
        },
    )

    normalized_mime = str(mime_type or "").strip().lower()
    if not normalized_mime:
        logger.warning(
            "Attachment upload rejected: missing MIME type",
            extra={
                "extra_fields": {
                    "event": "upload.validation.invalid_mime",
                    "request_id": request_id,
                    "filename_hash": _hash_for_logs(filename),
                    "size_bytes": len(payload or b""),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_mime_type", "message": "File MIME type is required."},
        )

    allowed = _allowed_mime_types()
    if normalized_mime not in allowed:
        logger.warning(
            "Attachment upload rejected: unsupported MIME type",
            extra={
                "extra_fields": {
                    "event": "upload.validation.unsupported_mime",
                    "request_id": request_id,
                    "mime_type": normalized_mime,
                    "filename_hash": _hash_for_logs(filename),
                    "size_bytes": len(payload or b""),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "unsupported_file_type",
                "message": f"Unsupported MIME type '{normalized_mime}'.",
                "allowed_mime_types": sorted(allowed),
            },
        )

    max_file_bytes = _max_upload_bytes()
    if not payload:
        logger.warning(
            "Attachment upload rejected: empty payload",
            extra={
                "extra_fields": {
                    "event": "upload.validation.empty_payload",
                    "request_id": request_id,
                    "mime_type": normalized_mime,
                    "filename_hash": _hash_for_logs(filename),
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Uploaded file is empty."},
        )
    if len(payload) > max_file_bytes:
        logger.warning(
            "Attachment upload rejected: file too large",
            extra={
                "extra_fields": {
                    "event": "upload.validation.file_too_large",
                    "request_id": request_id,
                    "mime_type": normalized_mime,
                    "filename_hash": _hash_for_logs(filename),
                    "size_bytes": len(payload),
                    "max_file_bytes": max_file_bytes,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "file_too_large",
                "message": f"File exceeds ATTACHMENTS_MAX_FILE_BYTES ({max_file_bytes}).",
                "max_file_bytes": max_file_bytes,
            },
        )

    normalized_filename = _normalize_filename(filename)
    sha256 = hashlib.sha256(payload).hexdigest()

    now_utc = datetime.now(timezone.utc)
    expires_at = now_utc + timedelta(hours=_attachment_ttl_hours())

    with _db_uow() as db_session:
        raw_api_key = str((auth.api_key if auth else api_key) or "").strip()
        if auth is not None:
            resolution = _resolve_identity(
                auth=auth,
                request_id=request_id,
                db_session=db_session,
            )
        else:
            resolution = _resolve_api_key_for_request(
                api_key=raw_api_key,
                request_id=request_id,
                db_session=db_session,
            )
        logger.info(
            "Attachment upload auth resolved",
            extra={
                "extra_fields": {
                    "event": "upload.auth.resolved",
                    "request_id": request_id,
                    "user_id": str(getattr(resolution, "user_id", "")),
                    "api_key_id": (
                        str(getattr(resolution, "api_key_id", "") or "")
                        if getattr(resolution, "api_key_id", None)
                        else None
                    ),
                    "decision_path": str(getattr(resolution, "decision_path", "")),
                }
            },
        )

        existing = find_active_uploaded_file_by_hash(
            db_session,
            user_id=resolution.user_id,
            sha256=sha256,
            size_bytes=len(payload),
        )
        if existing and str(existing.get("status") or "").strip().lower() in {
            "uploaded",
            "processing",
            "ready",
        }:
            if resolution.api_key_id is not None and raw_api_key:
                update_api_key_last_used(db_session, raw_api_key)
            logger.info(
                "Attachment upload deduplicated",
                extra={
                    "extra_fields": {
                        "event": "upload.deduplicated",
                        "request_id": request_id,
                        "file_id": str(existing.get("id") or ""),
                        "status": str(existing.get("status") or ""),
                        "mime_type": normalized_mime,
                        "size_bytes": len(payload),
                        "sha256_prefix": sha256[:16],
                    }
                },
            )
            return _serialize_uploaded_file_row(existing, deduplicated=True)

        try:
            storage = get_object_storage()
        except ObjectStorageConfigurationError as exc:
            logger.exception(
                "Attachment object storage is not configured",
                extra={
                    "extra_fields": {
                        "event": "upload.storage.not_configured",
                        "request_id": request_id,
                        "mime_type": normalized_mime,
                        "size_bytes": len(payload),
                        "filename_hash": _hash_for_logs(normalized_filename),
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "storage_not_configured",
                    "message": "This file could not be uploaded right now. Please try again in a moment.",
                },
            ) from exc

        storage_key = _build_storage_key(
            key_prefix=storage.key_prefix,
            user_id=resolution.user_id,
            sha256=sha256,
            filename=normalized_filename,
        )
        storage_key_hash = _hash_for_logs(storage_key)
        logger.info(
            "Attachment storage upload dispatch",
            extra={
                "extra_fields": {
                    "event": "upload.storage.put.start",
                    "request_id": request_id,
                    "mime_type": normalized_mime,
                    "size_bytes": len(payload),
                    "filename_hash": _hash_for_logs(normalized_filename),
                    "storage_key_hash": storage_key_hash,
                }
            },
        )

        try:
            storage.put_bytes(
                key=storage_key,
                payload=payload,
                content_type=normalized_mime,
                metadata={
                    "sha256": sha256,
                    "user_id": str(resolution.user_id),
                    "uploaded_at": now_utc.isoformat(),
                },
            )
            logger.info(
                "Attachment storage upload completed",
                extra={
                    "extra_fields": {
                        "event": "upload.storage.put.success",
                        "request_id": request_id,
                        "mime_type": normalized_mime,
                        "size_bytes": len(payload),
                        "storage_key_hash": storage_key_hash,
                    }
                },
            )
        except ObjectStorageOperationError as exc:
            logger.exception(
                "Attachment object upload failed",
                extra={
                    "extra_fields": {
                        "event": "upload.storage.put.failure",
                        "request_id": request_id,
                        "mime_type": normalized_mime,
                        "size_bytes": len(payload),
                        "filename_hash": _hash_for_logs(normalized_filename),
                        "storage_key_hash": storage_key_hash,
                        "error_type": type(exc).__name__,
                    }
                },
            )
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "storage_upload_failed",
                    "message": "This file could not be uploaded right now. Please try again in a moment.",
                },
            ) from exc

        try:
            ingestion_meta = _build_ingestion_meta_base(
                normalized_mime=normalized_mime,
                size_bytes=len(payload),
            )
            ingestion_required = bool(ingestion_meta.get("ingestion_required"))
            initial_status = "processing" if ingestion_required else "ready"
            uploaded_file_id = create_uploaded_file(
                db_session,
                user_id=resolution.user_id,
                api_key_id=resolution.api_key_id,
                original_filename=normalized_filename,
                mime_type=normalized_mime,
                size_bytes=len(payload),
                sha256=sha256,
                storage_bucket=storage.bucket,
                storage_key=storage_key,
                status=initial_status,
                ingestion_meta=ingestion_meta,
                expires_at=expires_at,
            )
            logger.info(
                "Attachment metadata persisted",
                extra={
                    "extra_fields": {
                        "event": "upload.metadata.persisted",
                        "request_id": request_id,
                        "file_id": str(uploaded_file_id),
                        "status": initial_status,
                        "ingestion_required": ingestion_required,
                        "mime_type": normalized_mime,
                        "size_bytes": len(payload),
                        "storage_key_hash": storage_key_hash,
                        "sha256_prefix": sha256[:16],
                    }
                },
            )

            if ingestion_required:
                if len(payload) <= _sync_ingest_inline_max_bytes():
                    sync_status, sync_meta, sync_error_code, sync_error_message = _run_sync_ingestion(
                        payload=payload,
                        normalized_mime=normalized_mime,
                        filename=normalized_filename,
                        base_meta=ingestion_meta,
                        request_id=request_id,
                        file_id=uploaded_file_id,
                    )
                    update_uploaded_file_status(
                        db_session,
                        file_id=uploaded_file_id,
                        status=sync_status,
                        error_code=sync_error_code,
                        error_message=(sync_error_message[:400] if sync_error_message else None),
                        ingestion_meta=sync_meta,
                    )
                else:
                    logger.info(
                        "Attachment ingestion deferred",
                        extra={
                            "extra_fields": {
                                "event": "upload.ingestion.deferred",
                                "request_id": request_id,
                                "file_id": str(uploaded_file_id),
                                "mime_type": normalized_mime,
                                "size_bytes": len(payload),
                                "sync_inline_max_bytes": _sync_ingest_inline_max_bytes(),
                            }
                        },
                    )
                    deferred_meta = _merge_ingestion_meta(
                        ingestion_meta,
                        {
                            "ingestion_state": "processing",
                            "deferred_reason": "size_exceeds_sync_inline_limit",
                            "deferred_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                        },
                    )
                    update_uploaded_file_status(
                        db_session,
                        file_id=uploaded_file_id,
                        status="processing",
                        error_code=None,
                        error_message=None,
                        ingestion_meta=deferred_meta,
                    )
        except Exception:
            # Best-effort rollback of object storage if metadata write fails.
            try:
                storage.delete_object(key=storage_key)
            except Exception:
                logger.exception(
                    "Failed to rollback object after metadata write failure",
                    extra={
                        "extra_fields": {
                            "event": "upload.storage.rollback.failure",
                            "request_id": request_id,
                            "storage_key_hash": storage_key_hash,
                        }
                    },
                )
            raise

        if resolution.api_key_id is not None and raw_api_key:
            update_api_key_last_used(db_session, raw_api_key)

        row = get_uploaded_file_for_user(
            db_session,
            user_id=resolution.user_id,
            file_id=uploaded_file_id,
            include_deleted=False,
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "uploaded_file_not_found",
                    "message": "File metadata not found after upload.",
                },
            )
        logger.info(
            "Attachment upload completed",
            extra={
                "extra_fields": {
                    "event": "upload.completed",
                    "request_id": request_id,
                    "file_id": str(uploaded_file_id),
                    "status": str(row.get("status") or ""),
                    "mime_type": normalized_mime,
                    "size_bytes": len(payload),
                    "storage_key_hash": storage_key_hash,
                }
            },
        )
        return _serialize_uploaded_file_row(row, deduplicated=False)


def get_user_file(
    *,
    api_key: str | None = None,
    auth: AuthResult | None = None,
    request_id: str,
    file_id: UUID,
) -> dict[str, Any]:
    """Fetch file metadata scoped to the authenticated owner."""
    _assert_feature_enabled(request_id=request_id)
    _assert_db_enabled(request_id=request_id)
    logger.info(
        "Attachment status lookup requested",
        extra={
            "extra_fields": {
                "event": "upload.status.lookup.start",
                "request_id": request_id,
                "file_id": str(file_id),
            }
        },
    )

    with _db_uow() as db_session:
        if auth is not None:
            resolution = _resolve_identity(
                auth=auth,
                request_id=request_id,
                db_session=db_session,
            )
        else:
            resolution = _resolve_api_key_for_request(
                api_key=str(api_key or "").strip(),
                request_id=request_id,
                db_session=db_session,
            )
        row = get_uploaded_file_for_user(
            db_session,
            user_id=resolution.user_id,
            file_id=file_id,
            include_deleted=False,
        )
        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "file_not_found", "message": "Attachment file not found."},
            )
        row = _maybe_finalize_processing_file(
            db_session=db_session,
            row=row,
            request_id=request_id,
        )
        logger.info(
            "Attachment status lookup completed",
            extra={
                "extra_fields": {
                    "event": "upload.status.lookup.success",
                    "request_id": request_id,
                    "file_id": str(file_id),
                    "status": str(row.get("status") or ""),
                    "mime_type": str(row.get("mime_type") or ""),
                    "size_bytes": int(row.get("size_bytes") or 0),
                }
            },
        )
        return _serialize_uploaded_file_row(row, deduplicated=False)
