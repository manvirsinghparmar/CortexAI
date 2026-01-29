"""Tavily-based research service - replaces Brave Search + extractor pipeline."""
from typing import Optional
from .contracts import ResearchContext, SourceDoc
from .tavily_client import TavilyResearchClient
from .cache import InMemoryTTLCache
from .research_pack import build_injected_text
from .intent import rewrite_query
from utils.logger import get_logger

logger = get_logger(__name__)


class TavilyResearchService:
    """
    Tavily-powered research service.

    Replaces the entire Brave Search + fetch + extract pipeline with Tavily API.
    Implements same interface as ResearchService for drop-in compatibility.
    """

    def __init__(
        self,
        api_key: str,
        cache: InMemoryTTLCache,
        max_sources: int = 5
    ):
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

    def build(self, prompt: str) -> ResearchContext:
        """
        Build research context from prompt using Tavily.

        This method NEVER raises exceptions - all errors are caught and returned
        in ResearchContext with used=False and error set.

        Args:
            prompt: User prompt to research

        Returns:
            ResearchContext with results or error
        """
        try:
            # Check cache first
            cached = self.cache.get(prompt)
            if cached:
                logger.info(f"✅ Cache hit for query: '{prompt[:50]}...'")
                cached.cache_hit = True
                return cached

            # Rewrite query for better results (e.g., finance queries)
            search_query = rewrite_query(prompt)
            if search_query != prompt:
                logger.info(f"Query rewritten: '{prompt[:30]}...' → '{search_query[:50]}...'")

            # Search using Tavily
            logger.info(f"🔎 Tavily searching: {search_query[:100]}...")
            sources = self.client.search(
                query=search_query,
                max_results=self.max_sources,
                search_depth="advanced"  # Use advanced for better quality
            )

            if not sources:
                logger.warning("❌ No sources found from Tavily")
                return ResearchContext(
                    used=False,
                    error="no_search_results",
                    search_query=search_query
                )

            # Build injection text
            injected_text = build_injected_text(sources)

            # Create research context
            context = ResearchContext(
                used=True,
                injected_text=injected_text,
                sources=sources,
                cache_hit=False,
                search_query=search_query
            )

            # Cache the result
            self.cache.set(prompt, context)

            logger.info(f"✅ Tavily research complete: {len(sources)} sources")
            return context

        except Exception as e:
            logger.error(f"❌ Tavily research failed: {e}", exc_info=True)
            return ResearchContext(
                used=False,
                error=str(e),
                search_query=prompt
            )
