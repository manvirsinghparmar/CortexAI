"""File upload/status endpoints for attachments."""

from __future__ import annotations

import hashlib
from urllib.parse import urlparse
from uuid import uuid4, UUID
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status

from server import files_service
from server import persistence as persistence_service
from server.dependencies import AuthResult, get_auth
from server.routes.session_auth import SessionScopedAuthGuard, auth_mode as session_auth_mode
from server.schemas.responses import FileUploadResponseDTO, FileStatusResponseDTO
from utils.logger import get_logger

logger = get_logger(__name__)
_SESSION_AUTH_GUARD = SessionScopedAuthGuard(
    route_label="Attachment",
    rejection_event="upload.route.rejected.auth_mode",
    logger=logger,
    log_message="Attachment route rejected non-session auth",
)

router = APIRouter(prefix="/v1/files", tags=["Files"])
API_DB_ENABLED = persistence_service.API_DB_ENABLED
_resolve_identity = persistence_service.resolve_identity


_EDGE_HEADER_KEYS = (
    "Host",
    "X-Forwarded-For",
    "X-Forwarded-Proto",
    "X-Forwarded-Port",
    "X-Amz-Cf-Id",
    "CloudFront-Viewer-Country",
    "CloudFront-Is-Desktop-Viewer",
    "CloudFront-Is-Mobile-Viewer",
    "CloudFront-Is-Tablet-Viewer",
    "CloudFront-Is-SmartTV-Viewer",
    "Via",
    "X-Amzn-Trace-Id",
)


def _header_value(request: Request, key: str) -> str | None:
    value = request.headers.get(key)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _hash_for_logs(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def _host_from_url(value: str | None) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return str(urlparse(text).netloc or "")
    except Exception:
        return ""


def _safe_int(value: str | None) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except Exception:
        return None


def _edge_context_fields(request: Request, *, request_id: str, auth: AuthResult) -> dict[str, Any]:
    x_forwarded_for = _header_value(request, "X-Forwarded-For") or ""
    forwarded_chain = [part.strip() for part in x_forwarded_for.split(",") if part.strip()]
    content_length_header = _header_value(request, "Content-Length")
    content_length = _safe_int(content_length_header)
    user_agent = _header_value(request, "User-Agent") or ""
    referer = _header_value(request, "Referer") or ""
    origin = _header_value(request, "Origin") or ""

    edge_headers: dict[str, str] = {}
    for key in _EDGE_HEADER_KEYS:
        header_value = _header_value(request, key)
        if header_value:
            edge_headers[key.lower().replace("-", "_")] = header_value

    return {
        "request_id": request_id,
        "method": str(request.method or "").upper(),
        "path": str(request.url.path or ""),
        "query_present": bool(request.url.query),
        "client_ip": request.client.host if request.client else "",
        "host": _header_value(request, "Host") or "",
        "content_type": _header_value(request, "Content-Type") or "",
        "content_length_header": content_length,
        "x_forwarded_for_first": forwarded_chain[0] if forwarded_chain else "",
        "x_forwarded_for_hops": len(forwarded_chain),
        "referer_host": _host_from_url(referer),
        "origin_host": _host_from_url(origin),
        "user_agent_hash": _hash_for_logs(user_agent),
        "has_cookie_header": bool(_header_value(request, "Cookie")),
        "has_authorization_header": bool(_header_value(request, "Authorization")),
        "has_x_api_key_header": bool(_header_value(request, "X-API-Key")),
        "auth_mode": session_auth_mode(auth),
        "api_key_hash": _hash_for_logs(auth.api_key_or_none()),
        "edge_headers": edge_headers,
    }


@router.post("/upload", response_model=FileUploadResponseDTO)
async def upload_file(
    request: Request,
    auth: AuthResult = Depends(get_auth),
):
    """
    Upload one attachment file as raw request bytes.

    Headers:
    - X-File-Name: original file name (optional, defaults to "file")
    - X-File-Content-Type: file MIME type (optional; falls back to Content-Type)
    """
    request_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=request_id)
    filename = _header_value(request, "X-File-Name") or "file"
    mime_type = (
        _header_value(request, "X-File-Content-Type")
        or _header_value(request, "Content-Type")
        or ""
    )
    if ";" in mime_type:
        mime_type = mime_type.split(";", 1)[0].strip().lower()

    logger.info(
        "Attachment upload route received request",
        extra={
            "extra_fields": {
                "event": "upload.route.received",
                **_edge_context_fields(request, request_id=request_id, auth=auth),
                "filename_hash": _hash_for_logs(filename),
                "mime_type": mime_type,
            }
        },
    )

    payload = await request.body()
    payload_size = len(payload or b"")
    content_length_header = _safe_int(_header_value(request, "Content-Length"))
    logger.info(
        "Attachment upload route read request body",
        extra={
            "extra_fields": {
                "event": "upload.route.payload.read",
                "request_id": request_id,
                "payload_size_bytes": payload_size,
                "content_length_header": content_length_header,
                "content_length_matches_payload": (
                    content_length_header == payload_size if content_length_header is not None else None
                ),
                "filename_hash": _hash_for_logs(filename),
                "mime_type": mime_type,
            }
        },
    )

    if not payload:
        logger.warning(
            "Attachment upload route rejected empty payload",
            extra={
                "extra_fields": {
                    "event": "upload.route.rejected.empty_body",
                    "request_id": request_id,
                    "filename_hash": _hash_for_logs(filename),
                    "mime_type": mime_type,
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Request body is empty."},
        )

    try:
        result = files_service.upload_user_file(
            auth=auth,
            request_id=request_id,
            filename=filename,
            mime_type=mime_type,
            payload=payload,
        )
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        logger.warning(
            "Attachment upload route rejected request",
            extra={
                "extra_fields": {
                    "event": "upload.route.rejected",
                    "request_id": request_id,
                    "status_code": int(exc.status_code),
                    "error_code": str(detail.get("code") or ""),
                    "filename_hash": _hash_for_logs(filename),
                    "mime_type": mime_type,
                    "payload_size_bytes": payload_size,
                }
            },
        )
        raise
    except BaseException as exc:
        logger.exception(
            "Attachment upload route failed unexpectedly",
            extra={
                "extra_fields": {
                    "event": "upload.route.exception",
                    "request_id": request_id,
                    "error_type": type(exc).__name__,
                    "filename_hash": _hash_for_logs(filename),
                    "mime_type": mime_type,
                    "payload_size_bytes": payload_size,
                }
            },
        )
        raise

    logger.info(
        "Attachment upload route completed successfully",
        extra={
            "extra_fields": {
                "event": "upload.route.success",
                "request_id": request_id,
                "file_id": str(result.get("file_id") or ""),
                "status": str(result.get("status") or ""),
                "filename_hash": _hash_for_logs(filename),
                "mime_type": mime_type,
                "payload_size_bytes": payload_size,
            }
        },
    )
    return FileUploadResponseDTO(**result)


@router.get("/{file_id}", response_model=FileStatusResponseDTO)
async def get_file_status(
    request: Request,
    file_id: UUID,
    auth: AuthResult = Depends(get_auth),
):
    """Get one uploaded file metadata row scoped to authenticated user identity."""
    request_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=request_id)
    result = files_service.get_user_file(
        auth=auth,
        request_id=request_id,
        file_id=file_id,
    )
    return FileStatusResponseDTO(**result)
