from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Tier(str, Enum):
    T0 = "T0"
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


@dataclass(frozen=True)
class PromptFeatures:
    word_count: int
    char_count: int
    token_estimate: int
    has_code: bool
    has_math: bool
    has_analysis: bool
    has_creative: bool
    has_factual: bool
    strict_format: bool
    has_logs_stacktrace: bool
    context_token_estimate: int
    context_messages: int
    is_follow_up: bool
    needs_latest_info: bool
    needs_accuracy: bool
    intent: str  # "rewrite"|"summarize"|"bullets"|"brainstorm"|"code"|"analysis"|"general"
    has_strict_constraints: bool


@dataclass(frozen=True)
class TierDecision:
    tier: Tier
    reasons: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class RoutingConstraints:
    max_cost_usd: float | None = None
    max_total_latency_ms: int | None = None
    preferred_provider: str | None = None
    allowed_providers: list[str] | None = None
    min_context_limit: int | None = None
    json_only: bool = False
    strict_format: bool = False


@dataclass(frozen=True)
class ModelCandidate:
    provider: str
    model_name: str
    tier: Tier
    input_cost_per_1m: float
    output_cost_per_1m: float
    context_limit: int
    tags: list[str]
    enabled: bool = True


@dataclass(frozen=True)
class SelectionResult:
    primary_candidate: ModelCandidate
    fallback_candidates: list[ModelCandidate]


@dataclass(frozen=True)
class ValidationResult:
    ok: bool
    reason: str = "ok"
    severity: str = "none"


class NextAction(str, Enum):
    RETRY_SAME_TIER = "retry_same_tier"
    ESCALATE_TIER = "escalate_tier"
    STOP = "stop"


@dataclass(frozen=True)
class FallbackDecision:
    action: NextAction
    next_tier: Tier | None
    reason: str
