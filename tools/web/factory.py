"""Factory for creating Tavily research service from environment configuration."""

import os

from utils.logger import get_logger

from .cache import InMemoryTTLCache
from .tavily_service import TavilyResearchService

logger = get_logger(__name__)

# Singleton cache instance (process-shared)
_cache_instance = None


def _safe_int_env(name: str, default: int) -> int:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return default
    try:
        parsed = int(raw)
    except Exception:
        return default
    return parsed if parsed > 0 else default


def create_research_service_from_env() -> TavilyResearchService:
    """
    Create Tavily ResearchService from environment variables.

    Environment variables:
        TAVILY_API_KEY: Tavily API key (required)
        RESEARCH_CACHE_TTL_SECONDS: Cache TTL in seconds (default: 3600)

    Returns:
        Configured TavilyResearchService instance

    Raises:
        ValueError: If TAVILY_API_KEY is not set
    """
    global _cache_instance

    # Create singleton cache if not exists
    if _cache_instance is None:
        ttl = _safe_int_env("RESEARCH_CACHE_TTL_SECONDS", default=3600)
        _cache_instance = InMemoryTTLCache(ttl_seconds=ttl)

    # Get Tavily API key
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        raise ValueError("TAVILY_API_KEY not set in environment")

    logger.info(
        "Using Tavily for web research",
        extra={
            "extra_fields": {
                "event": "research.provider.selected",
                "provider": "tavily",
                "cache_ttl_seconds": _safe_int_env("RESEARCH_CACHE_TTL_SECONDS", default=3600),
                "max_sources": 5,
                "diagnostic_host": str(
                    os.getenv("TAVILY_NETWORK_DIAGNOSTICS_HOST", "api.tavily.com")
                ),
                "diagnostic_port": _safe_int_env("TAVILY_NETWORK_DIAGNOSTICS_PORT", default=443),
                "diagnostic_interval_seconds": _safe_int_env(
                    "TAVILY_NETWORK_DIAGNOSTICS_INTERVAL_SECONDS", default=300
                ),
                "diagnostic_timeout_seconds": _safe_int_env(
                    "TAVILY_NETWORK_DIAGNOSTICS_TIMEOUT_SECONDS", default=2
                ),
                "https_proxy_present": bool(str(os.getenv("HTTPS_PROXY") or "").strip()),
                "http_proxy_present": bool(str(os.getenv("HTTP_PROXY") or "").strip()),
                "no_proxy_present": bool(str(os.getenv("NO_PROXY") or "").strip()),
            }
        },
    )

    return TavilyResearchService(api_key=tavily_api_key, cache=_cache_instance, max_sources=5)
