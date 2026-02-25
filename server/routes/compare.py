"""Compare endpoint for multi-model requests."""

import asyncio
import json
import uuid
from dataclasses import replace
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse

from models.unified_response import NormalizedError, TokenUsage, UnifiedResponse
from models.user_context import UserContext
from orchestrator.core import CortexOrchestrator
from server import persistence as persistence_service
from server.dependencies import get_api_key, get_orchestrator
from server.schemas.requests import CompareRequest
from server.schemas.responses import ChatResponseDTO, CompareResponseDTO
from server.utils import clamp_max_tokens, validate_and_trim_context
from utils.logger import get_logger
from utils.web_research import maybe_enrich_prompt_with_web

router = APIRouter(prefix="/v1", tags=["Compare"])

MAX_COMPARE_TARGETS = 4
STREAM_LINE_DELAY_S = 0.1

API_DB_ENABLED = persistence_service.API_DB_ENABLED
ApiKeyPersistenceResolution = persistence_service.ApiKeyPersistenceResolution

logger = get_logger(__name__)

_resolve_and_enforce_caps = persistence_service.resolve_and_enforce_usage_caps
_persist_compare_interaction = persistence_service.persist_compare_interaction
_resolve_runtime_byok_provider_keys = persistence_service.resolve_runtime_byok_provider_keys


def _resolve_compare_research_mode(request: CompareRequest) -> bool:
    """
    Compare mode always uses explicit targets; ignore smart_mode flags completely.
    """
    routing = request.routing
    if not routing:
        return False

    if bool(getattr(routing, "smart_mode", False)):
        logger.debug("Compare mode ignores routing.smart_mode=true and uses explicit targets only")
        try:
            routing.smart_mode = False
        except Exception:
            pass

    return bool(routing.research_mode)


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
        conversation_history=history,
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


def _with_web_sources_metadata(response: UnifiedResponse, research_meta: dict | None) -> UnifiedResponse:
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


def _make_error_response(
    provider: str,
    model: str,
    *,
    code: str,
    message: str,
    retryable: bool = False,
    details: dict | None = None,
) -> UnifiedResponse:
    """Create a normalized error response without raising exceptions."""
    return UnifiedResponse(
        request_id=str(uuid.uuid4()),
        text="",
        provider=provider or "unknown",
        model=model or "unknown",
        latency_ms=0,
        token_usage=TokenUsage(0, 0, 0),
        estimated_cost=0.0,
        finish_reason="error",
        error=NormalizedError(
            code=code,
            message=message,
            provider=provider or "unknown",
            retryable=retryable,
            details=details or {},
        ),
    )


async def _run_compare_target(
    *,
    index: int,
    prompt: str,
    provider: str,
    model: str,
    context: UserContext | None,
    orchestrator: CortexOrchestrator,
    timeout_s: float | None,
    research_mode: str,
    kwargs: dict,
):
    """Run one compare target and capture timeout as UnifiedResponse."""
    ask_coro = asyncio.to_thread(
        orchestrator.ask,
        prompt=prompt,
        model_type=provider,
        context=context,
        model_name=model,
        token_tracker=None,
        research_mode=research_mode,
        **kwargs,
    )

    try:
        response = await asyncio.wait_for(ask_coro, timeout=timeout_s) if timeout_s else await ask_coro
        return index, response
    except asyncio.TimeoutError:
        timeout_msg = f"Request timed out after {timeout_s}s"
        return index, _make_error_response(
            provider=provider,
            model=model,
            code="timeout",
            message=timeout_msg,
            retryable=True,
            details={"timeout_seconds": timeout_s},
        )

@router.post("/compare", response_model=CompareResponseDTO)
async def compare(
    request: CompareRequest,
    http_request: Request,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key),
):
    """Send a prompt to multiple AI models and compare responses."""
    if len(request.targets) > MAX_COMPARE_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_COMPARE_TARGETS} targets allowed",
        )

    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    force_new_session = bool(request.context and request.context.new_session)
    research_mode = _resolve_compare_research_mode(request)
    orchestrator_research_mode = "on" if research_mode else "off"
    effective_prompt, _research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )

    persistence_resolution: ApiKeyPersistenceResolution | None = None
    provider_api_keys: dict[str, str] = {}
    if API_DB_ENABLED:
        req_id = str(getattr(http_request.state, "request_id", "") or uuid.uuid4())
        persistence_resolution = _resolve_and_enforce_caps(api_key=api_key, request_id=req_id)
        providers = [(target.provider or "").strip().lower() for target in request.targets]
        provider_api_keys = _resolve_runtime_byok_provider_keys(
            resolution=persistence_resolution,
            providers=providers,
        )

    models_list = [{"provider": t.provider, "model": t.model or ""} for t in request.targets]

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)
    if provider_api_keys:
        kwargs["provider_api_keys"] = provider_api_keys

    response = await asyncio.to_thread(
        orchestrator.compare,
        prompt=effective_prompt,
        models_list=models_list,
        context=context,
        timeout_s=request.timeout_s,
        token_tracker=None,
        research_mode=orchestrator_research_mode,
        **kwargs,
    )

    dto = CompareResponseDTO.from_multi_unified_response(response)

    if API_DB_ENABLED and persistence_resolution is not None:
        try:
            persistable = [
                _with_web_sources_metadata(r, _research_meta)
                for r in response.responses
                if r is not None
            ]
            _persist_compare_interaction(
                api_key=api_key,
                resolution=persistence_resolution,
                prompt=request.prompt,
                responses=persistable,
                request_group_id=dto.request_group_id,
                requested_session_id=request.context.session_id if request.context else None,
                research_mode=research_mode,
                force_new_session=force_new_session,
            )
        except Exception:
            logger.exception("Compare persistence failed in DB mode")

    return dto


@router.post("/compare/stream")
async def compare_stream(
    request: CompareRequest,
    http_request: Request,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key),
):
    """Stream compare responses as NDJSON events, then emit aggregate summary."""
    if len(request.targets) > MAX_COMPARE_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_COMPARE_TARGETS} targets allowed",
        )

    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    force_new_session = bool(request.context and request.context.new_session)
    research_mode = _resolve_compare_research_mode(request)
    orchestrator_research_mode = "on" if research_mode else "off"
    effective_prompt, research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )

    persistence_resolution: ApiKeyPersistenceResolution | None = None
    provider_api_keys: dict[str, str] = {}
    if API_DB_ENABLED:
        req_id = str(getattr(http_request.state, "request_id", "") or uuid.uuid4())
        persistence_resolution = _resolve_and_enforce_caps(api_key=api_key, request_id=req_id)
        providers = [(target.provider or "").strip().lower() for target in request.targets]
        provider_api_keys = _resolve_runtime_byok_provider_keys(
            resolution=persistence_resolution,
            providers=providers,
        )

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)
    if provider_api_keys:
        kwargs["provider_api_keys"] = provider_api_keys

    request_group_id = str(uuid.uuid4())

    async def event_stream():
        yield _to_ndjson(
            {
                "type": "start",
                "mode": "compare",
                "target_count": len(request.targets),
                "research_mode": research_mode,
                "web_sources": research_meta.get("source_count", 0),
                "web_source_items": research_meta.get("sources", []),
            }
        )

        ordered_responses: list[UnifiedResponse | None] = [None] * len(request.targets)
        try:
            tasks = []

            for i, target in enumerate(request.targets):
                provider = (target.provider or "").strip().lower()
                model = (target.model or "").strip()

                if not provider or not model:
                    bad = _make_error_response(
                        provider=provider or "unknown",
                        model=model or "unknown",
                        code="bad_request",
                        message=f"Invalid model config: provider='{provider}', model='{model}'",
                        retryable=False,
                    )
                    ordered_responses[i] = bad
                    bad_dto = ChatResponseDTO.from_unified_response(bad)

                    yield _to_ndjson(
                        {
                            "type": "response_start",
                            "index": i,
                            "provider": bad_dto.provider,
                            "model": bad_dto.model,
                        }
                    )
                    stream_text = f"Error: {bad_dto.error.message}" if bad_dto.error else ""
                    for line in _iter_stream_lines(stream_text):
                        yield _to_ndjson({"type": "line", "index": i, "text": line})
                        await asyncio.sleep(STREAM_LINE_DELAY_S)
                    yield _to_ndjson(
                        {
                            "type": "response_done",
                            "index": i,
                            "response": jsonable_encoder(bad_dto),
                        }
                    )
                    continue

                tasks.append(
                    asyncio.create_task(
                        _run_compare_target(
                            index=i,
                            prompt=effective_prompt,
                            provider=provider,
                            model=model,
                            context=context,
                            orchestrator=orchestrator,
                            timeout_s=request.timeout_s,
                            research_mode=orchestrator_research_mode,
                            kwargs=kwargs,
                        )
                    )
                )

            for task in asyncio.as_completed(tasks):
                idx, response = await task
                response = _with_web_sources_metadata(response, research_meta)
                ordered_responses[idx] = response
                dto = ChatResponseDTO.from_unified_response(response)

                yield _to_ndjson(
                    {
                        "type": "response_start",
                        "index": idx,
                        "provider": dto.provider,
                        "model": dto.model,
                    }
                )

                stream_text = dto.text or ""
                if not stream_text and dto.error:
                    stream_text = f"Error: {dto.error.message}"
                for line in _iter_stream_lines(stream_text):
                    yield _to_ndjson({"type": "line", "index": idx, "text": line})
                    await asyncio.sleep(STREAM_LINE_DELAY_S)

                yield _to_ndjson(
                    {
                        "type": "response_done",
                        "index": idx,
                        "response": jsonable_encoder(dto),
                    }
                )

            raw_responses = [r for r in ordered_responses if r is not None]
            dtos = [ChatResponseDTO.from_unified_response(r) for r in raw_responses]

            compare_payload = {
                "request_group_id": request_group_id,
                "responses": [jsonable_encoder(r) for r in dtos],
                "success_count": sum(1 for r in dtos if r.error is None),
                "error_count": sum(1 for r in dtos if r.error is not None),
                "total_tokens": sum(r.token_usage.total_tokens for r in dtos),
                "total_cost": sum(r.estimated_cost for r in dtos),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }

            yield _to_ndjson({"type": "done", "mode": "compare", "compare": compare_payload})

            if API_DB_ENABLED and persistence_resolution is not None:
                try:
                    _persist_compare_interaction(
                        api_key=api_key,
                        resolution=persistence_resolution,
                        prompt=request.prompt,
                        responses=raw_responses,
                        request_group_id=request_group_id,
                        requested_session_id=request.context.session_id if request.context else None,
                        research_mode=research_mode,
                        force_new_session=force_new_session,
                    )
                except Exception:
                    logger.exception("Compare stream persistence failed in DB mode")

        except Exception as exc:
            if API_DB_ENABLED and persistence_resolution is not None:
                try:
                    partial_responses = [r for r in ordered_responses if r is not None]
                    if not partial_responses:
                        fallback_error = persistence_service.build_error_response(
                                provider="unknown",
                                model="unknown",
                                message=str(exc),
                                code="provider_error",
                                retryable=True,
                            )
                        partial_responses = [_with_web_sources_metadata(fallback_error, research_meta)]
                    _persist_compare_interaction(
                        api_key=api_key,
                        resolution=persistence_resolution,
                        prompt=request.prompt,
                        responses=partial_responses,
                        request_group_id=request_group_id,
                        requested_session_id=request.context.session_id if request.context else None,
                        research_mode=research_mode,
                        force_new_session=force_new_session,
                    )
                except Exception:
                    logger.exception("Compare stream error persistence failed in DB mode")
            yield _to_ndjson({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
