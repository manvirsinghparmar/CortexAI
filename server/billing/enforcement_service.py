"""Subscription authorization and unified AI-credit settlement."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from db import billing_repository as repository
from orchestrator.model_registry import ModelRegistry
from orchestrator.routing_types import ModelCandidate
from server.billing.credit_calculator import (
    ADVANCED_WEB_SEARCH_CREDITS,
    CreditCharge,
    calculate_credit_charge,
)
from server.billing.credit_estimator import estimate_model_credits, fallback_actual_tokens
from server.billing.entitlement_service import (
    EntitlementDenial,
    ModelTargetIntent,
    SubscriptionRequestIntent,
    evaluate_entitlement,
    load_allowance_usage,
)
from server.billing.errors import (
    BillingConfigurationError,
    EntitlementDeniedError,
    InvalidModelSelectionError,
    UsageAllowanceExceededError,
)
from server.billing.metering_service import release_usage, reserve_usage, settle_usage
from server.billing.models import ALLOWED_MODEL_BILLING_CLASSES
from server.billing.plan_catalog import get_plan_catalog
from server.billing.subscription_service import (
    EffectiveSubscription,
    resolve_effective_subscription,
)

_BILLING_CLASS_RANK = {
    "economical": 0,
    "standard": 1,
    "advanced": 2,
    "premium": 3,
}
_ATTACHMENT_ESTIMATE_CHARS = 12_000


@dataclass(frozen=True)
class ReservedModelEstimate:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    input_multiplier: float
    output_multiplier: float
    pricing_version: str
    total_credits: int


@dataclass(frozen=True)
class ReservedRequestUsage:
    reservation_id: UUID
    request_id: str
    operation_type: str
    requested_quantities: dict[str, int]
    allowed_billing_classes: frozenset[str]
    current_plan: str
    reset_at: datetime
    input_text: str = ""
    model_estimates: tuple[ReservedModelEstimate, ...] = ()


@dataclass(frozen=True)
class BillableModelUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    output_text: str = ""
    provider_cost_usd: float = 0.0
    usage_estimated: bool = False


class _BillingClassResolver(Protocol):
    def model_billing_class(self, provider: str, model: str) -> str | None: ...


@lru_cache(maxsize=1)
def _default_model_registry() -> ModelRegistry:
    try:
        return ModelRegistry.from_yaml()
    except Exception as exc:
        raise BillingConfigurationError("The model credit registry could not be loaded") from exc


def resolve_model_target(
    *,
    provider: str,
    model: str,
    orchestrator: _BillingClassResolver | object | None = None,
) -> ModelTargetIntent:
    """Resolve an enabled model to its server-owned access category."""
    normalized_provider = str(provider or "").strip().lower()
    normalized_model = str(model or "").strip()
    candidate = _default_model_registry().find_model(normalized_provider, normalized_model)
    if not candidate or not candidate.enabled:
        raise InvalidModelSelectionError(
            provider=normalized_provider or "unknown",
            model=normalized_model or "unknown",
        )

    resolver = getattr(orchestrator, "model_billing_class", None)
    billing_class: object = (
        resolver(normalized_provider, normalized_model) if callable(resolver) else candidate.billing_class
    )
    normalized_class = _normalized_billing_class(billing_class)
    if normalized_class not in ALLOWED_MODEL_BILLING_CLASSES:
        raise BillingConfigurationError("A model is missing a valid subscription access category")
    if normalized_class != candidate.billing_class.value:
        raise BillingConfigurationError("Model access metadata does not match the credit registry")
    return ModelTargetIntent(
        provider=normalized_provider,
        model=normalized_model,
        billing_class=normalized_class,
    )


def _normalized_billing_class(value: object) -> str:
    normalized = getattr(value, "value", value)
    return str(normalized or "").strip().lower()


def _candidate_for_target(target: ModelTargetIntent) -> ModelCandidate:
    candidate = _default_model_registry().find_model(target.provider, target.model)
    if (
        candidate is None
        or not candidate.enabled
        or candidate.billing_class.value != _normalized_billing_class(target.billing_class)
    ):
        raise BillingConfigurationError("A billable model target is unavailable or misclassified")
    return candidate


def _smart_reservation_candidate(effective: EffectiveSubscription) -> ModelCandidate:
    allowed = effective.plan.entitlements.allowed_billing_classes
    candidates = [
        candidate
        for candidate in _default_model_registry().list_enabled_models()
        if candidate.billing_class.value in allowed
    ]
    if not candidates:
        raise BillingConfigurationError("The plan has no eligible Smart routing models")
    return max(
        candidates,
        key=lambda item: (
            item.input_credit_multiplier + item.output_credit_multiplier,
            _BILLING_CLASS_RANK[item.billing_class.value],
        ),
    )


def _allowance_denial(
    error: UsageAllowanceExceededError,
    effective: EffectiveSubscription,
) -> EntitlementDenial:
    recommended = next(
        (
            plan.code
            for plan in get_plan_catalog().list_plans()
            if plan.rank > effective.plan.rank
            and plan.allowances.ai_credits > error.limit
        ),
        None,
    )
    return EntitlementDenial(
        code="insufficient_credits",
        message=(
            f"This request is estimated to require {error.requested:,} credits. "
            f"You have {error.remaining:,} remaining."
        ),
        meter="ai_credits",
        current_plan=error.current_plan,
        recommended_plan=recommended,
        used=error.used,
        limit=error.limit,
        required=error.requested,
        remaining=error.remaining,
        reset_at=error.reset_at,
    )


def authorize_and_reserve_usage(
    db_session: Session,
    *,
    user_id: UUID,
    request_id: str,
    operation_type: str,
    model_targets: Sequence[ModelTargetIntent],
    research_enabled: bool,
    smart_routing: bool = False,
    optimization_enabled: bool = False,
    attachment_count: int = 0,
    total_attachment_bytes: int = 0,
    attachment_sizes: Sequence[int] = (),
    input_text: str = "",
    max_output_tokens: int | None = None,
) -> ReservedRequestUsage:
    """Resolve access, estimate the maximum likely charge, and reserve it atomically."""
    effective = resolve_effective_subscription(db_session, user_id)
    normalized_targets = tuple(
        ModelTargetIntent(
            provider=str(target.provider or "").strip().lower(),
            model=str(target.model or "").strip(),
            billing_class=_normalized_billing_class(target.billing_class),
        )
        for target in model_targets
    )
    candidates = (
        (_smart_reservation_candidate(effective),)
        if smart_routing
        else tuple(_candidate_for_target(target) for target in normalized_targets)
    )
    if not candidates:
        raise BillingConfigurationError("A credit reservation requires at least one model")

    estimated_text = str(input_text or "") + (
        "x" * (_ATTACHMENT_ESTIMATE_CHARS * max(0, attachment_count))
    )
    estimates: list[ReservedModelEstimate] = []
    estimated_credits = ADVANCED_WEB_SEARCH_CREDITS if research_enabled else 0
    for candidate in candidates:
        estimate = estimate_model_credits(
            candidate,
            input_text=estimated_text,
            max_output_tokens=max_output_tokens,
        )
        estimated_credits += estimate.charge.total_credits
        estimates.append(
            ReservedModelEstimate(
                provider=candidate.provider,
                model=candidate.model_name,
                input_tokens=estimate.input_tokens,
                output_tokens=estimate.output_tokens,
                input_multiplier=candidate.input_credit_multiplier,
                output_multiplier=candidate.output_credit_multiplier,
                pricing_version=candidate.credit_pricing_version,
                total_credits=estimate.charge.total_credits,
            )
        )

    intent_targets = (
        (
            ModelTargetIntent(
                provider=candidates[0].provider,
                model=candidates[0].model_name,
                billing_class=candidates[0].billing_class.value,
            ),
        )
        if smart_routing
        else normalized_targets
    )
    intent = SubscriptionRequestIntent(
        operation_type=operation_type,
        model_targets=intent_targets,
        research_enabled=research_enabled,
        optimization_enabled=optimization_enabled,
        attachment_count=attachment_count,
        total_attachment_bytes=total_attachment_bytes,
        attachment_sizes=tuple(attachment_sizes),
        estimated_credits=estimated_credits,
    )
    allowances = load_allowance_usage(db_session, effective)
    decision = evaluate_entitlement(effective, intent, allowances)
    if not decision.allowed:
        if decision.denial is None:
            raise BillingConfigurationError("Subscription access was denied without a reason")
        raise EntitlementDeniedError(decision.denial)

    try:
        reservation = reserve_usage(
            db_session,
            effective_subscription=effective,
            request_id=request_id,
            operation_type=operation_type,
            requested_quantities={"ai_credits": estimated_credits},
        )
    except UsageAllowanceExceededError as exc:
        raise EntitlementDeniedError(_allowance_denial(exc, effective)) from exc

    return ReservedRequestUsage(
        reservation_id=reservation.id,
        request_id=request_id,
        operation_type=operation_type,
        requested_quantities=dict(reservation.requested_quantities),
        allowed_billing_classes=effective.plan.entitlements.allowed_billing_classes,
        current_plan=effective.plan.code,
        reset_at=effective.current_period_end,
        input_text=str(input_text or ""),
        model_estimates=tuple(estimates),
    )


def _usage_charge(usage: BillableModelUsage, reservation: ReservedRequestUsage) -> tuple[CreditCharge, ModelCandidate]:
    candidate = _default_model_registry().find_model(usage.provider, usage.model)
    if candidate is None or not candidate.enabled:
        raise BillingConfigurationError("Successful model usage is absent from the credit registry")
    input_tokens = max(0, int(usage.input_tokens))
    output_tokens = max(0, int(usage.output_tokens))
    estimated = bool(usage.usage_estimated)
    if input_tokens == 0 and output_tokens == 0:
        input_tokens, output_tokens = fallback_actual_tokens(
            input_text=reservation.input_text,
            output_text=usage.output_text,
        )
        estimated = True
    return (
        calculate_credit_charge(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            input_multiplier=candidate.input_credit_multiplier,
            output_multiplier=candidate.output_credit_multiplier,
            estimated=estimated,
        ),
        candidate,
    )


def _estimated_usage_for_target(
    target: ModelTargetIntent,
    reservation: ReservedRequestUsage,
) -> BillableModelUsage:
    estimate = next(
        (
            item
            for item in reservation.model_estimates
            if item.provider == target.provider and item.model == target.model
        ),
        None,
    )
    if estimate is None and len(reservation.model_estimates) == 1:
        estimate = reservation.model_estimates[0]
    if estimate is None:
        raise BillingConfigurationError("Successful usage cannot be matched to its reservation")
    return BillableModelUsage(
        provider=target.provider,
        model=target.model,
        input_tokens=estimate.input_tokens,
        output_tokens=estimate.output_tokens,
        usage_estimated=True,
    )


def finalize_reserved_usage(
    db_session: Session,
    *,
    reservation: ReservedRequestUsage,
    successful_targets: Sequence[ModelTargetIntent] = (),
    model_usages: Sequence[BillableModelUsage] = (),
    research_performed: bool,
    optimization_performed: bool = False,
    file_analysis_performed: bool = False,
    uploaded_bytes: int = 0,
    release_reason: str = "provider_failed_before_billable_output",
) -> None:
    """Settle actual model/search credits and persist itemized reconciliation rows."""
    del uploaded_bytes
    usages = tuple(model_usages) or tuple(
        _estimated_usage_for_target(target, reservation) for target in successful_targets
    )
    transaction_items: list[dict[str, object]] = []
    total_credits = 0
    for usage in usages:
        charge, candidate = _usage_charge(usage, reservation)
        total_credits += charge.total_credits
        transaction_items.append(
            {
                "item_type": "model",
                "provider": candidate.provider,
                "model": candidate.model_name,
                "input_tokens": charge.input_tokens,
                "output_tokens": charge.output_tokens,
                "input_credits": charge.input_credits,
                "output_credits": charge.output_credits,
                "fixed_credits": 0,
                "total_credits": charge.total_credits,
                "provider_cost_usd": max(0.0, float(usage.provider_cost_usd)),
                "usage_estimated": charge.estimated,
                "pricing_version": candidate.credit_pricing_version,
                "metadata": {
                    "file_context": bool(file_analysis_performed),
                    "prompt_optimization": bool(optimization_performed),
                },
            }
        )
    if research_performed:
        total_credits += ADVANCED_WEB_SEARCH_CREDITS
        transaction_items.append(
            {
                "item_type": "research",
                "provider": "tavily",
                "model": None,
                "input_tokens": 0,
                "output_tokens": 0,
                "input_credits": 0,
                "output_credits": 0,
                "fixed_credits": ADVANCED_WEB_SEARCH_CREDITS,
                "total_credits": ADVANCED_WEB_SEARCH_CREDITS,
                "provider_cost_usd": 0.0,
                "usage_estimated": False,
                "pricing_version": "research-2026-07-29",
                "metadata": {},
            }
        )
    if total_credits == 0:
        release_usage(db_session, reservation_id=reservation.reservation_id, reason=release_reason)
        return

    reserved = int(reservation.requested_quantities.get("ai_credits", 0))
    if total_credits > reserved:
        raise BillingConfigurationError("Actual credit usage exceeds the authorized reservation")
    settled = settle_usage(
        db_session,
        reservation_id=reservation.reservation_id,
        successful_quantities={"ai_credits": total_credits},
    )
    for index, item in enumerate(transaction_items):
        repository.create_credit_transaction(
            db_session,
            billing_account_id=settled.billing_account_id,
            usage_period_id=settled.usage_period_id,
            reservation_id=settled.id,
            request_id=settled.request_id,
            operation_type=settled.operation_type,
            item_index=index,
            **item,
        )


def release_reserved_usage(
    db_session: Session,
    *,
    reservation: ReservedRequestUsage,
    reason: str,
) -> None:
    release_usage(db_session, reservation_id=reservation.reservation_id, reason=reason)
