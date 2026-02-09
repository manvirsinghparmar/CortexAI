"""Tavily API client for AI-powered web research.

Tavily handles:
- JavaScript rendering (reads modern websites)
- Content extraction (production-grade)
- Relevance ranking (best sources first)
- Caching and deduplication

This replaces Brave Search + extractor + caching.
"""

import os

from utils.logger import get_logger

from .contracts import SourceDoc

logger = get_logger(__name__)


class TavilyResearchClient:
    """
    Tavily-powered research client.

    Replaces the entire Brave Search + extractor pipeline with one API call.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Tavily client.

        Args:
            api_key: Tavily API key (defaults to TAVILY_API_KEY env var)
        """
        self.api_key = api_key or os.getenv("TAVILY_API_KEY")

        if not self.api_key:
            raise ValueError("TAVILY_API_KEY not found in environment")

        # ✅ Lazy import so CI/tests don't require tavily unless Research Mode uses it
        try:
            from tavily import TavilyClient
        except ModuleNotFoundError as e:
            raise ModuleNotFoundError(
                "Optional dependency 'tavily' is not installed. "
                "Install it to enable Research Mode: pip install tavily-python"
            ) from e

        self.client = TavilyClient(api_key=self.api_key)
        logger.info("Tavily client initialized")

    def search(
        self, query: str, max_results: int = 5, search_depth: str = "advanced"
    ) -> list[SourceDoc]:
        """
        Search the web using Tavily API.

        Args:
            query: Search query
            max_results: Maximum number of sources (default: 5)
            search_depth: "basic" (faster) or "advanced" (deeper, recommended)

        Returns:
            List of SourceDoc objects with full content
        """
        logger.info(f"Tavily search: '{query}' (max_results={max_results}, depth={search_depth})")

        try:
            # Call Tavily API
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_raw_content=False,  # We don't need raw HTML
                include_answer=False,  # We generate our own answer
            )

            # Convert Tavily results to SourceDoc format
            sources = []

            for idx, result in enumerate(response.get("results", []), start=1):
                relevance_score = result.get("score", 0.0)  # Tavily relevance score (0-1)

                source = SourceDoc(
                    id=idx,
                    title=result.get("title", "Untitled"),
                    url=result.get("url", ""),
                    excerpt=result.get("content", ""),  # Tavily provides clean extracted content
                    fetched_at=response.get("query_time", "N/A"),
                )

                sources.append(source)
                logger.debug(f"[{idx}] {source.title[:50]} (score: {relevance_score:.2f})")

            logger.info(f"✅ Tavily returned {len(sources)} sources")
            return sources

        except Exception as e:
            logger.error(f"❌ Tavily search failed: {e}", exc_info=True)
            return []

    def qna_search(self, query: str) -> tuple[str, list[SourceDoc]]:
        """
        Get direct answer + sources from Tavily.

        This uses Tavily's built-in answer generation (faster but less control).

        Args:
            query: Search query

        Returns:
            Tuple of (answer, sources)
        """
        logger.info(f"Tavily QnA search: '{query}'")

        try:
            response = self.client.qna_search(query=query)

            answer = response.get("answer", "")

            # Convert sources
            sources = []
            for idx, result in enumerate(response.get("results", []), start=1):
                source = SourceDoc(
                    id=idx,
                    title=result.get("title", "Untitled"),
                    url=result.get("url", ""),
                    excerpt=result.get("content", ""),
                    fetched_at=response.get("query_time", "N/A"),
                )
                sources.append(source)

            logger.info(f"✅ Tavily QnA: {len(sources)} sources, answer length: {len(answer)}")
            return answer, sources

        except Exception as e:
            logger.error(f"❌ Tavily QnA failed: {e}", exc_info=True)
            return "", []
