"""Session-level research state store for follow-up handling."""

import threading

from .contracts import ResearchContext


class SessionResearchStore:
    """
    Thread-safe singleton store for last research per session.

    Allows follow-up queries to reuse previous research results
    instead of triggering new irrelevant searches.
    """

    def __init__(self):
        """Initialize store with thread lock and session dict."""
        self._lock = threading.Lock()
        self._sessions: dict[str, ResearchContext] = {}

    def get(self, session_id: str) -> ResearchContext | None:
        """
        Get last research context for a session.

        Args:
            session_id: Session identifier

        Returns:
            ResearchContext if exists, None otherwise
        """
        with self._lock:
            return self._sessions.get(session_id)

    def set(self, session_id: str, ctx: ResearchContext) -> None:
        """
        Store research context for a session.

        Args:
            session_id: Session identifier
            ctx: ResearchContext to store
        """
        with self._lock:
            self._sessions[session_id] = ctx

    def clear(self, session_id: str) -> None:
        """
        Clear research context for a session.

        Args:
            session_id: Session identifier
        """
        with self._lock:
            self._sessions.pop(session_id, None)


# Module-level singleton instance
_store = SessionResearchStore()


def get_session_store() -> SessionResearchStore:
    """Get the global session research store singleton."""
    return _store
