"""Pydantic response models (DTOs) for FastAPI endpoints."""

from typing import Any

from pydantic import BaseModel, Field


class TokenUsageDTO(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ErrorDTO(BaseModel):
    code: str
    message: str
    provider: str
    retryable: bool
    details: dict[str, Any] = Field(default_factory=dict)


class ChatResponseDTO(BaseModel):
    request_id: str
    text: str
    provider: str
    model: str
    latency_ms: int
    token_usage: TokenUsageDTO
    estimated_cost: float
    cost_currency: str = "USD"
    finish_reason: str | None = None
    error: ErrorDTO | None = None
    timestamp: str
    research_used: bool = False
    sources: list[dict[str, Any]] = Field(default_factory=list)
    research_error: str | None = None

    @classmethod
    def from_unified_response(cls, ur):
        """Convert UnifiedResponse to DTO."""
        # Extract research metadata (handle None case)
        md = ur.metadata or {}

        return cls(
            request_id=ur.request_id,
            text=ur.text,
            provider=ur.provider,
            model=ur.model,
            latency_ms=ur.latency_ms,
            token_usage=TokenUsageDTO(
                prompt_tokens=ur.token_usage.prompt_tokens,
                completion_tokens=ur.token_usage.completion_tokens,
                total_tokens=ur.token_usage.total_tokens,
            ),
            estimated_cost=ur.estimated_cost,
            cost_currency=ur.cost_currency,
            finish_reason=ur.finish_reason,
            error=(
                ErrorDTO(
                    code=ur.error.code,
                    message=ur.error.message,
                    provider=ur.error.provider,
                    retryable=ur.error.retryable,
                    details=ur.error.details,
                )
                if ur.error
                else None
            ),
            timestamp=ur.timestamp,
            research_used=md.get("research_used", False),
            sources=md.get("sources", []),
            research_error=md.get("research_error"),
        )


class CompareResponseDTO(BaseModel):
    request_group_id: str
    responses: list[ChatResponseDTO]
    success_count: int
    error_count: int
    total_tokens: int
    total_cost: float
    timestamp: str

    @classmethod
    def from_multi_unified_response(cls, mur):
        """Convert MultiUnifiedResponse to DTO."""
        return cls(
            request_group_id=mur.request_group_id,
            responses=[ChatResponseDTO.from_unified_response(r) for r in mur.responses],
            success_count=mur.success_count,
            error_count=mur.error_count,
            total_tokens=mur.total_tokens,
            total_cost=mur.total_cost,
            timestamp=mur.created_at.isoformat().replace("+00:00", "Z"),
        )


class HealthResponseDTO(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"
