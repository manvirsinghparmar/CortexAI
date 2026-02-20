"""History endpoints — retrieve and delete past chat records."""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel
from typing import List, Optional
from server.database import get_history, delete_history_entry, clear_all_history
from server.dependencies import get_api_key

router = APIRouter(prefix="/v1", tags=["History"])


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
    limit: int = 100,
    api_key: str = Depends(get_api_key),
):
    """Return recent chat history entries (newest first)."""
    return get_history(limit=limit)


@router.delete("/history/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entry(
    entry_id: int,
    api_key: str = Depends(get_api_key),
):
    """Delete a single history entry by ID."""
    removed = delete_history_entry(entry_id)
    if not removed:
        raise HTTPException(status_code=404, detail="History entry not found")


@router.delete("/history", status_code=status.HTTP_204_NO_CONTENT)
async def clear_history(
    api_key: str = Depends(get_api_key),
):
    """Delete all history entries."""
    clear_all_history()
