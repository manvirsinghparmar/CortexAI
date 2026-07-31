"""Tavily API client for AI-powered web research."""

from __future__ import annotations

import errno
import hashlib
import math
import os
import socket
import time
from datetime import datetime, timezone
from typing import Any

from utils.logger import get_logger

from .contracts import ProviderSearchResponse, SourceDoc
from .tavily_resolver import (
    TAVILY_CREDITS_PER_ADVANCED_SEARCH,
    resolve_tavily_search_options,
)

logger = get_logger(__name__)


class TavilyResearchClient:
    """
    Tavily-powered research client.

    Replaces direct search + extractor plumbing with one API call.
    """

    _DEFAULT_DIAGNOSTIC_HOST = "api.tavily.com"
    _DEFAULT_DIAGNOSTIC_PORT = 443

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
        self._network_diag_interval_seconds = self._coerce_positive_int(
            os.getenv("TAVILY_NETWORK_DIAGNOSTICS_INTERVAL_SECONDS"),
            default=300,
        )
        self._network_diag_timeout_seconds = float(
            self._coerce_positive_int(os.getenv("TAVILY_NETWORK_DIAGNOSTICS_TIMEOUT_SECONDS"), default=2)
        )
        self._diagnostic_host = (
            str(os.getenv("TAVILY_NETWORK_DIAGNOSTICS_HOST") or "").strip()
            or self._DEFAULT_DIAGNOSTIC_HOST
        )
        self._diagnostic_port = self._coerce_positive_int(
            os.getenv("TAVILY_NETWORK_DIAGNOSTICS_PORT"),
            default=self._DEFAULT_DIAGNOSTIC_PORT,
        )
        self._last_network_diag_at = 0.0
        self._last_network_diag_status = "never"
        self._last_network_diag: dict[str, Any] = {}
        logger.info(
            "Tavily client initialized",
            extra={
                "extra_fields": {
                    "event": "research.client.initialized",
                    "provider": "tavily",
                    "api_key_hash": self._query_hash(self.api_key),
                    "diagnostic_host": self._diagnostic_host,
                    "diagnostic_port": int(self._diagnostic_port),
                    "diagnostic_interval_seconds": int(self._network_diag_interval_seconds),
                    "diagnostic_timeout_seconds": float(self._network_diag_timeout_seconds),
                    **self._proxy_flags(),
                }
            },
        )
        self._maybe_emit_network_diagnostics(trigger="init")

    @staticmethod
    def _utc_now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _coerce_positive_int(raw: str | None, default: int) -> int:
        try:
            parsed = int(str(raw or "").strip())
        except Exception:
            return default
        return parsed if parsed > 0 else default

    @staticmethod
    def _query_hash(query: str) -> str:
        text = str(query or "").strip()
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _error_message_excerpt(exc: Exception) -> str:
        message = str(exc or "").strip()
        if not message:
            return ""
        return message[:220]

    @classmethod
    def _exception_chain_types(cls, exc: Exception, *, max_depth: int = 5) -> list[str]:
        chain: list[str] = []
        current: BaseException | None = exc
        depth = 0
        while current is not None and depth < max_depth:
            chain.append(type(current).__name__)
            current = current.__cause__ or current.__context__
            depth += 1
        return chain

    @classmethod
    def _classify_error_kind(cls, exc: Exception) -> str:
        chain_types = cls._exception_chain_types(exc)
        lower_message = str(exc or "").lower()
        for marker in (
            "name or service not known",
            "temporary failure in name resolution",
            "nodename nor servname provided",
            "getaddrinfo failed",
            "dns",
        ):
            if marker in lower_message:
                return "dns_resolution_failed"
        if isinstance(exc, socket.gaierror):
            return "dns_resolution_failed"
        if "timed out" in lower_message or "timeout" in lower_message:
            return "timeout"
        if "connection refused" in lower_message:
            return "connection_refused"
        if "proxy" in lower_message:
            return "proxy_error"
        if "certificate" in lower_message or "ssl" in lower_message or "tls" in lower_message:
            return "tls_error"
        if "429" in lower_message or "rate limit" in lower_message:
            return "rate_limited"
        if "401" in lower_message or "403" in lower_message or "forbidden" in lower_message:
            return "auth_forbidden"
        if "500" in lower_message or "502" in lower_message or "503" in lower_message or "504" in lower_message:
            return "provider_server_error"
        if "connectionerror" in (name.lower() for name in chain_types):
            return "connection_error"
        return "unknown"

    @staticmethod
    def _proxy_flags() -> dict[str, bool]:
        return {
            "http_proxy_present": bool(str(os.getenv("HTTP_PROXY") or "").strip()),
            "https_proxy_present": bool(str(os.getenv("HTTPS_PROXY") or "").strip()),
            "no_proxy_present": bool(str(os.getenv("NO_PROXY") or "").strip()),
        }

    def _network_diag_snapshot(self) -> dict[str, Any]:
        now = time.time()
        last_at = float(getattr(self, "_last_network_diag_at", 0.0) or 0.0)
        age_ms = int(max(0.0, now - last_at) * 1000) if last_at > 0.0 else None
        return {
            "network_diag_status": str(getattr(self, "_last_network_diag_status", "never") or "never"),
            "network_diag_age_ms": age_ms,
        }

    def get_network_diagnostics_snapshot(self) -> dict[str, Any]:
        """Return latest diagnostics summary for callers that need context fields."""
        snapshot = dict(self._network_diag_snapshot())
        last_diag = getattr(self, "_last_network_diag", {})
        if isinstance(last_diag, dict):
            if "diagnostic_host" not in snapshot:
                snapshot["diagnostic_host"] = str(last_diag.get("host") or "")
            if "diagnostic_port" not in snapshot:
                snapshot["diagnostic_port"] = int(last_diag.get("port") or 0) or None
            if "network_diag_dns_ok" not in snapshot:
                snapshot["network_diag_dns_ok"] = (
                    bool(last_diag.get("dns_ok")) if "dns_ok" in last_diag else None
                )
            if "network_diag_tcp_ok" not in snapshot:
                snapshot["network_diag_tcp_ok"] = (
                    bool(last_diag.get("tcp_ok")) if "tcp_ok" in last_diag else None
                )
        return snapshot

    def _maybe_emit_network_diagnostics(self, *, trigger: str) -> None:
        interval_s = self._coerce_positive_int(
            str(getattr(self, "_network_diag_interval_seconds", "300")),
            default=300,
        )
        now = time.time()
        last = float(getattr(self, "_last_network_diag_at", 0.0) or 0.0)
        if last > 0.0 and now - last < interval_s:
            return
        self._last_network_diag_at = now

        host = str(getattr(self, "_diagnostic_host", self._DEFAULT_DIAGNOSTIC_HOST) or self._DEFAULT_DIAGNOSTIC_HOST)
        port = int(getattr(self, "_diagnostic_port", self._DEFAULT_DIAGNOSTIC_PORT) or self._DEFAULT_DIAGNOSTIC_PORT)
        timeout_s = float(
            self._coerce_positive_int(
                str(getattr(self, "_network_diag_timeout_seconds", "2")),
                default=2,
            )
        )

        dns_ok = False
        dns_error_type = ""
        dns_error_message = ""
        dns_addresses: list[str] = []
        dns_started = time.perf_counter()
        try:
            infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            dns_addresses = sorted({str(info[4][0]) for info in infos if info and len(info) >= 5 and info[4]})
            dns_ok = True
        except Exception as exc:
            dns_error_type = type(exc).__name__
            dns_error_message = self._error_message_excerpt(exc)
        dns_latency_ms = int((time.perf_counter() - dns_started) * 1000)

        tcp_ok = False
        tcp_error_type = ""
        tcp_error_message = ""
        tcp_error_errno = None
        tcp_started = time.perf_counter()
        try:
            with socket.create_connection((host, port), timeout=timeout_s):
                tcp_ok = True
        except OSError as exc:
            tcp_error_type = type(exc).__name__
            tcp_error_message = self._error_message_excerpt(exc)
            tcp_error_errno = exc.errno if getattr(exc, "errno", None) is not None else None
        except Exception as exc:
            tcp_error_type = type(exc).__name__
            tcp_error_message = self._error_message_excerpt(exc)
        tcp_latency_ms = int((time.perf_counter() - tcp_started) * 1000)

        status = "ok" if (dns_ok and tcp_ok) else "degraded"
        self._last_network_diag_status = status
        self._last_network_diag = {
            "host": host,
            "port": port,
            "dns_ok": dns_ok,
            "dns_latency_ms": dns_latency_ms,
            "dns_ip_count": len(dns_addresses),
            "tcp_ok": tcp_ok,
            "tcp_latency_ms": tcp_latency_ms,
            "tcp_error_errno": tcp_error_errno,
        }

        log_fn = logger.info if status == "ok" else logger.warning
        log_fn(
            "Tavily network diagnostics",
            extra={
                "extra_fields": {
                    "event": "research.network.diagnostics",
                    "provider": "tavily",
                    "trigger": trigger,
                    "status": status,
                    "diagnostic_host": host,
                    "diagnostic_port": port,
                    "dns_ok": dns_ok,
                    "dns_latency_ms": dns_latency_ms,
                    "dns_ip_count": len(dns_addresses),
                    "dns_error_type": dns_error_type,
                    "dns_error_message": dns_error_message,
                    "tcp_ok": tcp_ok,
                    "tcp_latency_ms": tcp_latency_ms,
                    "tcp_error_type": tcp_error_type,
                    "tcp_error_message": tcp_error_message,
                    "tcp_error_errno": tcp_error_errno,
                    "tcp_error_is_eacces": tcp_error_errno == errno.EACCES if tcp_error_errno is not None else None,
                    **self._proxy_flags(),
                }
            },
        )

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

    @staticmethod
    def _resolve_credit_usage(response: dict[str, Any]) -> tuple[int, bool]:
        usage = response.get("usage")
        if isinstance(usage, dict):
            for key in ("credits", "credits_used", "api_credits"):
                value = usage.get(key)
                if (
                    not isinstance(value, bool)
                    and isinstance(value, (int, float))
                    and math.isfinite(float(value))
                    and value >= 0
                ):
                    return math.ceil(value), False
        return TAVILY_CREDITS_PER_ADVANCED_SEARCH, True

    @staticmethod
    def _resolve_credits_used(response: dict[str, Any]) -> int:
        """Backward-compatible credit count helper used by diagnostics/tests."""
        return TavilyResearchClient._resolve_credit_usage(response)[0]

    # Tavily rejects queries longer than this with BadRequestError.
    _TAVILY_MAX_QUERY_CHARS = 400

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
        return self.search_with_usage(
            query,
            max_results=max_results,
            search_depth=search_depth,
        ).sources

    def search_with_usage(
        self, query: str, max_results: int = 5, search_depth: str = "advanced"
    ) -> ProviderSearchResponse:
        """Search once and return sources with provider credit usage."""
        # Truncate before sending to avoid a guaranteed BadRequestError for
        # queries that exceed Tavily's 400-character hard limit.
        original_length = len(str(query or ""))
        if original_length > self._TAVILY_MAX_QUERY_CHARS:
            query = query[: self._TAVILY_MAX_QUERY_CHARS]
            logger.debug(
                "Tavily query truncated to %d chars (was %d)",
                self._TAVILY_MAX_QUERY_CHARS,
                original_length,
                extra={
                    "extra_fields": {
                        "event": "research.query.truncated",
                        "provider": "tavily",
                        "original_length": original_length,
                        "truncated_length": self._TAVILY_MAX_QUERY_CHARS,
                    }
                },
            )

        query_hash = self._query_hash(query)
        query_length = len(str(query or ""))
        resolution = resolve_tavily_search_options(
            query,
            max_results=max_results,
            search_depth=search_depth,
        )
        started = time.perf_counter()
        logger.info(
            "Tavily search options resolved",
            extra={
                "extra_fields": {
                    "event": "research.search.resolver",
                    "provider": "tavily",
                    "query_hash": query_hash,
                    "query_length": query_length,
                    **resolution.log_fields,
                }
            },
        )
        logger.info(
            "Tavily search started",
            extra={
                "extra_fields": {
                    "event": "research.search.start",
                    "provider": "tavily",
                    "query_hash": query_hash,
                    "query_length": query_length,
                    "max_results": int(resolution.params["max_results"]),
                    "search_depth": str(resolution.params["search_depth"]),
                    "chunks_per_source": int(resolution.params["chunks_per_source"]),
                    "auto_parameters": bool(resolution.params["auto_parameters"]),
                    **resolution.log_fields,
                    **self._network_diag_snapshot(),
                }
            },
        )

        try:
            response = self.client.search(
                query=query,
                **resolution.params,
            )

            request_timestamp = self._utc_now_iso()
            sources: list[SourceDoc] = []

            raw_results = response.get("results", []) or []
            for idx, result in enumerate(raw_results, start=1):
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
                logger.debug(
                    "Tavily source candidate",
                    extra={
                        "extra_fields": {
                            "event": "research.search.source",
                            "provider": "tavily",
                            "query_hash": query_hash,
                            "source_index": idx,
                            "score": float(relevance_score),
                            "title_length": len(str(source.title or "")),
                        }
                    },
                )

            provider_credits_used, provider_credits_estimated = self._resolve_credit_usage(response)
            latency_ms = int((time.perf_counter() - started) * 1000)
            source_content_lengths = [len(str(source.excerpt or "")) for source in sources]
            logger.info(
                "Tavily search completed",
                extra={
                    "extra_fields": {
                        "event": "research.search.success",
                        "provider": "tavily",
                        "query_hash": query_hash,
                        "query_length": query_length,
                        "result_count": len(sources),
                        "raw_result_count": len(raw_results),
                        "source_content_lengths": source_content_lengths,
                        "credits_used": provider_credits_used,
                        "credits_estimated": provider_credits_estimated,
                        "latency_ms": latency_ms,
                        "max_results": int(resolution.params["max_results"]),
                        "search_depth": str(resolution.params["search_depth"]),
                        "chunks_per_source": int(resolution.params["chunks_per_source"]),
                        "auto_parameters": bool(resolution.params["auto_parameters"]),
                        **resolution.log_fields,
                        **self._network_diag_snapshot(),
                    }
                },
            )
            return ProviderSearchResponse(
                sources=sources,
                provider_credits_used=provider_credits_used,
                provider_credits_estimated=provider_credits_estimated,
            )

        except Exception as exc:
            self._maybe_emit_network_diagnostics(trigger="search_failure")
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "Tavily search failed",
                extra={
                    "extra_fields": {
                        "event": "research.search.failure",
                        "provider": "tavily",
                        "query_hash": query_hash,
                        "query_length": query_length,
                        "max_results": int(resolution.params["max_results"]),
                        "search_depth": str(resolution.params["search_depth"]),
                        "chunks_per_source": int(resolution.params["chunks_per_source"]),
                        "auto_parameters": bool(resolution.params["auto_parameters"]),
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                        "error_kind": self._classify_error_kind(exc),
                        "error_message": self._error_message_excerpt(exc),
                        "error_chain_types": self._exception_chain_types(exc),
                        **resolution.log_fields,
                        "diagnostic_host": str(
                            getattr(self, "_diagnostic_host", self._DEFAULT_DIAGNOSTIC_HOST)
                        ),
                        "diagnostic_port": int(
                            getattr(self, "_diagnostic_port", self._DEFAULT_DIAGNOSTIC_PORT)
                        ),
                        **self._network_diag_snapshot(),
                        **self._proxy_flags(),
                    }
                },
            )
            return []

    def qna_search(self, query: str) -> tuple[str, list[SourceDoc]]:
        """
        Get direct answer + sources from Tavily.

        Args:
            query: Search query

        Returns:
            Tuple of (answer, sources)
        """
        query_hash = self._query_hash(query)
        query_length = len(str(query or ""))
        started = time.perf_counter()
        logger.info(
            "Tavily QnA started",
            extra={
                "extra_fields": {
                    "event": "research.qna.start",
                    "provider": "tavily",
                    "query_hash": query_hash,
                    "query_length": query_length,
                    **self._network_diag_snapshot(),
                }
            },
        )

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

            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.info(
                "Tavily QnA completed",
                extra={
                    "extra_fields": {
                        "event": "research.qna.success",
                        "provider": "tavily",
                        "query_hash": query_hash,
                        "query_length": query_length,
                        "result_count": len(sources),
                        "answer_length": len(answer),
                        "latency_ms": latency_ms,
                        **self._network_diag_snapshot(),
                    }
                },
            )
            return answer, sources

        except Exception as exc:
            self._maybe_emit_network_diagnostics(trigger="qna_failure")
            latency_ms = int((time.perf_counter() - started) * 1000)
            logger.exception(
                "Tavily QnA failed",
                extra={
                    "extra_fields": {
                        "event": "research.qna.failure",
                        "provider": "tavily",
                        "query_hash": query_hash,
                        "query_length": query_length,
                        "latency_ms": latency_ms,
                        "error_type": type(exc).__name__,
                        "error_kind": self._classify_error_kind(exc),
                        "error_message": self._error_message_excerpt(exc),
                        "error_chain_types": self._exception_chain_types(exc),
                        "diagnostic_host": str(
                            getattr(self, "_diagnostic_host", self._DEFAULT_DIAGNOSTIC_HOST)
                        ),
                        "diagnostic_port": int(
                            getattr(self, "_diagnostic_port", self._DEFAULT_DIAGNOSTIC_PORT)
                        ),
                        **self._network_diag_snapshot(),
                        **self._proxy_flags(),
                    }
                },
            )
            return "", []
