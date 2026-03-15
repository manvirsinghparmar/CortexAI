"""Authenticated identity/config snapshot endpoint for API key holders."""

import os
from uuid import uuid4

from fastapi import APIRouter, Depends, Request

from db import get_api_key_settings
from server import circuit_breaker as circuit_breaker_service
from server import persistence as persistence_service
from server import privacy as privacy_service
from server import rate_limit as rate_limit_service
from server import savings as savings_service
from server.dependencies import get_auth
from server.schemas.responses import WhoAmIResponseDTO

router = APIRouter(prefix="/v1", tags=["Auth"])

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_resolve_identity = persistence_service.resolve_identity
_db_uow = persistence_service.db_uow


def _parse_int(value: str | None) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def _parse_float(value: str | None) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(value)
    except Exception:
        return None


def _baseline_source_from_env() -> str:
    if os.getenv("BASELINE_MODEL_ID"):
        return "env_baseline_model_id"
    if os.getenv("BASELINE_PROVIDER") and os.getenv("BASELINE_MODEL"):
        return "env_provider_model"
    return "default"


def _resolve_baseline_no_db() -> tuple[str, str]:
    model_id = (os.getenv("BASELINE_MODEL_ID") or "").strip()
    if model_id and ":" in model_id:
        provider, model = model_id.split(":", 1)
        provider = provider.strip().lower()
        model = model.strip()
        if provider and model:
            return provider, model

    provider = (os.getenv("BASELINE_PROVIDER") or "").strip().lower()
    model = (os.getenv("BASELINE_MODEL") or "").strip()
    if provider and model:
        return provider, model

    return savings_service.DEFAULT_BASELINE_PROVIDER, savings_service.DEFAULT_BASELINE_MODEL


@router.get("/whoami", response_model=WhoAmIResponseDTO)
async def whoami(
    request: Request,
    auth=Depends(get_auth),
):
    req_id = str(getattr(request.state, "request_id", "") or uuid4())

    api_key_id: str | None = None
    user_id: str | None = None
    rpm = rate_limit_service.default_requests_per_minute()
    baseline_source = _baseline_source_from_env()

    if API_DB_ENABLED:
        with _db_uow(commit_on_success=False) as db_session:
            resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
            user_id = str(resolution.user_id)
            api_key_id = str(resolution.api_key_id) if resolution.api_key_id else None

            baseline_provider, baseline_model = savings_service.resolve_baseline_for_api_key(
                db_session,
                api_key_id=resolution.api_key_id,
            )

            if resolution.api_key_id is not None:
                settings = get_api_key_settings(db_session, resolution.api_key_id)
                if settings:
                    override_rpm = settings.get("requests_per_minute")
                    if override_rpm is not None:
                        try:
                            rpm = int(override_rpm)
                        except Exception:
                            pass
                    if settings.get("baseline_provider") and settings.get("baseline_model"):
                        baseline_source = "api_key"
    else:
        baseline_provider, baseline_model = _resolve_baseline_no_db()

    daily_cap_scope = (os.getenv("DAILY_CAP_SCOPE", "api_key") or "api_key").strip().lower()
    if daily_cap_scope not in {"api_key", "user"}:
        daily_cap_scope = "api_key"

    return WhoAmIResponseDTO(
        api_key_id=api_key_id,
        user_id=user_id,
        plan_tier=os.getenv("PLAN_TIER"),
        storage_policy="metadata" if privacy_service.is_metadata_only() else "full",
        redact_pii=privacy_service.redact_pii_enabled(),
        baseline={
            "provider": baseline_provider,
            "model": baseline_model,
            "source": baseline_source,
        },
        rate_limits={
            "requests_per_minute": max(0, int(rpm)),
            "daily_cap_scope": daily_cap_scope,
            "daily_token_cap": _parse_int(os.getenv("DAILY_TOKEN_CAP")),
            "daily_cost_cap": _parse_float(os.getenv("DAILY_COST_CAP")),
        },
        breakers={
            "failure_threshold": circuit_breaker_service.failure_threshold(),
            "window_seconds": circuit_breaker_service.window_seconds(),
            "cooldown_seconds": circuit_breaker_service.cooldown_seconds(),
            "scope": "global_provider_model",
        },
    )
