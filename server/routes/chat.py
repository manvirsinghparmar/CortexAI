"""Chat endpoint for single AI model requests."""

import asyncio
import os
from dataclasses import dataclass
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status

from models.user_context import UserContext
from orchestrator.core import CortexOrchestrator
from server.dependencies import get_api_key, get_orchestrator
from server.schemas.requests import ChatRequest
from server.schemas.responses import ChatResponseDTO
from server.utils import clamp_max_tokens, validate_and_trim_context
from utils.logger import get_logger

logger = get_logger(__name__)

API_DB_ENABLED = False
try:
    from db import (
        create_api_key,
        create_llm_request,
        create_llm_response,
        create_routing_attempts,
        create_routing_decision,
        get_db,
        get_or_create_service_user,
        get_user_by_api_key,
        upsert_usage_daily,
    )

    if os.getenv("DATABASE_URL"):
        API_DB_ENABLED = True
except Exception:
    API_DB_ENABLED = False

router = APIRouter(prefix="/v1", tags=["Chat"])
AUTO_REGISTER_UNMAPPED_DEFAULT = "false"


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
            "API key auto-registered for DB persistence",
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
            "Unmapped API key persisted under fallback service user (no api_key_id)",
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
            "Rejecting API request: unmapped API key and fallback disabled",
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
            "API key resolution failed",
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


def _persist_api_chat_interaction(
    *,
    api_key: str,
    prompt: str,
    response,
    request_context,
    research_mode: str,
    resolution: ApiKeyPersistenceResolution | None,
) -> None:
    """
    Persist API chat request/response and routing telemetry.
    Failures are isolated and never affect API response flow.
    """
    if not API_DB_ENABLED:
        return

    db_gen = None
    db_session = None
    try:
        db_gen = get_db()
        db_session = next(db_gen)

        request_id = getattr(response, "request_id", "unknown")
        resolved = resolution
        if resolved is None:
            mapped = get_user_by_api_key(db_session, api_key)
            if not mapped:
                logger.warning(
                    "Skipping API DB persistence: API key not mapped",
                    extra={
                        "extra_fields": {
                            "request_id": request_id,
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

        llm_request_id = create_llm_request(
            db_session,
            user_id=user_id,
            request_id=response.request_id,
            route_mode="ask",
            provider=response.provider,
            model=response.model,
            prompt=prompt,
            session_id=session_id,
            api_key_id=api_key_id,
            input_tokens_est=response.token_usage.prompt_tokens,
            store_prompt=False,
        )

        create_llm_response(db_session, llm_request_id, response)

        routing_metadata, attempts, features = _extract_routing_payload(response)
        if routing_metadata:
            metadata = response.metadata if isinstance(response.metadata, dict) else {}
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

        upsert_usage_daily(
            db_session,
            user_id=user_id,
            total_tokens=response.token_usage.total_tokens,
            estimated_cost=response.estimated_cost,
        )

        db_session.commit()
        logger.info(
            "API chat persisted to DB",
            extra={
                "extra_fields": {
                    "request_id": request_id,
                    "resolved_user_id": str(user_id),
                    "api_key_id": str(api_key_id) if api_key_id else None,
                    "decision_path": resolved.decision_path,
                    "persistence_status": "success",
                    "routing_persisted": bool(routing_metadata),
                }
            },
        )
    except Exception as exc:
        if db_session is not None:
            db_session.rollback()
        logger.warning(
            "API chat DB persistence failed",
            extra={
                "extra_fields": {
                    "request_id": getattr(response, "request_id", "unknown"),
                    "error": str(exc),
                    "decision_path": resolution.decision_path if resolution else "unknown",
                    "persistence_status": "failed",
                }
            },
        )
    finally:
        if db_gen is not None:
            db_gen.close()


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

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)

    research_mode = request.research_mode or "off"
    middleware_request_id = getattr(http_request.state, "request_id", "unknown")

    resolution = await asyncio.to_thread(
        _resolve_api_key_for_request,
        api_key=api_key,
        request_id=middleware_request_id,
    )

    response = await asyncio.to_thread(
        orchestrator.ask,
        prompt=request.prompt,
        model_type=request.provider,
        context=context,
        model_name=request.model,
        token_tracker=None,
        research_mode=research_mode,
        routing_mode=request.routing_mode or "smart",
        routing_constraints=request.routing_constraints,
        **kwargs,
    )

    await asyncio.to_thread(
        _persist_api_chat_interaction,
        api_key=api_key,
        prompt=request.prompt,
        response=response,
        request_context=request.context,
        research_mode=research_mode,
        resolution=resolution,
    )

    return ChatResponseDTO.from_unified_response(response)
