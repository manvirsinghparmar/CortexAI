"""Utilities for optional web research enrichment via Tavily."""

from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

import httpx

from utils.logger import get_logger

logger = get_logger(__name__)

TAVILY_SEARCH_URL = "https://api.tavily.com/search"
DEFAULT_MAX_RESULTS = 5
DEFAULT_TIMEOUT_S = 8.0
MAX_SNIPPET_CHARS = 320


def _trim_text(text: Any, limit: int = MAX_SNIPPET_CHARS) -> str:
    raw = str(text or "").strip()
    if len(raw) <= limit:
        return raw
    return raw[: limit - 3].rstrip() + "..."


def _normalize_sources(payload: Dict[str, Any], max_results: int) -> List[Dict[str, str]]:
    sources: List[Dict[str, str]] = []
    for item in (payload.get("results") or [])[:max_results]:
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        title = str(item.get("title") or "").strip() or url
        snippet = _trim_text(item.get("content") or "")
        sources.append(
            {
                "title": title,
                "url": url,
                "snippet": snippet,
            }
        )
    return sources


def build_web_enriched_prompt(
    prompt: str,
    *,
    summary: str = "",
    sources: List[Dict[str, str]] | None = None,
) -> str:
    """Inject web findings into the model prompt with clear citation instructions."""
    sources = sources or []
    blocks: List[str] = [
        "Web findings (cite factual claims as [1], [2], etc.; say when evidence is missing):"
    ]

    if summary:
        blocks.append(f"Summary: {_trim_text(summary, limit=600)}")

    for idx, source in enumerate(sources, start=1):
        title = _trim_text(source.get("title") or "", limit=180)
        url = _trim_text(source.get("url") or "", limit=300)
        snippet = _trim_text(source.get("snippet") or "", limit=MAX_SNIPPET_CHARS)
        blocks.append(f"[{idx}] {title}\nURL: {url}\nSnippet: {snippet}")

    findings = "\n\n".join(blocks)
    return f"{prompt.strip()}\n\n{findings}"


async def maybe_enrich_prompt_with_web(
    prompt: str,
    *,
    enabled: bool,
    max_results: int = DEFAULT_MAX_RESULTS,
    timeout_s: float = DEFAULT_TIMEOUT_S,
) -> Tuple[str, Dict[str, Any]]:
    """
    Optionally enrich a prompt with Tavily research context.

    Returns:
        (effective_prompt, metadata)
    """
    if not enabled:
        return prompt, {"enabled": False, "used": False, "reason": "disabled"}

    api_key = (os.getenv("TAVILY_API_KEY") or "").strip()
    if not api_key:
        logger.warning("Web mode enabled but TAVILY_API_KEY is not configured")
        return prompt, {"enabled": True, "used": False, "reason": "missing_api_key", "source_count": 0}

    request_payload = {
        "api_key": api_key,
        "query": prompt,
        "search_depth": "advanced",
        "include_answer": True,
        "max_results": max(1, min(int(max_results), 10)),
    }

    try:
        async with httpx.AsyncClient(timeout=timeout_s) as client:
            response = await client.post(TAVILY_SEARCH_URL, json=request_payload)
            response.raise_for_status()
            payload = response.json() if response.content else {}
    except Exception as exc:
        logger.warning(
            "Tavily lookup failed",
            extra={"extra_fields": {"error": str(exc), "error_type": type(exc).__name__}},
        )
        return prompt, {"enabled": True, "used": False, "reason": "request_failed", "source_count": 0}

    summary = _trim_text(payload.get("answer") or "", limit=600)
    sources = _normalize_sources(payload if isinstance(payload, dict) else {}, max_results=max_results)
    if not summary and not sources:
        return prompt, {"enabled": True, "used": False, "reason": "no_results", "source_count": 0}

    enriched_prompt = build_web_enriched_prompt(prompt, summary=summary, sources=sources)
    return (
        enriched_prompt,
        {
            "enabled": True,
            "used": True,
            "reason": "ok",
            "source_count": len(sources),
            "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
        },
    )

