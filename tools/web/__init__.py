"""Web research tools for CortexAI."""
from .contracts import SearchResult, SourceDoc, ResearchContext
from .factory import create_research_service_from_env

__all__ = [
    "SearchResult",
    "SourceDoc",
    "ResearchContext",
    "create_research_service_from_env"
]
