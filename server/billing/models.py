"""Immutable subscription plan value objects."""

from dataclasses import dataclass
from decimal import Decimal
from enum import Enum


class ModelBillingClass(str, Enum):
    """Consumer billing classification, independent of smart-routing tiers."""

    STANDARD = "standard"
    ADVANCED = "advanced"
    ULTRA = "ultra"


ALLOWED_MODEL_BILLING_CLASSES = frozenset(item.value for item in ModelBillingClass)


@dataclass(frozen=True)
class PlanAllowances:
    model_responses: int
    advanced_model_responses: int
    ultra_model_responses: int
    research_turns: int
    optimization_turns: int
    file_analysis_turns: int
    uploaded_bytes: int


@dataclass(frozen=True)
class PlanLimits:
    requests_per_minute: int
    max_files_per_request: int
    max_file_bytes: int


@dataclass(frozen=True)
class PlanEntitlements:
    compare_enabled: bool
    max_compare_models: int
    research_enabled: bool
    prompt_improvement_enabled: bool
    file_analysis_enabled: bool
    usage_export_enabled: bool
    saved_history_enabled: bool
    models_catalog_enabled: bool
    allowed_billing_classes: frozenset[str]


@dataclass(frozen=True)
class SubscriptionPlan:
    code: str
    display_name: str
    rank: int
    monthly_price_usd: Decimal
    stripe_price_env: str | None
    entitlements: PlanEntitlements
    allowances: PlanAllowances
    limits: PlanLimits
