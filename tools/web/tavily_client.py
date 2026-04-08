"""Tavily API client for AI-powered web research."""

import os
from datetime import datetime, timezone
from typing import Any

from utils.logger import get_logger

from .contracts import SourceDoc

logger = get_logger(__name__)


class TavilyResearchClient:
    """
    Tavily-powered research client.

    Replaces direct search + extractor plumbing with one API call.
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

        # Lazy import so local/unit runs do not require Tavily dependency unless used.
        try:
            from tavily import TavilyClient
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "Optional dependency 'tavily' is not installed. "
                "Install it to enable Research Mode: pip install tavily-python"
            ) from exc

        self.client = TavilyClient(api_key=self.api_key)
        logger.info("Tavily client initialized")

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _normalize_timestamp(value: Any) -> str:
        """
        Normalize provider timestamp-ish values to UTC ISO 8601.

        Numeric values are accepted only when they look like epoch seconds/millis.
        This intentionally ignores small numeric values like ``0.42`` (query duration).
        """
        if isinstance(value, str):
            candidate = value.strip()
            if not candidate:
                return ""
            try:
                parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            except ValueError:
                return ""
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat()

        if isinstance(value, (int, float)):
            ts = float(value)
            if ts > 1_000_000_000_000:  # epoch milliseconds
                ts = ts / 1000.0
            elif ts <= 1_000_000_000:  # likely not epoch time
                return ""

            try:
                return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()
            except (OverflowError, OSError, ValueError):
                return ""

        return ""

    def _resolve_fetched_at(self, response: dict[str, Any], result: dict[str, Any], fallback: str) -> str:
        """
        Resolve best-available fetched timestamp for each source.

        Preference:
        1) per-result published/updated timestamps
        2) response-level retrieval timestamps
        3) query_time only if it is parseable as a real timestamp
        4) server-side fallback timestamp
        """
        result_timestamp_keys = (
            "published_date",
            "published_at",
            "updated_at",
            "created_at",
            "date",
        )
        response_timestamp_keys = (
            "fetched_at",
            "retrieved_at",
            "retrievedAt",
            "search_timestamp",
            "timestamp",
        )

        for key in result_timestamp_keys:
            normalized = self._normalize_timestamp(result.get(key))
            if normalized:
                return normalized

        for key in response_timestamp_keys:
            normalized = self._normalize_timestamp(response.get(key))
            if normalized:
                return normalized

        query_time = self._normalize_timestamp(response.get("query_time"))
        if query_time:
            return query_time

        return fallback

    def search(
        self, query: str, max_results: int = 5, search_depth: str = "advanced"
    ) -> list[SourceDoc]:
        """
        Search the web using Tavily API.

        Args:
            query: Search query
            max_results: Maximum number of sources
            search_depth: "basic" (faster) or "advanced" (deeper)

        Returns:
            List of SourceDoc objects with extracted content
        """
        logger.info(f"Tavily search: '{query}' (max_results={max_results}, depth={search_depth})")

        try:
            response = self.client.search(
                query=query,
                max_results=max_results,
                search_depth=search_depth,
                include_raw_content=False,
                include_answer=False,
            )

            request_timestamp = self._utc_now_iso()
            sources: list[SourceDoc] = []

            for idx, result in enumerate(response.get("results", []), start=1):
                relevance_score = result.get("score", 0.0)
                fetched_at = self._resolve_fetched_at(response, result, request_timestamp)

                source = SourceDoc(
                    id=idx,
                    title=result.get("title", "Untitled"),
                    url=result.get("url", ""),
                    excerpt=result.get("content", ""),
                    fetched_at=fetched_at,
                )
                sources.append(source)
                logger.debug(f"[{idx}] {source.title[:50]} (score: {relevance_score:.2f})")

            logger.info(f"Tavily returned {len(sources)} sources")
            return sources

        except Exception as exc:
            logger.error(f"Tavily search failed: {exc}", exc_info=True)
            return []

    def qna_search(self, query: str) -> tuple[str, list[SourceDoc]]:
        """
        Get direct answer + sources from Tavily.

        Args:
            query: Search query

        Returns:
            Tuple of (answer, sources)
        """
        logger.info(f"Tavily QnA search: '{query}'")

        try:
            response = self.client.qna_search(query=query)
            answer = response.get("answer", "")
            request_timestamp = self._utc_now_iso()

            sources: list[SourceDoc] = []
            for idx, result in enumerate(response.get("results", []), start=1):
                source = SourceDoc(
                    id=idx,
                    title=result.get("title", "Untitled"),
                    url=result.get("url", ""),
                    excerpt=result.get("content", ""),
                    fetched_at=self._resolve_fetched_at(response, result, request_timestamp),
                )
                sources.append(source)

            logger.info(f"Tavily QnA complete: {len(sources)} sources, answer length: {len(answer)}")
            return answer, sources

        except Exception as exc:
            logger.error(f"Tavily QnA failed: {exc}", exc_info=True)
            return "", []
