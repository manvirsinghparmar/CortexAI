"""Best-effort PostgreSQL persistence for reusable research state."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from config.cache_optimization import persistent_research_reuse_enabled
from tools.web.research_state import ResearchMode, ResearchSource, ResearchState
from utils.logger import get_logger

logger = get_logger(__name__)


def _decode_research_mode(value: object) -> ResearchMode:
    if value == "off":
        return "off"
    if value == "on":
        return "on"
    return "auto"


def load_research_state(session_id: str) -> ResearchState | None:
    if not persistent_research_reuse_enabled():
        return None
    try:
        from sqlalchemy import select

        from db.session import SessionLocal
        from db.tables import get_table

        table = get_table("research_reuse_cache")
        with SessionLocal() as db:
            row = db.execute(
                select(table).where(
                    table.c.session_id == str(session_id),
                    table.c.expires_at > datetime.now(timezone.utc),
                )
            ).first()
        if row is None:
            return None
        payload = dict(row._mapping).get("state") or {}
        if not isinstance(payload, dict):
            return None
        return _decode_state(payload)
    except Exception:
        logger.warning("Persistent research reuse lookup unavailable", exc_info=True)
        return None


def save_research_state(state: ResearchState) -> None:
    if not persistent_research_reuse_enabled() or not state.used:
        return
    try:
        from sqlalchemy import select, insert, update

        from db.session import SessionLocal
        from db.tables import get_table

        table = get_table("research_reuse_cache")
        expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(1, int(state.ttl_seconds))
        )
        with SessionLocal() as db:
            exists = db.execute(
                select(table.c.session_id).where(table.c.session_id == state.session_id)
            ).scalar_one_or_none()
            values = {
                "state": _encode_state(state),
                "last_used_at": datetime.now(timezone.utc),
                "expires_at": expires_at,
            }
            if exists is None:
                db.execute(
                    insert(table).values(
                        session_id=state.session_id,
                        created_at=datetime.now(timezone.utc),
                        **values,
                    )
                )
            else:
                db.execute(
                    update(table)
                    .where(table.c.session_id == state.session_id)
                    .values(**values)
                )
            db.commit()
    except Exception:
        logger.warning("Persistent research reuse write unavailable", exc_info=True)


def _encode_state(state: ResearchState) -> dict[str, Any]:
    return {
        "topic": state.topic,
        "query": state.query,
        "injected_text": state.injected_text,
        "sources": [source.__dict__ for source in state.sources],
        "created_at": state.created_at,
        "last_used_at": state.last_used_at,
        "used": state.used,
        "cache_hit": state.cache_hit,
        "error": state.error,
        "session_id": state.session_id,
        "mode": state.mode,
        "ttl_seconds": state.ttl_seconds,
        "topic_key": state.topic_key,
        "provider_credits_consumed": state.provider_credits_consumed,
    }


def _decode_state(payload: dict[str, Any]) -> ResearchState:
    sources = [
        ResearchSource(
            id=int(item.get("id") or 0),
            title=str(item.get("title") or ""),
            url=str(item.get("url") or ""),
            fetched_at=str(item.get("fetched_at") or ""),
            excerpt=str(item.get("excerpt") or ""),
        )
        for item in payload.get("sources", [])
        if isinstance(item, dict)
    ]
    return ResearchState(
        topic=str(payload.get("topic") or ""),
        query=str(payload.get("query") or ""),
        injected_text=str(payload.get("injected_text") or ""),
        sources=sources,
        created_at=str(payload.get("created_at") or ""),
        last_used_at=str(payload.get("last_used_at") or ""),
        used=bool(payload.get("used")),
        cache_hit=bool(payload.get("cache_hit")),
        error=str(payload.get("error")) if payload.get("error") else None,
        session_id=str(payload.get("session_id") or "default"),
        mode=_decode_research_mode(payload.get("mode")),
        ttl_seconds=max(1, int(payload.get("ttl_seconds") or 900)),
        topic_key=str(payload.get("topic_key") or ""),
        provider_credits_consumed=max(
            0, int(payload.get("provider_credits_consumed") or 0)
        ),
    )
