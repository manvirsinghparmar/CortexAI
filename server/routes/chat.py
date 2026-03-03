"""Chat endpoint for single AI model requests."""

import asyncio
import json
import os
from dataclasses import dataclass, replace
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from config.provider_catalog import (
    get_provider_default_model_envs,
    get_provider_default_models,
    get_provider_ids,
)
from models.user_context import UserContext
from orchestrator.core import CortexOrchestrator
from server.dependencies import get_api_key, get_orchestrator
from server import persistence as persistence_service
from server.schemas.requests import ChatRequest
from server.schemas.responses import ChatResponseDTO
from server.utils import clamp_max_tokens, validate_and_trim_context
from utils.logger import get_logger
from utils.web_research import maybe_enrich_prompt_with_web

router = APIRouter(prefix="/v1", tags=["Chat"])
STREAM_LINE_DELAY_S = 0.1
API_DB_ENABLED = persistence_service.API_DB_ENABLED

logger = get_logger(__name__)

DEFAULT_MODELS = get_provider_default_models()
DEFAULT_MODEL_ENVS = get_provider_default_model_envs()
SUPPORTED_PROVIDERS = tuple(DEFAULT_MODELS.keys())
SMART_ROUTING_MODE = "smart"
LEGACY_ROUTING_MODE = "legacy"
TRUE_SMART_ROUTING_ENABLED = os.getenv(
    "ENABLE_TRUE_SMART_CHAT_ROUTING", "true"
).strip().lower() in {"1", "true", "yes", "on"}

ApiKeyPersistenceResolution = persistence_service.ApiKeyPersistenceResolution
_resolve_and_enforce_caps = persistence_service.resolve_and_enforce_usage_caps
_persist_chat_interaction = persistence_service.persist_chat_interaction
_resolve_runtime_byok_provider_keys = persistence_service.resolve_runtime_byok_provider_keys


@dataclass(frozen=True)
class ChatExecutionPlan:
    strategy: str
    model_type: str | None
    model_name: str | None
    routing_mode: str
    routing_constraints: dict[str, Any] | None
    preview_provider: str
    preview_model: str


def _default_model_for_provider(provider: str) -> str:
    env_key = DEFAULT_MODEL_ENVS.get(provider)
    default_model = DEFAULT_MODELS[provider]
    if not env_key:
        return default_model
    return os.getenv(env_key, default_model)


def _first_supported_provider(
    candidates: list[str] | tuple[str, ...],
    *,
    fallback: str | None = None,
) -> str:
    for candidate in candidates:
        provider = _normalize_provider(candidate)
        if provider:
            return provider

    if fallback:
        provider = _normalize_provider(fallback)
        if provider:
            return provider

    return SUPPORTED_PROVIDERS[0]


def _parse_float_env(name: str) -> float | None:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return None
    try:
        value = float(raw)
    except Exception:
        logger.warning("Ignoring invalid %s value: %s", name, raw)
        return None
    if value <= 0:
        logger.warning("Ignoring non-positive %s value: %s", name, raw)
        return None
    return value


def _parse_int_env(name: str) -> int | None:
    raw = str(os.getenv(name, "") or "").strip()
    if not raw:
        return None
    try:
        value = int(raw)
    except Exception:
        logger.warning("Ignoring invalid %s value: %s", name, raw)
        return None
    if value <= 0:
        logger.warning("Ignoring non-positive %s value: %s", name, raw)
        return None
    return value


def _normalize_provider(provider: str | None) -> str | None:
    value = str(provider or "").strip().lower()
    if value in SUPPORTED_PROVIDERS:
        return value
    return None


def _normalize_provider_list(values: list[str] | tuple[str, ...] | None) -> list[str]:
    if not values:
        return []
    normalized: list[str] = []
    for item in values:
        provider = _normalize_provider(item)
        if provider and provider not in normalized:
            normalized.append(provider)
    return normalized


def _build_chat_routing_constraints() -> dict[str, Any] | None:
    constraints: dict[str, Any] = {}

    max_cost_usd = _parse_float_env("SMART_CHAT_MAX_COST_USD")
    if max_cost_usd is not None:
        constraints["max_cost_usd"] = max_cost_usd

    max_total_latency_ms = _parse_int_env("SMART_CHAT_MAX_TOTAL_LATENCY_MS")
    if max_total_latency_ms is not None:
        constraints["max_total_latency_ms"] = max_total_latency_ms

    min_context_limit = _parse_int_env("SMART_CHAT_MIN_CONTEXT_LIMIT")
    if min_context_limit is not None:
        constraints["min_context_limit"] = min_context_limit

    preferred_provider = _normalize_provider(os.getenv("SMART_CHAT_PREFERRED_PROVIDER"))
    if preferred_provider:
        constraints["preferred_provider"] = preferred_provider

    allowed_raw = str(os.getenv("SMART_CHAT_ALLOWED_PROVIDERS", "") or "").strip()
    if allowed_raw:
        allowed = _normalize_provider_list([part.strip() for part in allowed_raw.split(",")])
        if allowed:
            constraints["allowed_providers"] = allowed

    return constraints or None


def _pick_smart_provider(prompt: str, *, smart_mode: bool, research_mode: bool) -> str:
    text = (prompt or "").lower()
    default_provider = _first_supported_provider(get_provider_ids(), fallback="openai")

    if not smart_mode:
        return _first_supported_provider(("gemini",), fallback=default_provider)

    if research_mode:
        return _first_supported_provider(("openai",), fallback=default_provider)

    code_signals = (
        "code", "bug", "debug", "stack trace", "python", "javascript", "typescript",
        "sql", "api", "refactor", "algorithm", "function", "class ", "exception",
    )
    deep_reasoning_signals = (
        "analyze", "analysis", "tradeoff", "architecture", "design", "compare",
        "step by step", "explain why", "root cause", "research", "cite",
    )
    creative_signals = ("poem", "story", "creative", "brainstorm", "tagline", "tweet")

    if any(signal in text for signal in code_signals):
        return _first_supported_provider(("deepseek", "claude", "openai"), fallback=default_provider)
    if any(signal in text for signal in deep_reasoning_signals) or len(text) > 900:
        return _first_supported_provider(("openai", "claude"), fallback=default_provider)
    if any(signal in text for signal in creative_signals):
        return _first_supported_provider(("grok", "gemini", "claude"), fallback=default_provider)
    return _first_supported_provider(("gemini", "claude"), fallback=default_provider)


def _resolve_chat_execution_plan(
    request: ChatRequest,
    *,
    effective_prompt: str,
    context: UserContext | None,
    orchestrator: CortexOrchestrator,
) -> ChatExecutionPlan:
    manual_provider = (request.provider or "").strip().lower()
    manual_model = (request.model or "").strip()
    normalized_manual_provider = _normalize_provider(manual_provider)

    if normalized_manual_provider:
        chosen_model = manual_model or _default_model_for_provider(normalized_manual_provider)
        return ChatExecutionPlan(
            strategy="explicit_manual",
            model_type=normalized_manual_provider,
            model_name=chosen_model,
            routing_mode=LEGACY_ROUTING_MODE,
            routing_constraints=None,
            preview_provider=normalized_manual_provider,
            preview_model=chosen_model,
        )

    routing = request.routing
    smart_mode = True if routing is None else bool(routing.smart_mode)
    research_mode = False if routing is None else bool(routing.research_mode)

    if TRUE_SMART_ROUTING_ENABLED and smart_mode:
        constraints = _build_chat_routing_constraints()
        preview = None
        preview_fn = getattr(orchestrator, "preview_smart_target", None)
        if callable(preview_fn):
            preview = preview_fn(
                prompt=effective_prompt,
                context=context,
                routing_mode=SMART_ROUTING_MODE,
                routing_constraints=constraints,
            )

        preview_provider: str | None = None
        preview_model: str | None = None
        if isinstance(preview, tuple) and len(preview) == 2:
            pp = _normalize_provider(preview[0])
            pm = str(preview[1] or "").strip()
            if pp and pm:
                preview_provider, preview_model = pp, pm

        if not preview_provider or not preview_model:
            fallback_provider = _pick_smart_provider(
                request.prompt,
                smart_mode=True,
                research_mode=research_mode,
            )
            preview_provider = fallback_provider
            preview_model = _default_model_for_provider(fallback_provider)

        return ChatExecutionPlan(
            strategy="smart_orchestrator",
            model_type=None,
            model_name=None,
            routing_mode=SMART_ROUTING_MODE,
            routing_constraints=constraints,
            preview_provider=preview_provider,
            preview_model=preview_model,
        )

    provider = _pick_smart_provider(
        request.prompt,
        smart_mode=smart_mode,
        research_mode=research_mode,
    )
    model = _default_model_for_provider(provider)
    return ChatExecutionPlan(
        strategy="legacy_auto",
        model_type=provider,
        model_name=model,
        routing_mode=LEGACY_ROUTING_MODE,
        routing_constraints=None,
        preview_provider=provider,
        preview_model=model,
    )


def _providers_for_runtime_keys(plan: ChatExecutionPlan) -> list[str]:
    if plan.strategy != "smart_orchestrator":
        return [plan.preview_provider]

    constraints = plan.routing_constraints or {}
    allowed = constraints.get("allowed_providers") or constraints.get("allow_providers")
    normalized_allowed = _normalize_provider_list(
        allowed if isinstance(allowed, (list, tuple)) else None
    )
    if normalized_allowed:
        return normalized_allowed
    return list(SUPPORTED_PROVIDERS)


def _build_user_context(context_req):
    """Convert request context to UserContext dataclass."""
    if not context_req:
        return None

    history = []
    if context_req.conversation_history:
        history = [
            {"role": item.role, "content": item.content}
            for item in context_req.conversation_history
        ]

    return UserContext(
        session_id=context_req.session_id,
        conversation_history=history
    )


def _iter_stream_lines(text: str):
    """Split response text into line chunks while preserving newline boundaries."""
    if not text:
        return []
    lines = text.splitlines(keepends=True)
    if len(lines) <= 1:
        # If the model returns one long paragraph, chunk it for smoother streaming.
        chunk_size = 120
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    return lines


def _to_ndjson(event: dict) -> str:
    """Serialize one stream event as NDJSON."""
    return json.dumps(event, ensure_ascii=False) + "\n"


def _normalize_web_source_items(raw_items: object) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    seen_urls: set[str] = set()
    if not isinstance(raw_items, list):
        return items

    for item in raw_items:
        if not isinstance(item, dict):
            continue
        url = str(item.get("url") or "").strip()
        if not url:
            continue
        normalized_url = url.lower()
        if normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        title = str(item.get("title") or "").strip() or url
        items.append({"title": title, "url": url})
        if len(items) >= 8:
            break

    return items


def _with_web_sources_metadata(response, research_meta: dict | None):
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    existing_sources = metadata.get("web_source_items")
    if not isinstance(existing_sources, list):
        existing_sources = metadata.get("sources")

    normalized_sources = _normalize_web_source_items(existing_sources)
    if not normalized_sources and isinstance(research_meta, dict):
        normalized_sources = _normalize_web_source_items(research_meta.get("sources"))
    if not normalized_sources:
        return response

    updated_metadata = dict(metadata)
    updated_metadata["web_source_items"] = normalized_sources
    updated_metadata.setdefault("sources", normalized_sources)
    updated_metadata["web_sources"] = len(normalized_sources)
    return replace(response, metadata=updated_metadata)


@router.post("/chat", response_model=ChatResponseDTO)
async def chat(
    request: ChatRequest,
    http_request: Request,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key),
):
    """Send a prompt to a single AI model and get a response."""
    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    force_new_session = bool(request.context and request.context.new_session)
    routing = request.routing
    research_mode = bool(routing and routing.research_mode)
    orchestrator_research_mode = "on" if research_mode else "off"
    effective_prompt, _research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )
    execution_plan = _resolve_chat_execution_plan(
        request,
        effective_prompt=effective_prompt,
        context=context,
        orchestrator=orchestrator,
    )

    persistence_resolution: ApiKeyPersistenceResolution | None = None
    provider_api_keys: dict[str, str] = {}
    if API_DB_ENABLED:
        req_id = str(getattr(http_request.state, "request_id", "") or uuid4())
        persistence_resolution = _resolve_and_enforce_caps(api_key=api_key, request_id=req_id)
        runtime_providers = _providers_for_runtime_keys(execution_plan)
        provider_api_keys = _resolve_runtime_byok_provider_keys(
            resolution=persistence_resolution,
            providers=runtime_providers,
        )

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)
    if provider_api_keys:
        kwargs["provider_api_keys"] = provider_api_keys

    response = await asyncio.to_thread(
        orchestrator.ask,
        prompt=effective_prompt,
        model_type=execution_plan.model_type,
        context=context,
        model_name=execution_plan.model_name,
        token_tracker=None,
        research_mode=orchestrator_research_mode,
        routing_mode=execution_plan.routing_mode,
        routing_constraints=execution_plan.routing_constraints,
        **kwargs,
    )
    response = _with_web_sources_metadata(response, _research_meta)

    dto = ChatResponseDTO.from_unified_response(response)

    if API_DB_ENABLED and persistence_resolution is not None:
        try:
            _persist_chat_interaction(
                api_key=api_key,
                resolution=persistence_resolution,
                prompt=request.prompt,
                response=response,
                requested_session_id=request.context.session_id if request.context else None,
                research_mode=research_mode,
                force_new_session=force_new_session,
            )
        except Exception:
            logger.exception("Chat persistence failed in DB mode")

    return dto


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key),
):
    """Stream a single-model chat response as NDJSON events."""
    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    force_new_session = bool(request.context and request.context.new_session)
    routing = request.routing
    research_mode = bool(routing and routing.research_mode)
    orchestrator_research_mode = "on" if research_mode else "off"
    effective_prompt, research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )
    execution_plan = _resolve_chat_execution_plan(
        request,
        effective_prompt=effective_prompt,
        context=context,
        orchestrator=orchestrator,
    )
    target_provider = execution_plan.preview_provider
    target_model = execution_plan.preview_model

    persistence_resolution: ApiKeyPersistenceResolution | None = None
    provider_api_keys: dict[str, str] = {}
    if API_DB_ENABLED:
        req_id = str(getattr(http_request.state, "request_id", "") or uuid4())
        persistence_resolution = _resolve_and_enforce_caps(api_key=api_key, request_id=req_id)
        runtime_providers = _providers_for_runtime_keys(execution_plan)
        provider_api_keys = _resolve_runtime_byok_provider_keys(
            resolution=persistence_resolution,
            providers=runtime_providers,
        )

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)
    if provider_api_keys:
        kwargs["provider_api_keys"] = provider_api_keys

    async def event_stream():
        yield _to_ndjson(
            {
                "type": "start",
                "mode": "chat",
                "provider": target_provider,
                "model": target_model,
                "research_mode": research_mode,
                "web_sources": research_meta.get("source_count", 0),
                "web_source_items": research_meta.get("sources", []),
            }
        )

        try:
            response = await asyncio.to_thread(
                orchestrator.ask,
                prompt=effective_prompt,
                model_type=execution_plan.model_type,
                context=context,
                model_name=execution_plan.model_name,
                token_tracker=None,
                research_mode=orchestrator_research_mode,
                routing_mode=execution_plan.routing_mode,
                routing_constraints=execution_plan.routing_constraints,
                **kwargs,
            )
            response = _with_web_sources_metadata(response, research_meta)

            dto = ChatResponseDTO.from_unified_response(response)
            stream_text = dto.text or ""
            if not stream_text and dto.error:
                stream_text = f"Error: {dto.error.message}"

            for line in _iter_stream_lines(stream_text):
                yield _to_ndjson({"type": "line", "index": 0, "text": line})
                await asyncio.sleep(STREAM_LINE_DELAY_S)

            yield _to_ndjson(
                {
                    "type": "response_done",
                    "index": 0,
                    "response": jsonable_encoder(dto),
                }
            )
            yield _to_ndjson({"type": "done", "mode": "chat"})

            if API_DB_ENABLED and persistence_resolution is not None:
                try:
                    _persist_chat_interaction(
                        api_key=api_key,
                        resolution=persistence_resolution,
                        prompt=request.prompt,
                        response=response,
                        requested_session_id=request.context.session_id if request.context else None,
                        research_mode=research_mode,
                        force_new_session=force_new_session,
                    )
                except Exception:
                    logger.exception("Chat stream persistence failed in DB mode")

        except Exception as exc:
            if API_DB_ENABLED and persistence_resolution is not None:
                try:
                    error_response = persistence_service.build_error_response(
                        provider=target_provider,
                        model=target_model,
                        message=str(exc),
                        code="provider_error",
                        retryable=True,
                    )
                    error_response = _with_web_sources_metadata(error_response, research_meta)
                    _persist_chat_interaction(
                        api_key=api_key,
                        resolution=persistence_resolution,
                        prompt=request.prompt,
                        response=error_response,
                        requested_session_id=request.context.session_id if request.context else None,
                        research_mode=research_mode,
                        force_new_session=force_new_session,
                    )
                except Exception:
                    logger.exception("Chat stream error persistence failed in DB mode")
            yield _to_ndjson({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
