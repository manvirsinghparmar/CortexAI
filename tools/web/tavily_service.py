"""Tavily-based research service."""

from utils.logger import get_logger

from .cache import InMemoryTTLCache
from .contracts import ResearchContext
from .intent import rewrite_query
from .research_pack import build_injected_text
from .tavily_client import TavilyResearchClient

logger = get_logger(__name__)


class TavilyResearchService:
    """
    Tavily-powered research service.

    Replaces the previous search + extraction pipeline with Tavily API.
    """

    def __init__(self, api_key: str, cache: InMemoryTTLCache, max_sources: int = 5):
        """
        Initialize Tavily research service.

        Args:
            api_key: Tavily API key
            cache: TTL cache for results
            max_sources: Maximum sources to return (default: 5)
        """
        self.client = TavilyResearchClient(api_key=api_key)
        self.cache = cache
        self.max_sources = max_sources

    def build(self, prompt: str, *, use_cache: bool = True) -> ResearchContext:
        """
        Build research context from prompt using Tavily.

        This method never raises exceptions. Errors are returned as ResearchContext
        with ``used=False`` and ``error`` set.

        Args:
            prompt: User prompt to research
            use_cache: Whether to read/write local cache for this call

        Returns:
            ResearchContext with results or error
        """
        try:
            if use_cache:
                cached = self.cache.get(prompt)
                if cached:
                    logger.info(f"Cache hit for query: '{prompt[:50]}...'")
                    cached.cache_hit = True
                    return cached
            else:
                logger.info(f"Bypassing research cache for query: '{prompt[:50]}...'")

            search_query = rewrite_query(prompt)
            if search_query != prompt:
                logger.info(f"Query rewritten: '{prompt[:30]}...' -> '{search_query[:50]}...'")

            logger.info(f"Tavily searching: {search_query[:100]}...")
            sources = self.client.search(
                query=search_query,
                max_results=self.max_sources,
                search_depth="advanced",
            )

            if not sources:
                logger.warning("No sources found from Tavily")
                return ResearchContext(used=False, error="no_search_results", search_query=search_query)

            injected_text = build_injected_text(sources)
            context = ResearchContext(
                used=True,
                injected_text=injected_text,
                sources=sources,
                cache_hit=False,
                search_query=search_query,
            )

            if use_cache:
                self.cache.set(prompt, context)

            logger.info(f"Tavily research complete: {len(sources)} sources")
            return context

        except Exception as exc:
            logger.error(f"Tavily research failed: {exc}", exc_info=True)
            return ResearchContext(used=False, error=str(exc), search_query=prompt)
