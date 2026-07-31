"""Subscription authorization and unified AI-credit settlement."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Protocol, TypedDict
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
from server.billing.metering_service import (
    release_usage,
    reserve_usage,
    settle_usage_with_supplement,
)
from server.billing.models import ALLOWED_MODEL_BILLING_CLASSES
from server.billing.plan_catalog import get_plan_catalog
from server.billing.subscription_service import (
    EffectiveSubscription,
    resolve_effective_subscription,
)

_ATTACHMENT_ESTIMATE_CHARS = 12_000
_RESEARCH_CONTEXT_ESTIMATE_CHARS = 30_000


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
class SmartCandidateEstimate:
    provider: str
    model: str
    billing_class: str
    reservation_credits: int


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
    smart_candidates: tuple[SmartCandidateEstimate, ...] = ()


@dataclass(frozen=True)
class BillableModelUsage:
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    output_text: str = ""
    provider_cost_usd: float = 0.0
    usage_estimated: bool = False


class _CreditTransactionItem(TypedDict):
    item_type: str
    provider: str | None
    model: str | None
    input_tokens: int
    output_tokens: int
    input_credits: int
    output_credits: int
    fixed_credits: int
    total_credits: int
    provider_cost_usd: float
    usage_estimated: bool
    pricing_version: str
    metadata: dict[str, object]


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
        resolver(normalized_provider, normalized_model)
        if callable(resolver)
        else candidate.billing_class
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


def _allowance_denial(
    error: UsageAllowanceExceededError,
    effective: EffectiveSubscription,
) -> EntitlementDenial:
    recommended = next(
        (
            plan.code
            for plan in get_plan_catalog().list_plans()
            if plan.rank > effective.plan.rank and plan.allowances.ai_credits > error.limit
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
    model_attempt_count: int = 1,
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
    estimated_text = str(input_text or "") + (
        "x" * (_ATTACHMENT_ESTIMATE_CHARS * max(0, attachment_count))
    )
    if research_enabled:
        estimated_text += "x" * _RESEARCH_CONTEXT_ESTIMATE_CHARS
    if isinstance(model_attempt_count, bool) or model_attempt_count < 1:
        raise ValueError("model_attempt_count must be a positive integer")
    estimates: list[ReservedModelEstimate] = []
    smart_candidate_estimates: list[SmartCandidateEstimate] = []
    allowances = load_allowance_usage(db_session, effective)

    candidates: tuple[ModelCandidate, ...]
    if smart_routing:
        if not normalized_targets:
            raise BillingConfigurationError("Smart routing produced no candidate plan")
        remaining = allowances["ai_credits"].remaining
        plan_candidates: list[tuple[ModelCandidate, int, ReservedModelEstimate]] = []
        for target in normalized_targets:
            candidate = _candidate_for_target(target)
            if (
                candidate.billing_class.value
                not in effective.plan.entitlements.allowed_billing_classes
            ):
                continue
            estimate = estimate_model_credits(
                candidate,
                input_text=estimated_text,
                max_output_tokens=max_output_tokens,
            )
            reservation_credits = estimate.charge.total_credits + (
                ADVANCED_WEB_SEARCH_CREDITS if research_enabled else 0
            )
            model_estimate = ReservedModelEstimate(
                provider=candidate.provider,
                model=candidate.model_name,
                input_tokens=estimate.input_tokens,
                output_tokens=estimate.output_tokens,
                input_multiplier=candidate.input_credit_multiplier,
                output_multiplier=candidate.output_credit_multiplier,
                pricing_version=candidate.credit_pricing_version,
                total_credits=estimate.charge.total_credits,
            )
            plan_candidates.append((candidate, reservation_credits, model_estimate))
            if reservation_credits <= remaining:
                smart_candidate_estimates.append(
                    SmartCandidateEstimate(
                        provider=candidate.provider,
                        model=candidate.model_name,
                        billing_class=candidate.billing_class.value,
                        reservation_credits=reservation_credits,
                    )
                )
        if not plan_candidates:
            raise BillingConfigurationError("The plan has no eligible Smart routing models")
        if not smart_candidate_estimates:
            required = min(item[1] for item in plan_candidates)
            recommended = next(
                (
                    plan.code
                    for plan in get_plan_catalog().list_plans()
                    if plan.rank > effective.plan.rank
                    and plan.allowances.ai_credits > effective.plan.allowances.ai_credits
                ),
                None,
            )
            raise EntitlementDeniedError(
                EntitlementDenial(
                    code="insufficient_credits",
                    message=(
                        f"The least expensive appropriate Smart candidate requires "
                        f"{required:,} credits. You have {remaining:,} remaining."
                    ),
                    meter="ai_credits",
                    current_plan=effective.plan.code,
                    recommended_plan=recommended,
                    used=allowances["ai_credits"].used,
                    limit=allowances["ai_credits"].limit,
                    required=required,
                    remaining=remaining,
                    reset_at=effective.current_period_end,
                )
            )
        selected_authorization = smart_candidate_estimates[0]
        selected = next(
            item
            for item in plan_candidates
            if item[0].provider == selected_authorization.provider
            and item[0].model_name == selected_authorization.model
        )
        candidates = (selected[0],)
        estimates.append(selected[2])
        estimated_credits = selected[1]
    else:
        candidates = tuple(_candidate_for_target(target) for target in normalized_targets)
        if not candidates:
            raise BillingConfigurationError("A credit reservation requires at least one model")
        estimated_credits = ADVANCED_WEB_SEARCH_CREDITS if research_enabled else 0
        for candidate in candidates:
            estimate = estimate_model_credits(
                candidate,
                input_text=estimated_text,
                max_output_tokens=max_output_tokens,
            )
            estimated_credits += estimate.charge.total_credits * model_attempt_count
            for _attempt in range(model_attempt_count):
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
        smart_candidates=tuple(smart_candidate_estimates),
    )


def _usage_charge(
    usage: BillableModelUsage, reservation: ReservedRequestUsage
) -> tuple[CreditCharge, ModelCandidate]:
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
    transaction_items: list[_CreditTransactionItem] = []
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

    plan = get_plan_catalog().require(reservation.current_plan)
    settlement = settle_usage_with_supplement(
        db_session,
        reservation_id=reservation.reservation_id,
        actual_quantity=total_credits,
        allowance_limit=plan.allowances.ai_credits,
    )
    settled = settlement.reservation
    transaction_items = _reconcile_transaction_items(
        transaction_items,
        billed_credits=settlement.billed_quantity,
        actual_credits=total_credits,
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


def _reconcile_transaction_items(
    items: Sequence[_CreditTransactionItem],
    *,
    billed_credits: int,
    actual_credits: int,
) -> list[_CreditTransactionItem]:
    """Keep ledger totals equal to settled credits while retaining overrun evidence."""

    if billed_credits >= actual_credits:
        return [item.copy() for item in items]

    remaining = max(0, billed_credits)
    reconciled: list[_CreditTransactionItem] = []
    unbilled_provider_cost = 0.0
    # Fixed research is deterministic and was included explicitly in preflight.
    ordered = sorted(items, key=lambda item: 0 if item.get("item_type") == "research" else 1)
    for original in ordered:
        item = original.copy()
        item_actual = max(0, int(item.get("total_credits") or 0))
        item_billed = min(item_actual, remaining)
        remaining -= item_billed
        original_cost = max(0.0, float(item.get("provider_cost_usd") or 0.0))
        billed_ratio = (item_billed / item_actual) if item_actual else 0.0
        billed_cost = original_cost * billed_ratio
        unbilled_provider_cost += max(0.0, original_cost - billed_cost)

        metadata = dict(item.get("metadata") or {})
        metadata.update(
            {
                "under_reserved": True,
                "calculated_total_credits": item_actual,
                "billed_total_credits": item_billed,
            }
        )
        item["metadata"] = metadata
        item["provider_cost_usd"] = billed_cost
        item["total_credits"] = item_billed
        if item.get("item_type") == "research":
            item["fixed_credits"] = item_billed
            item["input_credits"] = 0
            item["output_credits"] = 0
        else:
            input_actual = max(0, int(item.get("input_credits") or 0))
            billed_input = min(input_actual, item_billed)
            item["input_credits"] = billed_input
            item["output_credits"] = max(0, item_billed - billed_input)
            item["fixed_credits"] = 0
        reconciled.append(item)

    reconciled.append(
        {
            "item_type": "adjustment",
            "provider": None,
            "model": None,
            "input_tokens": 0,
            "output_tokens": 0,
            "input_credits": 0,
            "output_credits": 0,
            "fixed_credits": 0,
            "total_credits": 0,
            "provider_cost_usd": unbilled_provider_cost,
            "usage_estimated": False,
            "pricing_version": "reconciliation-2026-07-30",
            "metadata": {
                "under_reserved": True,
                "calculated_credits": actual_credits,
                "billed_credits": billed_credits,
                "unbilled_credits": max(0, actual_credits - billed_credits),
                "unbilled_provider_cost_usd": unbilled_provider_cost,
            },
        }
    )
    return reconciled


def release_reserved_usage(
    db_session: Session,
    *,
    reservation: ReservedRequestUsage,
    reason: str,
) -> None:
    release_usage(db_session, reservation_id=reservation.reservation_id, reason=reason)
