from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Optional

FinishReason = Optional[Literal["stop", "length", "tool", "content_filter", "error"]]


@dataclass(frozen=True)
class TokenUsage:
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

    def __post_init__(self):
        if self.total_tokens == 0 and (self.prompt_tokens > 0 or self.completion_tokens > 0):
            object.__setattr__(self, "total_tokens", self.prompt_tokens + self.completion_tokens)


@dataclass(frozen=True)
class NormalizedError:
    code: str
    message: str
    provider: str
    retryable: bool = False
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        valid_codes = {"timeout", "auth", "rate_limit", "bad_request", "provider_error", "unknown"}
        if self.code not in valid_codes:
            object.__setattr__(self, "code", "unknown")


@dataclass(frozen=True)
class UnifiedResponse:
    request_id: str
    text: str
    provider: str
    model: str
    latency_ms: int
    token_usage: TokenUsage
    estimated_cost: float

    # NEW: routing/debugging/caching guardrails
    mode: str | None = None  # ask/compare/eval
    language: str | None = "en"  # requested/expected output language
    input_hash: str | None = None  # prompt hash for cache + dedupe
    attempt: int = 1  # fallback attempt counter
    fallback_from: str | None = None  # "openai:gpt-4.1" etc.

    finish_reason: FinishReason = None
    error: NormalizedError | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] | None = None

    cost_currency: str = "USD"
    pricing_version: str | None = None

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    def __post_init__(self):
        valid_reasons = {"stop", "length", "tool", "content_filter", "error", None}
        if self.finish_reason not in valid_reasons:
            # preserve provider reason for debugging instead of dropping it silently
            md = dict(self.metadata)
            md.setdefault("provider_finish_reason", self.finish_reason)
            object.__setattr__(self, "metadata", md)
            object.__setattr__(self, "finish_reason", None)

    @property
    def is_success(self) -> bool:
        return self.error is None

    @property
    def is_error(self) -> bool:
        return self.error is not None

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "text": self.text if len(self.text) <= 200 else self.text[:200] + "...",
            "provider": self.provider,
            "model": self.model,
            "latency_ms": self.latency_ms,
            "token_usage": {
                "prompt_tokens": self.token_usage.prompt_tokens,
                "completion_tokens": self.token_usage.completion_tokens,
                "total_tokens": self.token_usage.total_tokens,
            },
            "estimated_cost": self.estimated_cost,
            "cost_currency": self.cost_currency,
            "pricing_version": self.pricing_version,
            "mode": self.mode,
            "language": self.language,
            "input_hash": self.input_hash,
            "attempt": self.attempt,
            "fallback_from": self.fallback_from,
            "finish_reason": self.finish_reason,
            "error": (
                {
                    "code": self.error.code,
                    "message": self.error.message,
                    "provider": self.error.provider,
                    "retryable": self.error.retryable,
                    "details": self.error.details,
                }
                if self.error
                else None
            ),
            "timestamp": self.timestamp,
        }


@dataclass(frozen=True)
class MultiUnifiedResponse:
    request_group_id: str
    prompt: str
    responses: list[UnifiedResponse]

    success_count: int
    error_count: int
    total_tokens: int
    total_cost: float

    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")

    @classmethod
    def from_responses(
        cls, request_group_id: str, prompt: str, responses: list[UnifiedResponse]
    ) -> "MultiUnifiedResponse":
        success_count = sum(1 for r in responses if r and r.is_success)
        error_count = len(responses) - success_count
        total_tokens = sum(
            (r.token_usage.total_tokens if r and r.token_usage else 0) for r in responses
        )
        total_cost = sum((r.estimated_cost if r else 0.0) for r in responses)

        return cls(
            request_group_id=request_group_id,
            prompt=prompt,
            responses=responses,
            success_count=success_count,
            error_count=error_count,
            total_tokens=total_tokens,
            total_cost=total_cost,
        )
