"""Shared subscription authorization and usage-finalization workflow.

This module keeps HTTP routes thin while preserving caller-owned transaction
boundaries. It combines the WP3 entitlement decision with WP4's atomic usage
reservation lifecycle, but never invokes model providers itself.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from typing import Protocol
from uuid import UUID

from sqlalchemy.orm import Session

from orchestrator.model_registry import ModelRegistry
from server.billing.entitlement_service import (
    EntitlementDenial,
    ModelTargetIntent,
    SubscriptionRequestIntent,
    evaluate_entitlement,
    load_allowance_usage,
    required_quantities,
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

_BILLING_CLASS_RANK = {"standard": 0, "advanced": 1, "ultra": 2}
_PREMIUM_CLASS_METERS = {
    "advanced": "advanced_model_responses",
    "ultra": "ultra_model_responses",
}


@dataclass(frozen=True)
class ReservedRequestUsage:
    """Reservation context retained until a provider attempt is finalized."""

    reservation_id: UUID
    request_id: str
    operation_type: str
    requested_quantities: Mapping[str, int]
    allowed_billing_classes: frozenset[str]
    current_plan: str
    reset_at: datetime


class _BillingClassResolver(Protocol):
    def model_billing_class(self, provider: str, model: str) -> str | None: ...


@lru_cache(maxsize=1)
def _default_model_registry() -> ModelRegistry:
    try:
        return ModelRegistry.from_yaml()
    except Exception as exc:
        raise BillingConfigurationError("The model billing registry could not be loaded") from exc


def resolve_model_target(
    *,
    provider: str,
    model: str,
    orchestrator: _BillingClassResolver | object | None = None,
) -> ModelTargetIntent:
    """Resolve an enabled model to its server-owned subscription class."""
    normalized_provider = str(provider or "").strip().lower()
    normalized_model = str(model or "").strip()
    if not normalized_provider or not normalized_model:
        raise InvalidModelSelectionError(
            provider=normalized_provider or "unknown",
            model=normalized_model or "unknown",
        )

    billing_class: object | None = None
    resolver = getattr(orchestrator, "model_billing_class", None)
    if callable(resolver):
        billing_class = resolver(normalized_provider, normalized_model)
    else:
        candidate = _default_model_registry().find_model(normalized_provider, normalized_model)
        if candidate and candidate.enabled:
            billing_class = candidate.billing_class

    if billing_class is None:
        raise InvalidModelSelectionError(
            provider=normalized_provider,
            model=normalized_model,
        )
    normalized_class = _normalized_billing_class(billing_class)
    if normalized_class not in ALLOWED_MODEL_BILLING_CLASSES:
        raise BillingConfigurationError("A model is missing a valid subscription billing class")
    return ModelTargetIntent(
        provider=normalized_provider,
        model=normalized_model,
        billing_class=normalized_class,
    )


def _normalized_billing_class(value: object) -> str:
    normalized = getattr(value, "value", value)
    return str(normalized or "").strip().lower()


def _validate_target(target: ModelTargetIntent) -> ModelTargetIntent:
    provider = str(target.provider or "").strip().lower()
    model = str(target.model or "").strip()
    billing_class = _normalized_billing_class(target.billing_class)
    if not provider or not model:
        raise BillingConfigurationError("A billable model target is incomplete")
    if billing_class not in ALLOWED_MODEL_BILLING_CLASSES:
        raise BillingConfigurationError("A model is missing a valid subscription billing class")
    return ModelTargetIntent(
        provider=provider,
        model=model,
        billing_class=billing_class,
    )


def _smart_reservation_target(
    effective: EffectiveSubscription,
    targets: Sequence[ModelTargetIntent],
) -> ModelTargetIntent:
    allowed = effective.plan.entitlements.allowed_billing_classes
    if not allowed or any(item not in _BILLING_CLASS_RANK for item in allowed):
        raise BillingConfigurationError("The plan has no valid Smart routing billing classes")
    highest = max(allowed, key=_BILLING_CLASS_RANK.__getitem__)
    preview = _validate_target(targets[0]) if targets else None
    return ModelTargetIntent(
        provider=preview.provider if preview else "smart",
        model=preview.model if preview else "smart-routing-reservation",
        billing_class=highest,
    )


def _allowance_denial(
    error: UsageAllowanceExceededError,
    effective: EffectiveSubscription,
) -> EntitlementDenial:
    catalog = get_plan_catalog()
    recommended_plan = next(
        (
            plan.code
            for plan in catalog.list_plans()
            if plan.rank > effective.plan.rank
            and int(getattr(plan.allowances, error.meter)) > error.limit
        ),
        None,
    )
    return EntitlementDenial(
        code=error.code,
        message=str(error),
        meter=error.meter,
        current_plan=error.current_plan,
        recommended_plan=recommended_plan,
        used=error.used,
        limit=error.limit,
        remaining=error.remaining,
        reset_at=error.reset_at,
    )


def _smart_reservation_quantities(
    effective: EffectiveSubscription,
    required: Mapping[str, int],
) -> dict[str, int]:
    """Reserve every premium meter Smart may settle for one response.

    WP4 settlement cannot transfer a reservation between meter keys. Reserving
    the permitted premium envelope lets a Pro request reserve Ultra
    conservatively while still settling an Advanced fallback accurately.
    """
    quantities = dict(required)
    for billing_class in effective.plan.entitlements.allowed_billing_classes:
        meter = _PREMIUM_CLASS_METERS.get(billing_class)
        if meter is not None:
            quantities[meter] = max(1, quantities.get(meter, 0))
    return quantities


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
) -> ReservedRequestUsage:
    """Resolve plan, evaluate intent, and reserve all required units atomically."""
    effective = resolve_effective_subscription(db_session, user_id)
    normalized_targets = tuple(_validate_target(target) for target in model_targets)
    reservation_targets = (
        (_smart_reservation_target(effective, normalized_targets),)
        if smart_routing
        else normalized_targets
    )
    intent = SubscriptionRequestIntent(
        operation_type=operation_type,
        model_targets=reservation_targets,
        research_enabled=research_enabled,
        optimization_enabled=optimization_enabled,
        attachment_count=attachment_count,
        total_attachment_bytes=total_attachment_bytes,
        attachment_sizes=tuple(attachment_sizes),
    )
    allowances = load_allowance_usage(db_session, effective)
    decision = evaluate_entitlement(effective, intent, allowances)
    if not decision.allowed:
        if decision.denial is None:
            raise BillingConfigurationError("Subscription access was denied without a reason")
        raise EntitlementDeniedError(decision.denial)

    requested_quantities = (
        _smart_reservation_quantities(effective, decision.required_quantities)
        if smart_routing
        else dict(decision.required_quantities)
    )

    try:
        reservation = reserve_usage(
            db_session,
            effective_subscription=effective,
            request_id=request_id,
            operation_type=operation_type,
            requested_quantities=requested_quantities,
        )
    except UsageAllowanceExceededError as exc:
        # The atomic reservation remains authoritative if another request used
        # the allowance after the optimistic entitlement snapshot was loaded.
        raise EntitlementDeniedError(_allowance_denial(exc, effective)) from exc

    return ReservedRequestUsage(
        reservation_id=reservation.id,
        request_id=request_id,
        operation_type=operation_type,
        requested_quantities=dict(reservation.requested_quantities),
        allowed_billing_classes=effective.plan.entitlements.allowed_billing_classes,
        current_plan=effective.plan.code,
        reset_at=effective.current_period_end,
    )


def finalize_reserved_usage(
    db_session: Session,
    *,
    reservation: ReservedRequestUsage,
    successful_targets: Sequence[ModelTargetIntent],
    research_performed: bool,
    optimization_performed: bool = False,
    file_analysis_performed: bool = False,
    uploaded_bytes: int = 0,
    release_reason: str = "provider_failed_before_billable_output",
) -> None:
    """Settle successful units and release every failed or unused unit."""
    if uploaded_bytes < 0:
        raise BillingConfigurationError("Successful uploaded bytes cannot be negative")
    normalized_targets = tuple(_validate_target(target) for target in successful_targets)
    successful_intent = SubscriptionRequestIntent(
        operation_type=reservation.operation_type,
        model_targets=normalized_targets,
        research_enabled=research_performed,
        optimization_enabled=optimization_performed,
        attachment_count=1 if file_analysis_performed else 0,
        total_attachment_bytes=uploaded_bytes,
    )
    quantities = required_quantities(successful_intent)
    if not quantities:
        release_usage(
            db_session,
            reservation_id=reservation.reservation_id,
            reason=release_reason,
        )
        return

    for meter, quantity in quantities.items():
        if quantity > int(reservation.requested_quantities.get(meter, 0)):
            raise BillingConfigurationError(
                f"Successful {meter} usage exceeds the authorized reservation"
            )
    settle_usage(
        db_session,
        reservation_id=reservation.reservation_id,
        successful_quantities=quantities,
        settlement_metadata={
            "successful_targets": [
                {"provider": target.provider, "model": target.model}
                for target in normalized_targets
            ],
            "research_performed": research_performed,
            "optimization_performed": optimization_performed,
            "file_analysis_performed": file_analysis_performed,
            "uploaded_bytes": uploaded_bytes,
        },
    )


def release_reserved_usage(
    db_session: Session,
    *,
    reservation: ReservedRequestUsage,
    reason: str,
) -> None:
    """Release a reservation when execution exits before finalization."""
    release_usage(
        db_session,
        reservation_id=reservation.reservation_id,
        reason=reason,
    )
