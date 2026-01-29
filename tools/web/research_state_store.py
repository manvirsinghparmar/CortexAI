"""Thread-safe in-memory store for ResearchState objects."""
import threading
from typing import Optional, Dict
from .research_state import ResearchState


class ResearchStateStore:
    """
    Thread-safe singleton store for per-session ResearchState.

    Allows concurrent access from FastAPI requests while maintaining
    session-level research memory.
    """

    def __init__(self):
        """Initialize store with thread lock and session dict."""
        self._lock = threading.Lock()
        self._sessions: Dict[str, ResearchState] = {}

    def get(self, session_id: str) -> Optional[ResearchState]:
        """
        Get research state for a session.

        Args:
            session_id: Session identifier

        Returns:
            ResearchState if exists, None otherwise
        """
        with self._lock:
            return self._sessions.get(session_id)

    def set(self, session_id: str, state: ResearchState) -> None:
        """
        Store research state for a session.

        Args:
            session_id: Session identifier
            state: ResearchState to store
        """
        with self._lock:
            self._sessions[session_id] = state

    def clear(self, session_id: str) -> None:
        """
        Clear research state for a session.

        Args:
            session_id: Session identifier
        """
        with self._lock:
            self._sessions.pop(session_id, None)

    def clear_all(self) -> None:
        """Clear all research states (for testing)."""
        with self._lock:
            self._sessions.clear()


# Module-level singleton instance
_store = ResearchStateStore()


def get_research_state_store() -> ResearchStateStore:
    """
    Get the global research state store singleton.

    Returns:
        Singleton ResearchStateStore instance
    """
    return _store