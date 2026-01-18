"""Factory for creating Tavily research service from environment configuration."""
import os
from .cache import InMemoryTTLCache
from .tavily_service import TavilyResearchService
from utils.logger import get_logger

logger = get_logger(__name__)

# Singleton cache instance (process-shared)
_cache_instance = None


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
        ttl = int(os.getenv("RESEARCH_CACHE_TTL_SECONDS", "3600"))
        _cache_instance = InMemoryTTLCache(ttl_seconds=ttl)

    # Get Tavily API key
    tavily_api_key = os.getenv("TAVILY_API_KEY", "")
    if not tavily_api_key:
        raise ValueError("TAVILY_API_KEY not set in environment")

    logger.info("🚀 Using Tavily for web research (JavaScript rendering enabled)")

    return TavilyResearchService(
        api_key=tavily_api_key,
        cache=_cache_instance,
        max_sources=5
    )
