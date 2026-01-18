"""Data contracts for web research module."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class SearchResult:
    """Result from a search provider."""
    title: str
    url: str
    snippet: str = ""


@dataclass
class SourceDoc:
    """A processed source document with extracted content."""
    id: int
    title: str
    url: str
    fetched_at: str  # ISO 8601 format
    excerpt: str


@dataclass
class ResearchContext:
    """Research context to be injected into LLM prompts."""
    used: bool
    injected_text: str = ""
    sources: List[SourceDoc] = field(default_factory=list)
    error: Optional[str] = None
    cache_hit: bool = False
    search_query: str = ""  # Actual search query used (after rewriting)
