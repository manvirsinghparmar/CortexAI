"""Savings computation and persistence for B2B reporting."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from db import get_api_key_settings, upsert_llm_savings
from models.unified_response import UnifiedResponse
from utils.cost_calculator import CostCalculator
from utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_BASELINE_PROVIDER = "openai"
DEFAULT_BASELINE_MODEL = "gpt-4o"


@dataclass(frozen=True)
class SavingsComputation:
    actual_cost: float
    baseline_provider: str
    baseline_model: str
    baseline_cost: float
    savings_amount: float
    savings_pct: float
    response_status: str
    error_code: str | None


def _parse_baseline_model_id(raw: str | None) -> tuple[str, str] | None:
    if not raw:
        return None
    value = raw.strip()
    if not value or ":" not in value:
        return None
    provider, model = value.split(":", 1)
    provider = provider.strip().lower()
    model = model.strip()
    if not provider or not model:
        return None
    return provider, model


def resolve_baseline_for_api_key(
    db_session: Session,
    *,
    api_key_id: UUID | None,
) -> tuple[str, str]:
    """
    Resolve baseline provider/model with policy:
    1) api_key_settings baseline
    2) BASELINE_MODEL_ID (provider:model)
    3) BASELINE_PROVIDER + BASELINE_MODEL
    4) DEFAULT_BASELINE_PROVIDER + DEFAULT_BASELINE_MODEL
    """
    if api_key_id is not None:
        try:
            settings = get_api_key_settings(db_session, api_key_id)
        except Exception:
            settings = None
        if settings:
            provider = (settings.get("baseline_provider") or "").strip().lower()
            model = (settings.get("baseline_model") or "").strip()
            if provider and model:
                return provider, model

    model_id = _parse_baseline_model_id(os.getenv("BASELINE_MODEL_ID"))
    if model_id is not None:
        return model_id

    baseline_provider = (os.getenv("BASELINE_PROVIDER") or "").strip().lower()
    baseline_model = (os.getenv("BASELINE_MODEL") or "").strip()
    if baseline_provider and baseline_model:
        return baseline_provider, baseline_model

    return DEFAULT_BASELINE_PROVIDER, DEFAULT_BASELINE_MODEL


def _safe_cost(
    *,
    provider: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
) -> float:
    try:
        calculator = CostCalculator(model_type=provider, model_name=model)
        costs = calculator.calculate_cost(prompt_tokens, completion_tokens)
        return float(costs.get("total_cost") or 0.0)
    except Exception:
        logger.exception("Baseline cost simulation failed")
        return 0.0


def compute_savings(
    *,
    response: UnifiedResponse,
    baseline_provider: str,
    baseline_model: str,
) -> SavingsComputation:
    prompt_tokens = int(getattr(response.token_usage, "prompt_tokens", 0) or 0)
    completion_tokens = int(getattr(response.token_usage, "completion_tokens", 0) or 0)
    actual_cost = float(response.estimated_cost or 0.0)
    response_status = "error" if response.is_error else "success"
    error_code = response.error.code if response.error else None

    # Avoid misleading "savings" on failed calls by zeroing baseline/savings for error rows.
    if response.is_error:
        baseline_cost = 0.0
        savings_amount = 0.0
        savings_pct = 0.0
    else:
        baseline_cost = _safe_cost(
            provider=baseline_provider,
            model=baseline_model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )
        savings_amount = baseline_cost - actual_cost
        savings_pct = (savings_amount / baseline_cost) if baseline_cost > 0 else 0.0

    return SavingsComputation(
        actual_cost=actual_cost,
        baseline_provider=baseline_provider,
        baseline_model=baseline_model,
        baseline_cost=baseline_cost,
        savings_amount=savings_amount,
        savings_pct=savings_pct,
        response_status=response_status,
        error_code=error_code,
    )


def persist_request_savings(
    db_session: Session,
    *,
    llm_request_id: UUID,
    user_id: UUID,
    api_key_id: UUID | None,
    response: UnifiedResponse,
    usage_date: date | None = None,
) -> SavingsComputation:
    baseline_provider, baseline_model = resolve_baseline_for_api_key(
        db_session,
        api_key_id=api_key_id,
    )
    result = compute_savings(
        response=response,
        baseline_provider=baseline_provider,
        baseline_model=baseline_model,
    )

    upsert_llm_savings(
        db_session,
        llm_request_id=llm_request_id,
        user_id=user_id,
        api_key_id=api_key_id,
        provider=response.provider,
        model=response.model,
        actual_cost=result.actual_cost,
        baseline_provider=result.baseline_provider,
        baseline_model=result.baseline_model,
        baseline_cost=result.baseline_cost,
        savings_amount=result.savings_amount,
        savings_pct=result.savings_pct,
        response_status=result.response_status,
        error_code=result.error_code,
        usage_date=usage_date,
    )
    return result
