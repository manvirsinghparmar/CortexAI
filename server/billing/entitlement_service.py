"""Plan entitlement evaluation and public allowance snapshots."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from functools import partial
from typing import Mapping

from sqlalchemy.orm import Session

from db.billing_repository import ALLOWED_USAGE_METERS, get_or_create_usage_counter
from server.billing.errors import BillingConfigurationError
from server.billing.models import ALLOWED_MODEL_BILLING_CLASSES, SubscriptionPlan
from server.billing.plan_catalog import PlanCatalog, get_plan_catalog
from server.billing.subscription_service import EffectiveSubscription

_MODEL_RESPONSE_OPERATIONS = frozenset({"ask", "compare", "regenerate", "follow_up"})
_ALLOWED_OPERATIONS = frozenset(
    {
        "ask",
        "compare",
        "regenerate",
        "follow_up",
        "optimize",
        "file_upload",
        "usage_export",
    }
)


@dataclass(frozen=True)
class ModelTargetIntent:
    provider: str
    model: str
    billing_class: str


@dataclass(frozen=True)
class SubscriptionRequestIntent:
    operation_type: str
    model_targets: tuple[ModelTargetIntent, ...] = ()
    research_enabled: bool = False
    optimization_enabled: bool = False
    attachment_count: int = 0
    total_attachment_bytes: int = 0
    attachment_sizes: tuple[int, ...] = ()


@dataclass(frozen=True)
class EntitlementDenial:
    code: str
    message: str
    feature: str | None = None
    meter: str | None = None
    model: str | None = None
    billing_class: str | None = None
    current_plan: str | None = None
    recommended_plan: str | None = None
    used: int | None = None
    limit: int | None = None
    remaining: int | None = None
    reset_at: datetime | None = None


@dataclass(frozen=True)
class EntitlementDecision:
    allowed: bool
    plan_code: str
    required_quantities: Mapping[str, int]
    denial: EntitlementDenial | None = None


@dataclass(frozen=True)
class AllowanceUsage:
    used: int
    reserved: int
    limit: int
    remaining: int


def _billing_class_value(value: object) -> str:
    normalized = getattr(value, "value", value)
    return str(normalized or "").strip().lower()


def _allowance_limit(plan: SubscriptionPlan, meter: str) -> int:
    if meter not in ALLOWED_USAGE_METERS:
        raise KeyError(f"Unknown allowance meter '{meter}'")
    return int(getattr(plan.allowances, meter))


def _plan_allows_billing_class(
    required_class: str,
    plan: SubscriptionPlan,
) -> bool:
    return required_class in plan.entitlements.allowed_billing_classes


def _plan_has_larger_allowance(
    meter: str,
    current_limit: int,
    plan: SubscriptionPlan,
) -> bool:
    return _allowance_limit(plan, meter) > current_limit


def load_allowance_usage(
    db: Session,
    effective: EffectiveSubscription,
) -> dict[str, AllowanceUsage]:
    """Ensure and return every plan counter for the effective usage period."""
    result: dict[str, AllowanceUsage] = {}
    try:
        for meter in sorted(ALLOWED_USAGE_METERS):
            record = get_or_create_usage_counter(db, effective.usage_period_id, meter)
            used = max(0, int(record.get("used_quantity") or 0))
            reserved = max(0, int(record.get("reserved_quantity") or 0))
            limit = _allowance_limit(effective.plan, meter)
            result[meter] = AllowanceUsage(
                used=used,
                reserved=reserved,
                limit=limit,
                remaining=max(0, limit - used - reserved),
            )
    except Exception as exc:
        raise BillingConfigurationError("Allowance counters could not be resolved") from exc
    return result


def required_quantities(intent: SubscriptionRequestIntent) -> dict[str, int]:
    """Translate a request into subscription allowance units."""
    quantities: dict[str, int] = {}

    if intent.operation_type in _MODEL_RESPONSE_OPERATIONS and intent.model_targets:
        quantities["model_responses"] = len(intent.model_targets)

    advanced = sum(
        1
        for target in intent.model_targets
        if _billing_class_value(target.billing_class) == "advanced"
    )
    ultra = sum(
        1
        for target in intent.model_targets
        if _billing_class_value(target.billing_class) == "ultra"
    )
    if advanced:
        quantities["advanced_model_responses"] = advanced
    if ultra:
        quantities["ultra_model_responses"] = ultra
    if intent.research_enabled:
        quantities["research_turns"] = 1
    if intent.optimization_enabled or intent.operation_type == "optimize":
        quantities["optimization_turns"] = 1
    if intent.attachment_count > 0 and intent.operation_type != "file_upload":
        quantities["file_analysis_turns"] = 1
    if intent.operation_type == "file_upload" and intent.total_attachment_bytes > 0:
        quantities["uploaded_bytes"] = intent.total_attachment_bytes
    return quantities


def _recommended_upgrade(
    current: SubscriptionPlan,
    predicate: Callable[[SubscriptionPlan], bool],
    catalog: PlanCatalog,
) -> str | None:
    for plan in catalog.list_plans():
        if plan.rank > current.rank and predicate(plan):
            return plan.code
    return None


def _feature_denial(
    effective: EffectiveSubscription,
    *,
    feature: str,
    message: str,
    predicate: Callable[[SubscriptionPlan], bool],
    catalog: PlanCatalog,
) -> EntitlementDecision:
    return EntitlementDecision(
        allowed=False,
        plan_code=effective.plan.code,
        required_quantities={},
        denial=EntitlementDenial(
            code="feature_not_in_plan",
            message=message,
            feature=feature,
            current_plan=effective.plan.code,
            recommended_plan=_recommended_upgrade(effective.plan, predicate, catalog),
            reset_at=effective.current_period_end,
        ),
    )


def _configuration_denial(
    effective: EffectiveSubscription,
    message: str,
) -> EntitlementDecision:
    return EntitlementDecision(
        allowed=False,
        plan_code=effective.plan.code,
        required_quantities={},
        denial=EntitlementDenial(
            code="subscription_configuration_error",
            message=message,
            current_plan=effective.plan.code,
            reset_at=effective.current_period_end,
        ),
    )


def evaluate_entitlement(
    effective: EffectiveSubscription,
    intent: SubscriptionRequestIntent,
    allowances: Mapping[str, AllowanceUsage],
    *,
    catalog: PlanCatalog | None = None,
) -> EntitlementDecision:
    """Evaluate feature, model, file, and monthly allowance access.

    Existing operational rate limits and safety checks remain separate. The
    returned quantities are intended for WP4's future atomic reservation step.
    """
    plan_catalog = catalog or get_plan_catalog()
    plan = effective.plan
    operation = str(intent.operation_type or "").strip().lower()
    if operation not in _ALLOWED_OPERATIONS:
        return _configuration_denial(effective, "Unknown subscription operation type.")
    if intent.attachment_count < 0 or intent.total_attachment_bytes < 0:
        return _configuration_denial(effective, "Attachment quantities cannot be negative.")
    if any(size < 0 for size in intent.attachment_sizes):
        return _configuration_denial(effective, "Attachment sizes cannot be negative.")

    entitlements = plan.entitlements
    if operation == "compare" and not entitlements.compare_enabled:
        return _feature_denial(
            effective,
            feature="compare",
            message=f"Compare is not available on the {plan.display_name} plan.",
            predicate=lambda candidate: candidate.entitlements.compare_enabled,
            catalog=plan_catalog,
        )
    if intent.research_enabled and not entitlements.research_enabled:
        return _feature_denial(
            effective,
            feature="research",
            message=f"Research is not available on the {plan.display_name} plan.",
            predicate=lambda candidate: candidate.entitlements.research_enabled,
            catalog=plan_catalog,
        )
    if (intent.optimization_enabled or operation == "optimize") and not (
        entitlements.prompt_improvement_enabled
    ):
        return _feature_denial(
            effective,
            feature="prompt_improvement",
            message=f"Prompt improvement is not available on the {plan.display_name} plan.",
            predicate=lambda candidate: candidate.entitlements.prompt_improvement_enabled,
            catalog=plan_catalog,
        )
    if (intent.attachment_count > 0 or operation == "file_upload") and not (
        entitlements.file_analysis_enabled
    ):
        return _feature_denial(
            effective,
            feature="file_analysis",
            message=f"File analysis is not available on the {plan.display_name} plan.",
            predicate=lambda candidate: candidate.entitlements.file_analysis_enabled,
            catalog=plan_catalog,
        )
    if operation == "usage_export" and not entitlements.usage_export_enabled:
        return _feature_denial(
            effective,
            feature="usage_export",
            message=f"Usage export is not available on the {plan.display_name} plan.",
            predicate=lambda candidate: candidate.entitlements.usage_export_enabled,
            catalog=plan_catalog,
        )

    if operation == "compare" and len(intent.model_targets) > entitlements.max_compare_models:
        requested = len(intent.model_targets)
        return _feature_denial(
            effective,
            feature="compare_model_count",
            message=(
                f"The {plan.display_name} plan supports up to "
                f"{entitlements.max_compare_models} Compare models."
            ),
            predicate=lambda candidate: (
                candidate.entitlements.compare_enabled
                and candidate.entitlements.max_compare_models >= requested
            ),
            catalog=plan_catalog,
        )

    for target in intent.model_targets:
        billing_class = _billing_class_value(target.billing_class)
        if billing_class not in ALLOWED_MODEL_BILLING_CLASSES:
            return _configuration_denial(
                effective,
                "The selected model is missing a valid subscription billing class.",
            )
        if billing_class not in entitlements.allowed_billing_classes:
            recommended = _recommended_upgrade(
                plan,
                partial(_plan_allows_billing_class, billing_class),
                plan_catalog,
            )
            return EntitlementDecision(
                allowed=False,
                plan_code=plan.code,
                required_quantities={},
                denial=EntitlementDenial(
                    code="model_not_in_plan",
                    message=(f"{target.model} is not available on the {plan.display_name} plan."),
                    model=target.model,
                    billing_class=billing_class,
                    current_plan=plan.code,
                    recommended_plan=recommended,
                    reset_at=effective.current_period_end,
                ),
            )

    if intent.attachment_count > plan.limits.max_files_per_request:
        requested = intent.attachment_count
        return _feature_denial(
            effective,
            feature="attachment_count",
            message=(
                f"The {plan.display_name} plan supports up to "
                f"{plan.limits.max_files_per_request} files per request."
            ),
            predicate=lambda candidate: candidate.limits.max_files_per_request >= requested,
            catalog=plan_catalog,
        )

    oversized = next(
        (size for size in intent.attachment_sizes if size > plan.limits.max_file_bytes),
        None,
    )
    if oversized is not None:
        return _feature_denial(
            effective,
            feature="attachment_size",
            message=(f"A selected file exceeds the {plan.display_name} plan's per-file limit."),
            predicate=lambda candidate: candidate.limits.max_file_bytes >= oversized,
            catalog=plan_catalog,
        )

    quantities = required_quantities(intent)
    for meter, quantity in quantities.items():
        current = allowances.get(meter)
        if current is None:
            return _configuration_denial(
                effective,
                f"The {meter} subscription counter is unavailable.",
            )
        if quantity > current.remaining:
            recommended = _recommended_upgrade(
                plan,
                partial(_plan_has_larger_allowance, meter, current.limit),
                plan_catalog,
            )
            return EntitlementDecision(
                allowed=False,
                plan_code=plan.code,
                required_quantities=quantities,
                denial=EntitlementDenial(
                    code="monthly_allowance_exhausted",
                    message=(
                        f"The {plan.display_name} plan's monthly {meter} allowance "
                        "has been exhausted."
                    ),
                    meter=meter,
                    current_plan=plan.code,
                    recommended_plan=recommended,
                    used=current.used,
                    limit=current.limit,
                    remaining=current.remaining,
                    reset_at=effective.current_period_end,
                ),
            )

    return EntitlementDecision(
        allowed=True,
        plan_code=plan.code,
        required_quantities=quantities,
        denial=None,
    )
