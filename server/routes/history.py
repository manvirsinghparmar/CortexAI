"""History endpoints - retrieve and delete past chat records."""

from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from db import clear_llm_history, delete_llm_history_entry, get_llm_history_entries
from server import persistence as persistence_service
from server.dependencies import get_api_key
from server.database import clear_all_history, delete_history_entry, get_history

router = APIRouter(prefix="/v1", tags=["History"])

API_DB_ENABLED = persistence_service.API_DB_ENABLED
ApiKeyPersistenceResolution = persistence_service.ApiKeyPersistenceResolution
_resolve_api_key_for_request = persistence_service.resolve_api_key_for_request
_db_uow = persistence_service.db_uow


class HistoryEntry(BaseModel):
    id: int
    timestamp: str
    mode: str
    prompt: str
    provider: str
    model: str
    response: str
    latency_ms: Optional[int] = None
    tokens: Optional[int] = None
    cost: Optional[float] = None


@router.get("/history", response_model=List[HistoryEntry])
async def list_history(
    request: Request,
    limit: int = 100,
    api_key: str = Depends(get_api_key),
):
    """Return recent chat history entries (newest first)."""
    if API_DB_ENABLED:
        req_id = str(getattr(request.state, "request_id", "") or uuid4())
        with _db_uow(commit_on_success=False) as db_session:
            resolution = _resolve_api_key_for_request(
                api_key=api_key,
                request_id=req_id,
                db_session=db_session,
            )
            return get_llm_history_entries(db_session, resolution.user_id, limit=limit)

    return get_history(limit=limit)


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    request: Request,
    entry_id: int,
    api_key: str = Depends(get_api_key),
):
    """Delete a single history entry by ID."""
    if API_DB_ENABLED:
        req_id = str(getattr(request.state, "request_id", "") or uuid4())
        with _db_uow() as db_session:
            resolution = _resolve_api_key_for_request(
                api_key=api_key,
                request_id=req_id,
                db_session=db_session,
            )
            removed = delete_llm_history_entry(db_session, resolution.user_id, entry_id)

        if not removed:
            raise HTTPException(status_code=404, detail="History entry not found")
        return

    removed = delete_history_entry(entry_id)
    if not removed:
        raise HTTPException(status_code=404, detail="History entry not found")


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    request: Request,
    api_key: str = Depends(get_api_key),
):
    """Delete all history entries."""
    if API_DB_ENABLED:
        req_id = str(getattr(request.state, "request_id", "") or uuid4())
        with _db_uow() as db_session:
            resolution = _resolve_api_key_for_request(
                api_key=api_key,
                request_id=req_id,
                db_session=db_session,
            )
            clear_llm_history(db_session, resolution.user_id)
        return

    clear_all_history()
