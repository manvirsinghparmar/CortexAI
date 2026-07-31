"""Attachment resolution and model-compatibility preflight helpers."""

from __future__ import annotations

import csv
import os
from dataclasses import dataclass, field
import base64
import io
import json
import re
import zipfile
from xml.etree import ElementTree
from typing import Any, Iterable
from uuid import UUID

from fastapi import HTTPException, status

from db import get_uploaded_file_for_user
from orchestrator.model_registry import ModelRegistry
from server.object_storage import (
    ObjectStorageConfigurationError,
    ObjectStorageOperationError,
    get_object_storage,
)
from server import persistence as persistence_service
from utils.logger import get_logger

logger = get_logger(__name__)

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_db_uow = persistence_service.db_uow

READY_FILE_STATUSES = {"ready"}
TEXT_EXTRACTABLE_MIME_TYPES = {
    "text/plain",
    "text/csv",
    "application/json",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
TABLE_LIKE_MIME_TYPES = {
    "text/csv",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}
VISION_MIME_TYPES = {"application/pdf"}
MAX_EXTRACT_ROWS = 80
MAX_EXTRACT_COLUMNS = 40


def _env_bool(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _attachments_enabled() -> bool:
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


def _max_attachments_per_request() -> int:
    return _parse_positive_int_env("ATTACHMENTS_MAX_FILES_PER_REQUEST", default=5)


def _max_text_extract_chars() -> int:
    return _parse_positive_int_env("ATTACHMENTS_TEXT_EXTRACT_MAX_CHARS", default=12000)


def _text_chunk_chars() -> int:
    return _parse_positive_int_env("ATTACHMENTS_TEXT_CHUNK_CHARS", default=3000)


def _text_max_chunks_for_primary() -> int:
    return _parse_positive_int_env("ATTACHMENTS_TEXT_MAX_CHUNKS", default=4)


def _text_max_chunks_for_reference() -> int:
    return _parse_positive_int_env("ATTACHMENTS_REFERENCE_TEXT_MAX_CHUNKS", default=2)


def _local_name(tag: str) -> str:
    raw = str(tag or "")
    if "}" in raw:
        return raw.rsplit("}", 1)[-1]
    return raw


def _truncate_text(value: str, *, filename: str, max_chars: int) -> str:
    text = str(value or "").strip()
    if len(text) <= max_chars:
        return text
    clipped = text[: max(0, max_chars - 120)].rstrip()
    return (
        f"{clipped}\n\n[truncated] Attachment '{filename}' exceeded {max_chars} characters "
        "after extraction."
    )


def _effective_transform_mode(*, mime_type: str, requested_mode: str) -> str:
    requested = str(requested_mode or "auto").strip().lower() or "auto"
    mime = str(mime_type or "").strip().lower()
    if requested != "auto":
        return requested
    if mime in TABLE_LIKE_MIME_TYPES:
        return "table_summary"
    if mime in TEXT_EXTRACTABLE_MIME_TYPES:
        return "text_only"
    return "vision_pages"


def _materializes_as_text(*, mime_type: str, requested_mode: str) -> bool:
    effective_mode = _effective_transform_mode(
        mime_type=mime_type,
        requested_mode=requested_mode,
    )
    return (
        effective_mode in {"text_only", "table_summary"}
        and mime_type in TEXT_EXTRACTABLE_MIME_TYPES
    )


def _extract_txt(payload: bytes) -> str:
    return payload.decode("utf-8", errors="replace")


def _extract_json(payload: bytes) -> str:
    decoded = payload.decode("utf-8", errors="replace")
    try:
        obj = json.loads(decoded)
    except Exception:
        return decoded
    return json.dumps(obj, indent=2, ensure_ascii=False)


def _extract_csv(payload: bytes) -> str:
    decoded = payload.decode("utf-8", errors="replace")
    reader = csv.reader(io.StringIO(decoded))
    lines: list[str] = []
    for row_idx, row in enumerate(reader):
        if row_idx >= MAX_EXTRACT_ROWS:
            lines.append("[truncated rows]")
            break
        normalized = [
            str(cell or "").strip().replace("\n", " ") for cell in row[:MAX_EXTRACT_COLUMNS]
        ]
        if len(row) > MAX_EXTRACT_COLUMNS:
            normalized.append("...")
        lines.append(" | ".join(normalized))
    return "\n".join(lines)


def _extract_docx(payload: bytes) -> str:
    paragraphs: list[str] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        with archive.open("word/document.xml") as handle:
            root = ElementTree.parse(handle).getroot()
            for element in root.iter():
                if _local_name(element.tag) == "t":
                    text = str(element.text or "").strip()
                    if text:
                        paragraphs.append(text)
    return "\n".join(paragraphs)


def _extract_pptx(payload: bytes) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        slide_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for idx, slide_name in enumerate(slide_names[:MAX_EXTRACT_ROWS], start=1):
            with archive.open(slide_name) as handle:
                root = ElementTree.parse(handle).getroot()
                chunks: list[str] = []
                for element in root.iter():
                    if _local_name(element.tag) == "t":
                        text = str(element.text or "").strip()
                        if text:
                            chunks.append(text)
                if chunks:
                    lines.append(f"[Slide {idx}]")
                    lines.extend(chunks)
    return "\n".join(lines)


def _xlsx_cell_value(cell: ElementTree.Element, shared_strings: list[str]) -> str:
    cell_type = str(cell.attrib.get("t") or "").strip().lower()
    value = ""
    for child in cell:
        if _local_name(child.tag) == "v":
            value = str(child.text or "")
            break
        if _local_name(child.tag) == "is":
            text_parts: list[str] = []
            for inline_child in child.iter():
                if _local_name(inline_child.tag) == "t":
                    text = str(inline_child.text or "")
                    if text:
                        text_parts.append(text)
            value = "".join(text_parts)
            break

    if cell_type == "s":
        try:
            shared_idx = int(value)
            return shared_strings[shared_idx]
        except Exception:
            return value
    return value


def _extract_xlsx(payload: bytes) -> str:
    lines: list[str] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as archive:
        shared_strings: list[str] = []
        if "xl/sharedStrings.xml" in archive.namelist():
            with archive.open("xl/sharedStrings.xml") as handle:
                root = ElementTree.parse(handle).getroot()
                for element in root.iter():
                    if _local_name(element.tag) == "t":
                        shared_strings.append(str(element.text or ""))

        worksheet_names = sorted(
            name
            for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        )
        for sheet_idx, sheet_name in enumerate(worksheet_names[:3], start=1):
            with archive.open(sheet_name) as handle:
                root = ElementTree.parse(handle).getroot()
                rows = []
                for worksheet_row in root.iter():
                    if _local_name(worksheet_row.tag) != "row":
                        continue
                    current = []
                    for cell in worksheet_row:
                        if _local_name(cell.tag) != "c":
                            continue
                        current.append(_xlsx_cell_value(cell, shared_strings))
                    if current:
                        rows.append(current)
                    if len(rows) >= MAX_EXTRACT_ROWS:
                        break
                if rows:
                    lines.append(f"[Sheet {sheet_idx}]")
                    for worksheet_values in rows:
                        normalized = [
                            str(cell or "").strip().replace("\n", " ")
                            for cell in worksheet_values[:MAX_EXTRACT_COLUMNS]
                        ]
                        if len(worksheet_values) > MAX_EXTRACT_COLUMNS:
                            normalized.append("...")
                        lines.append(" | ".join(normalized))
    return "\n".join(lines)


def _extract_text_payload(*, payload: bytes, mime_type: str, filename: str) -> str:
    mime = str(mime_type or "").strip().lower()
    if mime == "text/plain":
        text = _extract_txt(payload)
    elif mime == "application/json":
        text = _extract_json(payload)
    elif mime == "text/csv":
        text = _extract_csv(payload)
    elif mime == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        text = _extract_docx(payload)
    elif mime == "application/vnd.openxmlformats-officedocument.presentationml.presentation":
        text = _extract_pptx(payload)
    elif mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet":
        text = _extract_xlsx(payload)
    else:
        raise ValueError(f"Unsupported text extraction MIME type: {mime}")

    return _truncate_text(
        text,
        filename=filename,
        max_chars=_max_text_extract_chars(),
    )


def _split_text_into_chunks(
    text: str, *, chunk_chars: int, max_chunks: int
) -> tuple[list[str], bool]:
    raw = str(text or "").strip()
    if not raw:
        return [], False

    chunks: list[str] = []
    cursor = 0
    truncated = False
    max_chars = max(200, int(chunk_chars))
    max_chunk_count = max(1, int(max_chunks))

    while cursor < len(raw):
        if len(chunks) >= max_chunk_count:
            truncated = True
            break

        end = min(len(raw), cursor + max_chars)
        if end < len(raw):
            newline_break = raw.rfind("\n", cursor + int(max_chars * 0.6), end)
            if newline_break > cursor:
                end = newline_break + 1

        chunk = raw[cursor:end].strip()
        if chunk:
            chunks.append(chunk)
        cursor = end

    return chunks, truncated


def _text_chunk_budget_for_usage_role(usage_role: str) -> int:
    role = str(usage_role or "primary").strip().lower()
    if role == "reference":
        return _text_max_chunks_for_reference()
    return _text_max_chunks_for_primary()


def _format_text_chunks_for_model(
    text: str,
    *,
    usage_role: str,
    query_text: str = "",
) -> tuple[str, dict[str, Any]]:
    raw = str(text or "").strip()
    chunk_chars = _text_chunk_chars()
    max_chunks = _text_chunk_budget_for_usage_role(usage_role)
    all_chunks, _ = _split_text_into_chunks(
        raw,
        chunk_chars=chunk_chars,
        max_chunks=max(1, (len(raw) // max(1, chunk_chars)) + 2),
    )
    query_terms = {
        term
        for term in re.findall(r"[a-z0-9]{3,}", str(query_text or "").lower())
        if term not in {"about", "from", "have", "please", "that", "this", "what", "with"}
    }
    selected_indexes = list(range(min(len(all_chunks), max_chunks)))
    selection_strategy = "leading_chunks"
    if query_terms and len(all_chunks) > max_chunks:
        scored = [
            (
                sum(chunk.lower().count(term) for term in query_terms),
                index,
            )
            for index, chunk in enumerate(all_chunks)
        ]
        relevant = [
            index
            for score, index in sorted(scored, key=lambda item: (-item[0], item[1]))
            if score > 0
        ][:max_chunks]
        if relevant:
            selected_indexes = sorted(relevant)
            selection_strategy = "query_relevance"
    chunks = [all_chunks[index] for index in selected_indexes]
    truncated_to_chunks = len(chunks) < len(all_chunks)

    if not chunks:
        return "", {
            "materialization": "text",
            "chunk_char_limit": chunk_chars,
            "chunk_count": 0,
            "max_chunks_applied": max_chunks,
            "truncated_to_chunks": False,
            "source_char_count": len(raw),
            "model_text_char_count": 0,
            "usage_role": str(usage_role or "primary"),
            "selection_strategy": selection_strategy,
            "selected_chunk_indexes": [],
        }

    if len(chunks) == 1:
        model_text = chunks[0]
    else:
        total = len(chunks)
        lines = [f"[Chunk {idx + 1}/{total}]\n{chunk}" for idx, chunk in enumerate(chunks)]
        model_text = "\n\n".join(lines)

    if truncated_to_chunks:
        model_text = (
            f"{model_text}\n\n[truncated] Attachment text was clipped to {len(chunks)} chunks "
            f"(limit={max_chunks}, chunk_chars={chunk_chars})."
        )

    return model_text, {
        "materialization": "text",
        "chunk_char_limit": chunk_chars,
        "chunk_count": len(chunks),
        "max_chunks_applied": max_chunks,
        "truncated_to_chunks": truncated_to_chunks,
        "source_char_count": len(raw),
        "model_text_char_count": len(model_text),
        "usage_role": str(usage_role or "primary"),
        "selection_strategy": selection_strategy,
        "selected_chunk_indexes": selected_indexes,
    }


def extract_text_attachment_artifact(
    *,
    payload: bytes,
    mime_type: str,
    filename: str,
    transform_mode: str,
    usage_role: str = "primary",
    query_text: str = "",
) -> dict[str, Any]:
    """
    Build text materialization output for one attachment.

    Returns:
      {
        "effective_transform_mode": "text_only|table_summary",
        "extracted_text": "...",
        "artifact_meta": {...}
      }
    """
    if not _materializes_as_text(mime_type=mime_type, requested_mode=transform_mode):
        raise ValueError(
            f"Attachment mime '{mime_type}' with transform_mode '{transform_mode}' does not materialize as text."
        )

    effective_mode = _effective_transform_mode(
        mime_type=mime_type,
        requested_mode=transform_mode,
    )
    extracted_raw = _extract_text_payload(
        payload=payload,
        mime_type=mime_type,
        filename=filename,
    )
    extracted_text, artifact_meta = _format_text_chunks_for_model(
        extracted_raw,
        usage_role=usage_role,
        query_text=query_text,
    )
    artifact_meta = dict(artifact_meta)
    artifact_meta["effective_transform_mode"] = effective_mode
    artifact_meta["mime_type"] = str(mime_type or "").strip().lower()
    artifact_meta["filename"] = str(filename or "file")

    return {
        "effective_transform_mode": effective_mode,
        "extracted_text": extracted_text,
        "extracted_source_text": extracted_raw,
        "artifact_meta": artifact_meta,
    }


def _to_uuid(value: Any) -> UUID:
    if isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"code": "invalid_attachment_id", "message": f"Invalid file_id '{value}'."},
        ) from exc


@dataclass(frozen=True)
class ResolvedAttachment:
    file_id: UUID
    usage_role: str
    transform_mode: str
    order_index: int
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    storage_bucket: str
    storage_key: str
    ingestion_meta: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class InferenceAttachment:
    file_id: UUID
    usage_role: str
    transform_mode: str
    order_index: int
    filename: str
    mime_type: str
    size_bytes: int
    data_base64: str


def _require_attachments_runtime() -> None:
    if not _attachments_enabled():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "attachments_disabled",
                "message": "Attachments are disabled. Enable ENABLE_ATTACHMENTS=true.",
            },
        )
    if not API_DB_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail={
                "code": "attachments_require_db",
                "message": "Attachments require DATABASE_URL (DB mode).",
            },
        )


def _read_attr(item: Any, name: str, default: Any = None) -> Any:
    if isinstance(item, dict):
        return item.get(name, default)
    return getattr(item, name, default)


def resolve_request_attachments(
    *,
    user_id: UUID,
    attachments: Iterable[Any] | None,
) -> list[ResolvedAttachment]:
    """
    Resolve request attachment references into owned uploaded_file rows.

    Raises HTTPException on invalid ownership, status, limits, or malformed IDs.
    """
    items = list(attachments or [])
    if not items:
        return []

    _require_attachments_runtime()

    max_files = _max_attachments_per_request()
    if len(items) > max_files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "too_many_attachments",
                "message": f"Maximum {max_files} attachments allowed per request.",
                "max_attachments_per_request": max_files,
            },
        )

    resolved: list[ResolvedAttachment] = []
    seen: set[UUID] = set()
    with _db_uow(commit_on_success=False) as db_session:
        for idx, item in enumerate(items):
            file_id = _to_uuid(_read_attr(item, "file_id"))
            if file_id in seen:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "code": "duplicate_attachment",
                        "message": f"Duplicate file_id '{file_id}' in attachments.",
                    },
                )
            seen.add(file_id)

            usage_role = str(_read_attr(item, "usage_role", "primary") or "primary")
            transform_mode = str(_read_attr(item, "transform_mode", "auto") or "auto")

            row = get_uploaded_file_for_user(
                db_session,
                user_id=user_id,
                file_id=file_id,
                include_deleted=False,
            )
            if not row:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={
                        "code": "attachment_file_not_found",
                        "message": f"Attachment file '{file_id}' was not found for this API key owner.",
                    },
                )

            file_status = str(row.get("status") or "").strip().lower()
            if file_status not in READY_FILE_STATUSES:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "code": "attachment_file_not_ready",
                        "message": (
                            f"Attachment file '{file_id}' is in status '{file_status}'. "
                            "Only ready files can be used."
                        ),
                        "status": file_status,
                    },
                )

            mime_type = str(row.get("mime_type") or "").strip().lower()
            size_bytes = int(row.get("size_bytes") or 0)
            if not mime_type or size_bytes <= 0:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail={
                        "code": "attachment_metadata_invalid",
                        "message": f"Attachment file '{file_id}' has invalid stored metadata.",
                    },
                )

            ingestion_meta = row.get("ingestion_meta")
            resolved.append(
                ResolvedAttachment(
                    file_id=file_id,
                    usage_role=usage_role,
                    transform_mode=transform_mode,
                    order_index=idx,
                    original_filename=str(row.get("original_filename") or "file"),
                    mime_type=mime_type,
                    size_bytes=size_bytes,
                    status=file_status,
                    storage_bucket=str(row.get("storage_bucket") or "").strip(),
                    storage_key=str(row.get("storage_key") or "").strip(),
                    ingestion_meta=(
                        dict(ingestion_meta) if isinstance(ingestion_meta, dict) else {}
                    ),
                )
            )

    return resolved


def materialize_inference_attachments(
    attachments: list[ResolvedAttachment],
    *,
    query_text: str = "",
) -> list[dict[str, Any]]:
    """Load attachment bytes from object storage and convert to provider-neutral payloads."""
    if not attachments:
        return []

    storage = None
    items: list[dict[str, Any]] = []
    for attachment in attachments:
        effective_mode = _effective_transform_mode(
            mime_type=attachment.mime_type,
            requested_mode=attachment.transform_mode,
        )
        cached_text = str(attachment.ingestion_meta.get("cached_extracted_text") or "").strip()
        if (
            cached_text
            and attachment.ingestion_meta.get("ingestion_state") == "ready"
            and _materializes_as_text(
                mime_type=attachment.mime_type,
                requested_mode=attachment.transform_mode,
            )
        ):
            extracted_text, artifact_meta = _format_text_chunks_for_model(
                cached_text,
                usage_role=attachment.usage_role,
                query_text=query_text,
            )
            items.append(
                {
                    "file_id": str(attachment.file_id),
                    "usage_role": attachment.usage_role,
                    "transform_mode": effective_mode,
                    "order_index": attachment.order_index,
                    "filename": attachment.original_filename or "file",
                    "mime_type": attachment.mime_type,
                    "size_bytes": attachment.size_bytes,
                    "extracted_text": extracted_text,
                    "artifact_meta": {
                        **artifact_meta,
                        "effective_transform_mode": effective_mode,
                        "mime_type": attachment.mime_type,
                        "filename": attachment.original_filename or "file",
                        "parse_cache_reused": True,
                    },
                }
            )
            continue

        if not attachment.storage_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "attachment_storage_metadata_invalid",
                    "message": f"Attachment '{attachment.file_id}' has no storage key.",
                },
            )
        try:
            if storage is None:
                storage = get_object_storage()
            payload = storage.get_bytes(key=attachment.storage_key)
        except ObjectStorageConfigurationError as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"code": "storage_not_configured", "message": str(exc)},
            ) from exc
        except ObjectStorageOperationError as exc:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail={
                    "code": "attachment_read_failed",
                    "message": (
                        f"Failed to read attachment '{attachment.file_id}' from object storage."
                    ),
                },
            ) from exc

        if not payload:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={
                    "code": "attachment_payload_empty",
                    "message": f"Attachment '{attachment.file_id}' is empty in storage.",
                },
            )

        if _materializes_as_text(
            mime_type=attachment.mime_type,
            requested_mode=attachment.transform_mode,
        ):
            try:
                artifact = extract_text_attachment_artifact(
                    payload=payload,
                    mime_type=attachment.mime_type,
                    filename=attachment.original_filename or "file",
                    transform_mode=attachment.transform_mode,
                    usage_role=attachment.usage_role,
                    query_text=query_text,
                )
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail={
                        "code": "attachment_text_extraction_failed",
                        "message": (
                            f"Failed to extract text from '{attachment.original_filename}'. "
                            f"{exc!s}"
                        ),
                        "mime_type": attachment.mime_type,
                    },
                ) from exc

            artifact_meta_value = artifact.get("artifact_meta")
            items.append(
                {
                    "file_id": str(attachment.file_id),
                    "usage_role": attachment.usage_role,
                    "transform_mode": str(
                        artifact.get("effective_transform_mode") or effective_mode
                    ),
                    "order_index": attachment.order_index,
                    "filename": attachment.original_filename or "file",
                    "mime_type": attachment.mime_type,
                    "size_bytes": attachment.size_bytes,
                    "extracted_text": str(artifact.get("extracted_text") or ""),
                    "artifact_meta": (
                        dict(artifact_meta_value) if isinstance(artifact_meta_value, dict) else {}
                    ),
                }
            )
            continue

        if (
            effective_mode in {"text_only", "table_summary"}
            and attachment.mime_type not in TEXT_EXTRACTABLE_MIME_TYPES
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "unsupported_transform_mode_for_mime",
                    "message": (
                        f"transform_mode '{effective_mode}' is not supported for MIME "
                        f"type '{attachment.mime_type}'."
                    ),
                    "mime_type": attachment.mime_type,
                    "transform_mode": effective_mode,
                },
            )

        items.append(
            {
                "file_id": str(attachment.file_id),
                "usage_role": attachment.usage_role,
                "transform_mode": effective_mode,
                "order_index": attachment.order_index,
                "filename": attachment.original_filename or "file",
                "mime_type": attachment.mime_type,
                "size_bytes": attachment.size_bytes,
                "data_base64": base64.b64encode(payload).decode("ascii"),
                "artifact_meta": {
                    "materialization": "binary",
                    "effective_transform_mode": effective_mode,
                    "mime_type": attachment.mime_type,
                    "filename": attachment.original_filename or "file",
                    "size_bytes": int(attachment.size_bytes),
                },
            }
        )

    return items


def build_request_attachment_persistence_items(
    *,
    resolved_attachments: list[ResolvedAttachment],
    inference_attachments: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """
    Build persistence-safe request attachment rows.

    Semantics:
    - `uploaded_files.ingestion_meta`: file-level ingestion/extraction metadata.
    - `request_attachments.resolved_artifact_meta`: request-level materialization decision
      for this specific turn (effective transform mode, chunk budget, etc.).
    """
    if not resolved_attachments:
        return []

    by_file_id: dict[str, dict[str, Any]] = {}
    for item in inference_attachments or []:
        if not isinstance(item, dict):
            continue
        file_id = str(item.get("file_id") or "").strip()
        if file_id:
            by_file_id[file_id] = item

    out: list[dict[str, Any]] = []
    for attachment in resolved_attachments:
        file_id_text = str(attachment.file_id)
        inference_item = by_file_id.get(file_id_text) or {}
        artifact_meta = inference_item.get("artifact_meta")
        safe_meta = dict(artifact_meta) if isinstance(artifact_meta, dict) else {}
        if not safe_meta:
            safe_meta = {
                "materialization": (
                    "text"
                    if _materializes_as_text(
                        mime_type=attachment.mime_type,
                        requested_mode=attachment.transform_mode,
                    )
                    else "binary"
                ),
                "effective_transform_mode": _effective_transform_mode(
                    mime_type=attachment.mime_type,
                    requested_mode=attachment.transform_mode,
                ),
                "mime_type": attachment.mime_type,
                "filename": attachment.original_filename or "file",
                "size_bytes": int(attachment.size_bytes),
            }

        out.append(
            {
                "file_id": attachment.file_id,
                "usage_role": attachment.usage_role,
                "transform_mode": str(
                    inference_item.get("transform_mode")
                    or _effective_transform_mode(
                        mime_type=attachment.mime_type,
                        requested_mode=attachment.transform_mode,
                    )
                ),
                "order_index": int(attachment.order_index),
                "resolved_artifact_meta": safe_meta,
            }
        )
    return out


def _get_model_candidate_or_400(*, provider: str, model: str):
    provider_norm = str(provider or "").strip().lower()
    model_norm = str(model or "").strip()
    candidate = ModelRegistry.from_yaml().find_model(provider_norm, model_norm)
    if candidate:
        return candidate
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={
            "code": "invalid_model",
            "message": f"Unknown or unsupported model '{provider_norm}:{model_norm}'.",
        },
    )


def compatible_providers_for_attachments(
    attachments: list[ResolvedAttachment],
) -> list[str]:
    """Return providers that can accept all resolved attachments."""
    if not attachments:
        return []

    binary_attachments = [
        attachment
        for attachment in attachments
        if not _materializes_as_text(
            mime_type=attachment.mime_type,
            requested_mode=attachment.transform_mode,
        )
    ]
    if not binary_attachments:
        return sorted(
            {
                candidate.provider
                for candidate in ModelRegistry.from_yaml().list_models(include_disabled=False)
            }
        )

    required_mime_types = {attachment.mime_type for attachment in binary_attachments}
    largest_size = max(attachment.size_bytes for attachment in binary_attachments)
    count = len(binary_attachments)
    registry = ModelRegistry.from_yaml()

    compatible: set[str] = set()
    for candidate in registry.list_models(include_disabled=False):
        if not candidate.supports_image_input:
            continue

        if candidate.max_attachments_per_request is not None and count > int(
            candidate.max_attachments_per_request
        ):
            continue
        if candidate.max_attachment_bytes is not None and largest_size > int(
            candidate.max_attachment_bytes
        ):
            continue

        supported = {mime.strip().lower() for mime in candidate.supported_attachment_mime_types}
        if required_mime_types.issubset(supported):
            compatible.add(candidate.provider)

    return sorted(compatible)


def enforce_model_attachment_compatibility(
    *,
    provider: str,
    model: str,
    attachments: list[ResolvedAttachment],
    mode: str,
) -> None:
    """Validate one provider/model target can consume all resolved attachments."""
    if not attachments:
        return

    binary_attachments = [
        attachment
        for attachment in attachments
        if not _materializes_as_text(
            mime_type=attachment.mime_type,
            requested_mode=attachment.transform_mode,
        )
    ]
    if not binary_attachments:
        return

    candidate = _get_model_candidate_or_400(provider=provider, model=model)
    if not candidate.supports_image_input:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "attachment_model_incompatible",
                "message": (
                    f"Selected model '{candidate.provider}:{candidate.model_name}' "
                    "does not support attachment inputs."
                ),
                "mode": mode,
                "provider": candidate.provider,
                "model": candidate.model_name,
            },
        )

    attachment_count = len(binary_attachments)
    if candidate.max_attachments_per_request is not None and attachment_count > int(
        candidate.max_attachments_per_request
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "attachment_count_exceeded",
                "message": (
                    f"Model '{candidate.provider}:{candidate.model_name}' supports at most "
                    f"{candidate.max_attachments_per_request} attachments per request."
                ),
                "max_attachments_per_request": int(candidate.max_attachments_per_request),
                "attachment_count": attachment_count,
            },
        )

    largest_size = max(attachment.size_bytes for attachment in binary_attachments)
    if candidate.max_attachment_bytes is not None and largest_size > int(
        candidate.max_attachment_bytes
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "attachment_size_exceeded",
                "message": (
                    f"Model '{candidate.provider}:{candidate.model_name}' supports max attachment size "
                    f"{candidate.max_attachment_bytes} bytes."
                ),
                "max_attachment_bytes": int(candidate.max_attachment_bytes),
                "attachment_largest_bytes": largest_size,
            },
        )

    supported_mime_types = {
        mime.strip().lower()
        for mime in (candidate.supported_attachment_mime_types or [])
        if str(mime).strip()
    }
    attachment_mime_types = sorted({attachment.mime_type for attachment in binary_attachments})
    unsupported = sorted(mime for mime in attachment_mime_types if mime not in supported_mime_types)
    if unsupported:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "attachment_mime_type_incompatible",
                "message": (
                    f"Model '{candidate.provider}:{candidate.model_name}' does not support one or more "
                    "attachment MIME types."
                ),
                "unsupported_mime_types": unsupported,
                "supported_mime_types": sorted(supported_mime_types),
            },
        )
