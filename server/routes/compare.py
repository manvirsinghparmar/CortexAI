"""Compare endpoint for multi-model requests."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Tuple
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from orchestrator.core import CortexOrchestrator
from models.unified_response import UnifiedResponse, TokenUsage, NormalizedError
from models.user_context import UserContext
from orchestrator.core import CortexOrchestrator
from server.dependencies import get_api_key, get_orchestrator
from server.schemas.requests import CompareRequest
from server.schemas.responses import ChatResponseDTO, CompareResponseDTO
from server.dependencies import get_api_key, get_orchestrator
from server.utils import validate_and_trim_context, clamp_max_tokens
from utils.web_research import maybe_enrich_prompt_with_web

router = APIRouter(prefix="/v1", tags=["Compare"])

MAX_COMPARE_TARGETS = 4
STREAM_LINE_DELAY_S = 0.1


@dataclass(frozen=True)
class ApiKeyPersistenceResolution:
    user_id: UUID
    api_key_id: UUID | None
    decision_path: str


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

    return UserContext(session_id=context_req.session_id, conversation_history=history)


def _extract_routing_payload(response) -> tuple[dict, list[dict], dict]:
    metadata = response.metadata if isinstance(response.metadata, dict) else {}
    routing_metadata = metadata.get("routing", {})
    if not isinstance(routing_metadata, dict):
        return {}, [], {}

    attempts = routing_metadata.get("selected_sequence") or routing_metadata.get("attempts") or []
    if not isinstance(attempts, list):
        attempts = []

    features = routing_metadata.get("features", {})
    if not isinstance(features, dict):
        features = {}

    return routing_metadata, attempts, features


def _safe_uuid(value: str | None) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(value)
    except Exception:
        return None


def _env_flag(name: str, default: str) -> bool:
    return os.getenv(name, default).strip().lower() == "true"


def _resolve_api_key_in_session(
    db_session,
    *,
    api_key: str,
    request_id: str,
    reject_unmapped: bool,
) -> ApiKeyPersistenceResolution | None:
    resolved = get_user_by_api_key(db_session, api_key)
    if resolved:
        user_id, api_key_id = resolved
        return ApiKeyPersistenceResolution(
            user_id=user_id,
            api_key_id=api_key_id,
            decision_path="mapped",
        )

    auto_register = _env_flag("AUTO_REGISTER_UNMAPPED_API_KEYS", AUTO_REGISTER_UNMAPPED_DEFAULT)
    allow_unmapped = _env_flag("ALLOW_UNMAPPED_API_KEY_PERSIST", "false")

    fallback_email = os.getenv("API_KEY_FALLBACK_USER_EMAIL", "api@cortexai.local")
    fallback_name = os.getenv("API_KEY_FALLBACK_USER_NAME", "API Service User")

    if auto_register:
        owner_user_id = get_or_create_service_user(
            db_session,
            email=fallback_email,
            display_name=fallback_name,
        )
        api_key_id, owner_user_id = create_api_key(
            db_session,
            user_id=owner_user_id,
            raw_api_key=api_key,
            label="auto-registered",
        )
        logger.warning(
            "API key auto-registered for compare persistence",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "resolved_user_id": str(owner_user_id),
                    "api_key_id": str(api_key_id),
                    "decision_path": "auto_registered",
                }
            },
        )
        return ApiKeyPersistenceResolution(
            user_id=owner_user_id,
            api_key_id=api_key_id,
            decision_path="auto_registered",
        )

    if allow_unmapped:
        owner_user_id = get_or_create_service_user(
            db_session,
            email=fallback_email,
            display_name=fallback_name,
        )
        logger.warning(
            "Unmapped API key compare persisted under fallback service user (no api_key_id)",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "resolved_user_id": str(owner_user_id),
                    "api_key_id": None,
                    "decision_path": "fallback_user_without_api_key_id",
                }
            },
        )
        return ApiKeyPersistenceResolution(
            user_id=owner_user_id,
            api_key_id=None,
            decision_path="fallback_user_without_api_key_id",
        )

    if reject_unmapped:
        logger.warning(
            "Rejecting compare request: unmapped API key and fallback disabled",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "decision_path": "rejected_unmapped_key",
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "API key is not registered for persistence. "
                "Enable AUTO_REGISTER_UNMAPPED_API_KEYS=true or "
                "ALLOW_UNMAPPED_API_KEY_PERSIST=true for testing overrides."
            ),
        )

    return None


def _resolve_api_key_for_request(*, api_key: str, request_id: str) -> ApiKeyPersistenceResolution | None:
    """
    Resolve API key -> persistence attribution before model invocation.
    """
    if not API_DB_ENABLED:
        return None

    db_gen = None
    db_session = None
    try:
        db_gen = get_db()
        db_session = next(db_gen)

        resolution = _resolve_api_key_in_session(
            db_session,
            api_key=api_key,
            request_id=request_id,
            reject_unmapped=True,
        )
        db_session.commit()
        return resolution
    except HTTPException:
        if db_session is not None:
            db_session.rollback()
        raise
    except Exception as exc:
        if db_session is not None:
            db_session.rollback()
        logger.warning(
            "Compare API key resolution failed",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "error": str(exc),
                    "decision_path": "resolution_error",
                }
            },
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to resolve API key attribution",
        ) from exc
    finally:
        if db_gen is not None:
            db_gen.close()


def _persist_api_compare_interaction(
    *,
    api_key: str,
    prompt: str,
    compare_response,
    request_context,
    research_mode: str,
    resolution: ApiKeyPersistenceResolution | None,
) -> None:
    """
    Persist API compare request/response set and optional routing telemetry.
    Failures are isolated and never affect API response flow.
    """
    if not API_DB_ENABLED:
        return

    db_gen = None
    db_session = None
    request_group_id = _safe_uuid(getattr(compare_response, "request_group_id", None))

    try:
        db_gen = get_db()
        db_session = next(db_gen)

        resolved = resolution
        if resolved is None:
            mapped = get_user_by_api_key(db_session, api_key)
            if not mapped:
                logger.warning(
                    "Skipping compare DB persistence: API key not mapped",
                    extra={
                        "extra_fields": {
                            "request_group_id": str(request_group_id) if request_group_id else None,
                            "decision_path": "unmapped_skip",
                            "persistence_status": "skipped",
                        }
                    },
                )
                return
            resolved = ApiKeyPersistenceResolution(
                user_id=mapped[0],
                api_key_id=mapped[1],
                decision_path="mapped",
            )

        user_id = resolved.user_id
        api_key_id = resolved.api_key_id
        session_id = _safe_uuid(request_context.session_id) if request_context else None

        responses = list(getattr(compare_response, "responses", []) or [])
        persisted_count = 0
        routing_persisted_count = 0

        for resp in responses:
            if resp is None:
                continue

            token_usage = getattr(resp, "token_usage", None)
            llm_request_id = create_llm_request(
                db_session,
                user_id=user_id,
                request_id=getattr(resp, "request_id", "unknown"),
                route_mode="compare",
                provider=getattr(resp, "provider", "unknown"),
                model=getattr(resp, "model", "unknown"),
                prompt=prompt,
                session_id=session_id,
                request_group_id=request_group_id,
                api_key_id=api_key_id,
                input_tokens_est=(
                    getattr(token_usage, "prompt_tokens", None) if token_usage else None
                ),
                store_prompt=False,
            )
            create_llm_response(db_session, llm_request_id, resp)
            persisted_count += 1

            routing_metadata, attempts, features = _extract_routing_payload(resp)
            if routing_metadata:
                metadata = resp.metadata if isinstance(resp.metadata, dict) else {}
                prompt_category = (
                    metadata.get("prompt_category")
                    or routing_metadata.get("prompt_category")
                    or "unknown"
                )
                normalized_research_mode = (
                    metadata.get("research_mode")
                    or routing_metadata.get("research_mode")
                    or research_mode
                    or "off"
                )
                routing_decision_id = create_routing_decision(
                    db_session,
                    llm_request_id,
                    routing_metadata,
                    prompt_category=str(prompt_category),
                    research_mode=str(normalized_research_mode),
                    features=features,
                )
                create_routing_attempts(db_session, routing_decision_id, attempts)
                routing_persisted_count += 1

            upsert_usage_daily(
                db_session,
                user_id=user_id,
                total_tokens=getattr(token_usage, "total_tokens", 0) if token_usage else 0,
                estimated_cost=float(getattr(resp, "estimated_cost", 0.0) or 0.0),
            )

        db_session.commit()
        logger.info(
            "API compare persisted to DB",
            extra={
                "extra_fields": {
                    "request_group_id": str(request_group_id) if request_group_id else None,
                    "resolved_user_id": str(user_id),
                    "api_key_id": str(api_key_id) if api_key_id else None,
                    "decision_path": resolved.decision_path,
                    "persisted_count": persisted_count,
                    "routing_persisted_count": routing_persisted_count,
                    "persistence_status": "success",
                }
            },
        )
    except Exception as exc:
        if db_session is not None:
            db_session.rollback()
        logger.warning(
            "API compare DB persistence failed",
            extra={
                "extra_fields": {
                    "request_group_id": str(request_group_id) if request_group_id else None,
                    "error": str(exc),
                    "decision_path": resolution.decision_path if resolution else "unknown",
                    "persistence_status": "failed",
                }
            },
        )
    finally:
        if db_gen is not None:
            db_gen.close()


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
) -> Tuple[int, UnifiedResponse]:
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

    models_list = [{"provider": t.provider, "model": t.model or ""} for t in request.targets]

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)

    canonical_request_group_id = str(uuid4())

    resolution = None
    if API_DB_ENABLED:
        middleware_request_id = getattr(http_request.state, "request_id", "unknown")
        resolution = await asyncio.to_thread(
            _resolve_api_key_for_request,
            api_key=api_key,
            request_id=middleware_request_id,
        )

    research_mode = request.research_mode or "off"
    response = await asyncio.to_thread(
        orchestrator.compare,
        prompt=effective_prompt,
        models_list=models_list,
        context=context,
        timeout_s=request.timeout_s,
        token_tracker=None,
        research_mode=research_mode,
        request_group_id=canonical_request_group_id,
        **kwargs,
    )

    await asyncio.to_thread(
        _persist_api_compare_interaction,
        api_key=api_key,
        prompt=request.prompt,
        compare_response=response,
        request_context=request.context,
        research_mode=research_mode,
        resolution=resolution,
    )

    dto = CompareResponseDTO.from_multi_unified_response(response)

    # Persist each model's response to history DB (best-effort)
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
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key)
):
    """Stream compare responses as NDJSON events, then emit aggregate summary."""
    if len(request.targets) > MAX_COMPARE_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_COMPARE_TARGETS} targets allowed"
        )

    if request.context and len(request.targets) > 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Context not allowed with more than 2 targets"
        )

    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    research_mode = bool(request.routing and request.routing.research_mode)
    effective_prompt, research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)

    async def event_stream():
        yield _to_ndjson({
            "type": "start",
            "mode": "compare",
            "target_count": len(request.targets),
            "research_mode": research_mode,
            "web_sources": research_meta.get("source_count", 0),
            "web_source_items": research_meta.get("sources", []),
        })

        try:
            ordered_responses = [None] * len(request.targets)
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
                    bad_dto = ChatResponseDTO.from_unified_response(bad)
                    ordered_responses[i] = bad_dto

                    yield _to_ndjson({
                        "type": "response_start",
                        "index": i,
                        "provider": bad_dto.provider,
                        "model": bad_dto.model,
                    })
                    stream_text = f"Error: {bad_dto.error.message}" if bad_dto.error else ""
                    for line in _iter_stream_lines(stream_text):
                        yield _to_ndjson({"type": "line", "index": i, "text": line})
                        await asyncio.sleep(STREAM_LINE_DELAY_S)
                    yield _to_ndjson({
                        "type": "response_done",
                        "index": i,
                        "response": jsonable_encoder(bad_dto),
                    })
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
                dto = ChatResponseDTO.from_unified_response(response)
                ordered_responses[idx] = dto

                yield _to_ndjson({
                    "type": "response_start",
                    "index": idx,
                    "provider": dto.provider,
                    "model": dto.model,
                })

                stream_text = dto.text or ""
                if not stream_text and dto.error:
                    stream_text = f"Error: {dto.error.message}"
                for line in _iter_stream_lines(stream_text):
                    yield _to_ndjson({"type": "line", "index": idx, "text": line})
                    await asyncio.sleep(STREAM_LINE_DELAY_S)

                yield _to_ndjson({
                    "type": "response_done",
                    "index": idx,
                    "response": jsonable_encoder(dto),
                })

            dtos = [r for r in ordered_responses if r is not None]
            compare_payload = {
                "request_group_id": str(uuid.uuid4()),
                "responses": [jsonable_encoder(r) for r in dtos],
                "success_count": sum(1 for r in dtos if r.error is None),
                "error_count": sum(1 for r in dtos if r.error is not None),
                "total_tokens": sum(r.token_usage.total_tokens for r in dtos),
                "total_cost": sum(r.estimated_cost for r in dtos),
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            }

            yield _to_ndjson({"type": "done", "mode": "compare", "compare": compare_payload})

            # Persist each model response to history DB (best-effort)
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
            yield _to_ndjson({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
