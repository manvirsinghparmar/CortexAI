"""Tavily-based research service."""

import hashlib
from dataclasses import replace
from typing import Protocol

from utils.logger import get_logger

from .cache import InMemoryTTLCache
from .contracts import ProviderSearchResponse, ResearchContext
from .intent import rewrite_query
from .research_pack import build_injected_text
from .tavily_client import TavilyResearchClient

logger = get_logger(__name__)


class _ResearchClient(Protocol):
    def get_network_diagnostics_snapshot(self) -> dict: ...

    def search_with_usage(
        self, *, query: str, max_results: int, search_depth: str
    ) -> ProviderSearchResponse: ...


def _text_hash(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


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
        self.client: _ResearchClient = TavilyResearchClient(api_key=api_key)
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
            prompt_hash = _text_hash(prompt)
            prompt_length = len(str(prompt or ""))
            client_diag = self.client.get_network_diagnostics_snapshot()
            if use_cache:
                cached = self.cache.get(prompt)
                if cached:
                    logger.info(
                        "Research cache hit",
                        extra={
                            "extra_fields": {
                                "event": "research.cache.hit",
                                "provider": "tavily",
                                "prompt_hash": prompt_hash,
                                "prompt_length": prompt_length,
                            }
                        },
                    )
                    return replace(
                        cached,
                        cache_hit=True,
                        provider_credits_used=0,
                        provider_credits_estimated=False,
                    )
            else:
                logger.info(
                    "Research cache bypassed",
                    extra={
                        "extra_fields": {
                            "event": "research.cache.bypass",
                            "provider": "tavily",
                            "prompt_hash": prompt_hash,
                            "prompt_length": prompt_length,
                        }
                    },
                )

            search_query = rewrite_query(prompt)
            query_hash = _text_hash(search_query)
            query_length = len(str(search_query or ""))
            if search_query != prompt:
                logger.info(
                    "Research query rewritten",
                    extra={
                        "extra_fields": {
                            "event": "research.query.rewritten",
                            "provider": "tavily",
                            "prompt_hash": prompt_hash,
                            "query_hash": query_hash,
                            "prompt_length": prompt_length,
                            "query_length": query_length,
                        }
                    },
                )

            logger.info(
                "Research search dispatch",
                extra={
                    "extra_fields": {
                        "event": "research.dispatch",
                        "provider": "tavily",
                        "prompt_hash": prompt_hash,
                        "query_hash": query_hash,
                        "query_length": query_length,
                        "use_cache": bool(use_cache),
                        "max_sources": int(self.max_sources),
                        **client_diag,
                    }
                },
            )
            search_response = self.client.search_with_usage(
                query=search_query,
                max_results=self.max_sources,
                search_depth="advanced",
            )
            sources = search_response.sources

            if not sources:
                logger.warning(
                    "Research returned no sources",
                    extra={
                        "extra_fields": {
                            "event": "research.search.empty",
                            "provider": "tavily",
                            "prompt_hash": prompt_hash,
                            "query_hash": query_hash,
                            "query_length": query_length,
                            **client_diag,
                        }
                    },
                )
                return ResearchContext(
                    used=False,
                    error="no_search_results",
                    search_query=search_query,
                    provider_credits_used=search_response.provider_credits_used,
                    provider_credits_estimated=search_response.provider_credits_estimated,
                )

            injected_text = build_injected_text(sources)
            context = ResearchContext(
                used=True,
                injected_text=injected_text,
                sources=sources,
                cache_hit=False,
                search_query=search_query,
                provider_credits_used=search_response.provider_credits_used,
                provider_credits_estimated=search_response.provider_credits_estimated,
            )

            if use_cache:
                self.cache.set(prompt, context)

            logger.info(
                "Research context ready",
                extra={
                    "extra_fields": {
                        "event": "research.context.ready",
                        "provider": "tavily",
                        "prompt_hash": prompt_hash,
                        "query_hash": query_hash,
                        "source_count": len(sources),
                        "cache_written": bool(use_cache),
                        **client_diag,
                    }
                },
            )
            return context

        except Exception as exc:
            client_diag = self.client.get_network_diagnostics_snapshot()
            logger.exception(
                "Research context build failed",
                extra={
                    "extra_fields": {
                        "event": "research.context.failure",
                        "provider": "tavily",
                        "prompt_hash": _text_hash(prompt),
                        "prompt_length": len(str(prompt or "")),
                        "error_type": type(exc).__name__,
                        **client_diag,
                    }
                },
            )
            return ResearchContext(used=False, error=str(exc), search_query=prompt)
