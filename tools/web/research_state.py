"""ResearchState dataclass for stateful research memory."""

import hashlib
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal

ResearchMode = Literal["off", "auto", "on"]
Decision = Literal["skip", "reuse", "search"]


@dataclass(frozen=True)
class ResearchSource:
    """Immutable research source with citation info."""

    id: int
    title: str
    url: str
    fetched_at: str
    excerpt: str = ""


@dataclass(frozen=True)
class ResearchState:
    """
    Immutable per-session research state representing ONE topic.

    Required contract fields:
    - topic: canonical topic string
    - query: search query used
    - injected_text: system injection text
    - sources: list of SourceDoc
    - created_at: ISO timestamp
    - last_used_at: ISO timestamp
    - used: whether research was performed
    - cache_hit: whether result was cached
    - error: optional error message
    """

    topic: str  # canonical topic
    query: str  # search query used
    injected_text: str  # system injection text
    sources: list[ResearchSource] = field(default_factory=list)
    created_at: str = ""  # ISO 8601 timestamp
    last_used_at: str = ""  # ISO 8601 timestamp
    used: bool = False
    cache_hit: bool = False
    error: str | None = None

    # Additional fields for compatibility
    session_id: str = "default"
    mode: ResearchMode = "auto"
    ttl_seconds: int = 900  # 15 minutes default

    def is_expired(self, now: datetime | None = None) -> bool:
        """
        Check if research state is expired based on TTL.

        Args:
            now: Current UTC datetime (defaults to utcnow)

        Returns:
            True if expired or never used, False otherwise
        """
        if not self.last_used_at:
            return True

        now = now or datetime.now(timezone.utc)
        try:
            last_used = datetime.fromisoformat(self.last_used_at.replace("Z", "+00:00"))
            elapsed = (now - last_used).total_seconds()
            return elapsed > self.ttl_seconds
        except (ValueError, AttributeError):
            return True

    def with_update(self, **kwargs) -> "ResearchState":
        """
        Return a new ResearchState instance with updated fields.

        Automatically updates last_used_at to current UTC time.
        """
        # Always update the last_used_at timestamp
        if "last_used_at" not in kwargs:
            kwargs["last_used_at"] = datetime.now(timezone.utc).isoformat()

        return replace(self, **kwargs)

    def to_metadata(self) -> dict[str, Any]:
        """
        Convert to metadata dict for UnifiedResponse.metadata merge.

        Returns:
            Dict with research metadata fields
        """
        return {
            "research_used": self.used,
            "research_reused": self.cache_hit,
            "research_topic": self.topic if self.topic else None,
            "research_error": self.error,
            "sources": [
                {"id": s.id, "title": s.title, "url": s.url, "fetched_at": s.fetched_at}
                for s in self.sources
            ],
        }


def compute_topic_key(text: str) -> str:
    """
    Compute a stable topic key from text.

    Args:
        text: Input text (e.g., user prompt)

    Returns:
        16-character hex hash of normalized text
    """
    normalized = text.lower().strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def create_initial_state(
    session_id: str, mode: ResearchMode = "auto", ttl_seconds: int = 900
) -> ResearchState:
    """
    Create a new initial ResearchState.

    Args:
        session_id: Session identifier
        mode: Research mode
        ttl_seconds: TTL for research freshness

    Returns:
        New ResearchState instance
    """
    now = datetime.now(timezone.utc).isoformat()
    return ResearchState(
        topic="",
        query="",
        injected_text="",
        sources=[],
        created_at=now,
        last_used_at="",
        used=False,
        cache_hit=False,
        error=None,
        session_id=session_id,
        mode=mode,
        ttl_seconds=ttl_seconds,
    )
