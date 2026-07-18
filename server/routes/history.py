"""History endpoints - retrieve and delete past chat records."""

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from db import (
    clear_llm_history,
    delete_llm_history_entry,
    get_llm_history_entries,
    rename_history_session,
)
from server import persistence as persistence_service
from server.dependencies import AuthResult, get_auth
from server.routes.session_auth import SessionScopedAuthGuard
from utils.logger import get_logger

router = APIRouter(prefix="/v1", tags=["History"])
logger = get_logger(__name__)
_SESSION_AUTH_GUARD = SessionScopedAuthGuard(
    route_label="History",
    rejection_event="history.route.rejected.auth_mode",
    logger=logger,
)

API_DB_ENABLED = persistence_service.API_DB_ENABLED
ApiKeyPersistenceResolution = persistence_service.ApiKeyPersistenceResolution
_resolve_identity = persistence_service.resolve_identity
_db_uow = persistence_service.db_uow


def _require_db_mode() -> None:
    if API_DB_ENABLED:
        return
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="History endpoints require DATABASE_URL (DB mode).",
    )


class HistoryEntry(BaseModel):
    id: int
    session_id: Optional[str] = None
    session_title: Optional[str] = None
    request_group_id: Optional[str] = None
    timestamp: str
    mode: str
    prompt: str
    provider: str
    model: str
    response: str
    latency_ms: Optional[int] = None
    tokens: Optional[int] = None
    cost: Optional[float] = None
    web_source_items: List[dict[str, str]] = Field(default_factory=list)


class RenameHistorySessionRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class RenameHistorySessionResponse(BaseModel):
    session_id: str
    title: str


@router.get("/history", response_model=List[HistoryEntry])
async def list_history(
    request: Request,
    limit: int = 100,
    session_id: str | None = None,
    auth: AuthResult = Depends(get_auth),
):
    """Return recent chat history entries (newest first)."""
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
    with _db_uow(commit_on_success=False) as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        return get_llm_history_entries(
            db_session,
            resolution.user_id,
            limit=limit,
            session_id=session_id,
        )


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    request: Request,
    entry_id: int,
    auth: AuthResult = Depends(get_auth),
):
    """Delete a single history entry by ID."""
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
    with _db_uow() as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        removed = delete_llm_history_entry(db_session, resolution.user_id, entry_id)

    if not removed:
        raise HTTPException(status_code=404, detail="History entry not found")


@router.patch(
    "/history/session/{session_id}",
    response_model=RenameHistorySessionResponse,
)
async def rename_session(
    request: Request,
    session_id: str,
    payload: RenameHistorySessionRequest,
    auth: AuthResult = Depends(get_auth),
):
    """Rename one authenticated user's persisted chat session."""
    _require_db_mode()
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=422, detail="Session title cannot be empty")

    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
    with _db_uow() as db_session:
        resolution = _resolve_identity(
            auth=auth,
            request_id=req_id,
            db_session=db_session,
        )
        renamed = rename_history_session(
            db_session,
            resolution.user_id,
            session_id,
            title,
        )

    if not renamed:
        raise HTTPException(status_code=404, detail="History session not found")
    return RenameHistorySessionResponse(session_id=session_id, title=title)


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    request: Request,
    session_id: str | None = None,
    auth: AuthResult = Depends(get_auth),
):
    """Delete all history entries, or one session when session_id is provided."""
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    _SESSION_AUTH_GUARD.require(auth=auth, request_id=req_id)
    with _db_uow() as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        clear_llm_history(db_session, resolution.user_id, session_id=session_id)
