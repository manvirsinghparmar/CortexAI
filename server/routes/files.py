"""File upload/status endpoints for attachments."""

from __future__ import annotations

from uuid import uuid4, UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from server import files_service
#from server.dependencies import get_api_key
from server.dependencies import get_auth #, get_orchestrator
from server.schemas.responses import FileUploadResponseDTO, FileStatusResponseDTO

router = APIRouter(prefix="/v1/files", tags=["Files"])


def _header_value(request: Request, key: str) -> str | None:
    value = request.headers.get(key)
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


@router.post("/upload", response_model=FileUploadResponseDTO)
async def upload_file(
    request: Request,
    #api_key: str = Depends(get_api_key),
    auth=Depends(get_auth),
):
    """
    Upload one attachment file as raw request bytes.

    Headers:
    - X-File-Name: original file name (optional, defaults to "file")
    - X-File-Content-Type: file MIME type (optional; falls back to Content-Type)
    """
    payload = await request.body()
    filename = _header_value(request, "X-File-Name") or "file"
    mime_type = (
        _header_value(request, "X-File-Content-Type")
        or _header_value(request, "Content-Type")
        or ""
    )
    if ";" in mime_type:
        mime_type = mime_type.split(";", 1)[0].strip().lower()

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "empty_file", "message": "Request body is empty."},
        )

    request_id = str(getattr(request.state, "request_id", "") or uuid4())
    result = files_service.upload_user_file(
        api_key=auth.api_key_or_none(),
        request_id=request_id,
        filename=filename,
        mime_type=mime_type,
        payload=payload,
    )
    return FileUploadResponseDTO(**result)


@router.get("/{file_id}", response_model=FileStatusResponseDTO)
async def get_file_status(
    request: Request,
    file_id: UUID,
    api_key: str = Depends(get_auth),
):
    """Get one uploaded file metadata row scoped to API key ownership."""
    request_id = str(getattr(request.state, "request_id", "") or uuid4())
    result = files_service.get_user_file(
        api_key=api_key,
        request_id=request_id,
        file_id=file_id,
    )
    return FileStatusResponseDTO(**result)
