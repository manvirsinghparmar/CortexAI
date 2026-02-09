"""Web research tools for CortexAI."""

from .contracts import ResearchContext, SearchResult, SourceDoc
from .factory import create_research_service_from_env

__all__ = ["ResearchContext", "SearchResult", "SourceDoc", "create_research_service_from_env"]
