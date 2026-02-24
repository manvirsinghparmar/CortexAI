"""Compare endpoint for multi-model requests."""

import asyncio
import json
import uuid
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

_resolve_api_key_for_request = persistence_service.resolve_api_key_for_request
_enforce_usage_caps = persistence_service.enforce_usage_caps
_resolve_and_enforce_caps = persistence_service.resolve_and_enforce_usage_caps
_persist_compare_interaction = persistence_service.persist_compare_interaction
_resolve_runtime_byok_provider_keys = persistence_service.resolve_runtime_byok_provider_keys


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

    if request.context and len(request.targets) > 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Context not allowed with more than 2 targets",
        )

    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    research_mode = bool(request.routing and request.routing.research_mode)
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
        **kwargs,
    )

    dto = CompareResponseDTO.from_multi_unified_response(response)

    if API_DB_ENABLED and persistence_resolution is not None:
        try:
            persistable = [r for r in response.responses if r is not None]
            _persist_compare_interaction(
                api_key=api_key,
                resolution=persistence_resolution,
                prompt=request.prompt,
                responses=persistable,
                request_group_id=dto.request_group_id,
                requested_session_id=request.context.session_id if request.context else None,
                research_mode=research_mode,
            )
        except Exception:
            logger.exception("Compare persistence failed in DB mode")
    else:
        # Legacy/local fallback when DATABASE_URL is not configured.
        try:
            from server.database import save_chat

            for r in dto.responses:
                save_chat(
                    prompt=request.prompt,
                    provider=r.provider,
                    model=r.model,
                    response=r.text,
                    latency_ms=r.latency_ms,
                    tokens=r.token_usage.total_tokens if r.token_usage else None,
                    cost=r.estimated_cost,
                    mode="compare",
                )
        except Exception:
            pass

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

    if request.context and len(request.targets) > 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Context not allowed with more than 2 targets",
        )

    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    research_mode = bool(request.routing and request.routing.research_mode)
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
                            kwargs=kwargs,
                        )
                    )
                )

            for task in asyncio.as_completed(tasks):
                idx, response = await task
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
                    )
                except Exception:
                    logger.exception("Compare stream persistence failed in DB mode")
            else:
                # Legacy/local fallback when DATABASE_URL is not configured.
                try:
                    from server.database import save_chat

                    for r in dtos:
                        save_chat(
                            prompt=request.prompt,
                            provider=r.provider,
                            model=r.model,
                            response=r.text,
                            latency_ms=r.latency_ms,
                            tokens=r.token_usage.total_tokens if r.token_usage else None,
                            cost=r.estimated_cost,
                            mode="compare",
                        )
                except Exception:
                    pass

        except Exception as exc:
            if API_DB_ENABLED and persistence_resolution is not None:
                try:
                    partial_responses = [r for r in ordered_responses if r is not None]
                    if not partial_responses:
                        partial_responses = [
                            persistence_service.build_error_response(
                                provider="unknown",
                                model="unknown",
                                message=str(exc),
                                code="provider_error",
                                retryable=True,
                            )
                        ]
                    _persist_compare_interaction(
                        api_key=api_key,
                        resolution=persistence_resolution,
                        prompt=request.prompt,
                        responses=partial_responses,
                        request_group_id=request_group_id,
                        requested_session_id=request.context.session_id if request.context else None,
                        research_mode=research_mode,
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
