"""Pydantic response models (DTOs) for FastAPI endpoints."""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class TokenUsageDTO(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ErrorDTO(BaseModel):
    code: str
    message: str
    provider: str
    retryable: bool
    details: Dict[str, Any] = Field(default_factory=dict)


class ChatResponseDTO(BaseModel):
    request_id: str
    session_id: Optional[str] = None
    text: str
    provider: str
    model: str
    latency_ms: int
    token_usage: TokenUsageDTO
    estimated_cost: float
    cost_currency: str = "USD"
    finish_reason: Optional[str] = None
    error: Optional[ErrorDTO] = None
    web_source_items: List[Dict[str, str]] = Field(default_factory=list)
    timestamp: str

    @classmethod
    def from_unified_response(cls, ur, *, session_id: Optional[str] = None):
        """Convert UnifiedResponse to DTO."""
        metadata = ur.metadata if isinstance(getattr(ur, "metadata", None), dict) else {}
        source_candidates = metadata.get("web_source_items")
        if not isinstance(source_candidates, list):
            source_candidates = metadata.get("sources")

        normalized_sources: List[Dict[str, str]] = []
        seen_urls: set[str] = set()
        if isinstance(source_candidates, list):
            for item in source_candidates:
                if not isinstance(item, dict):
                    continue
                url = str(item.get("url") or "").strip()
                if not url:
                    continue
                normalized_url = url.lower()
                if normalized_url in seen_urls:
                    continue
                seen_urls.add(normalized_url)
                title = str(item.get("title") or "").strip() or url
                normalized_sources.append({"title": title, "url": url})
                if len(normalized_sources) >= 8:
                    break

        return cls(
            request_id=ur.request_id,
            session_id=session_id,
            text=ur.text,
            provider=ur.provider,
            model=ur.model,
            latency_ms=ur.latency_ms,
            token_usage=TokenUsageDTO(
                prompt_tokens=ur.token_usage.prompt_tokens,
                completion_tokens=ur.token_usage.completion_tokens,
                total_tokens=ur.token_usage.total_tokens
            ),
            estimated_cost=ur.estimated_cost,
            cost_currency=ur.cost_currency,
            finish_reason=ur.finish_reason,
            error=ErrorDTO(
                code=ur.error.code,
                message=ur.error.message,
                provider=ur.error.provider,
                retryable=ur.error.retryable,
                details=ur.error.details
            ) if ur.error else None,
            web_source_items=normalized_sources,
            timestamp=ur.timestamp
        )


class CompareResponseDTO(BaseModel):
    request_group_id: str
    session_id: Optional[str] = None
    responses: List[ChatResponseDTO]
    success_count: int
    error_count: int
    total_tokens: int
    total_cost: float
    timestamp: str

    @classmethod
    def from_multi_unified_response(cls, mur, *, session_id: Optional[str] = None):
        """Convert MultiUnifiedResponse to DTO."""
        return cls(
            request_group_id=mur.request_group_id,
            session_id=session_id,
            responses=[ChatResponseDTO.from_unified_response(r, session_id=session_id) for r in mur.responses],
            success_count=mur.success_count,
            error_count=mur.error_count,
            total_tokens=mur.total_tokens,
            total_cost=mur.total_cost,
            timestamp=mur.timestamp
        )


class HealthResponseDTO(BaseModel):
    status: str
    timestamp: str
    version: str = "1.0.0"


class ModelCatalogItemDTO(BaseModel):
    provider: str
    model: str
    tier: str
    input_cost_per_1m: float
    output_cost_per_1m: float
    context_limit: int
    tags: List[str] = Field(default_factory=list)
    enabled: bool
    supports_image_input: bool = False
    supported_attachment_mime_types: List[str] = Field(default_factory=list)
    max_attachment_bytes: Optional[int] = None
    max_attachments_per_request: Optional[int] = None


class ProviderCatalogItemDTO(BaseModel):
    provider: str
    label: str
    api_key_env: str
    default_model_env: str
    default_model: str
    byok_supported: bool
    capabilities: List[str] = Field(default_factory=list)
    ui: Dict[str, Any] = Field(default_factory=dict)
    model_count: int = 0
    enabled_model_count: int = 0


class ProvidersCatalogResponseDTO(BaseModel):
    providers: List[ProviderCatalogItemDTO] = Field(default_factory=list)
    total: int
    timestamp: str


class ModelsCatalogResponseDTO(BaseModel):
    provider: Optional[str] = None
    enabled_only: bool
    models: List[ModelCatalogItemDTO] = Field(default_factory=list)
    total: int
    timestamp: str


class FailedAttemptDTO(BaseModel):
    request_id: str
    request_group_id: str
    attempt_number: int
    tier: Optional[str] = None
    provider: Optional[str] = None
    model: Optional[str] = None
    validation: Optional[str] = None
    latency_ms: Optional[int] = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None


class FailedAttemptsByGroupDTO(BaseModel):
    request_group_id: str
    count: int
    items: List[FailedAttemptDTO] = Field(default_factory=list)


class UsageTotalsDTO(BaseModel):
    requests: int
    tokens: int
    cost: float


class UsageBucketDTO(BaseModel):
    bucket: str
    requests: int
    tokens: int
    cost: float


class UsageReportDTO(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    group_by: str
    totals: UsageTotalsDTO
    breakdown: List[UsageBucketDTO] = Field(default_factory=list)


class SavingsTotalsDTO(BaseModel):
    requests: int
    successful_requests: int = 0
    failed_requests: int = 0
    actual_cost: float
    baseline_cost: float
    savings_amount: float
    savings_pct: float


class SavingsBucketDTO(BaseModel):
    bucket: str
    requests: int
    successful_requests: int = 0
    failed_requests: int = 0
    actual_cost: float
    baseline_cost: float
    savings_amount: float
    savings_pct: float


class SavingsReportDTO(BaseModel):
    from_date: Optional[str] = None
    to_date: Optional[str] = None
    group_by: str
    totals: SavingsTotalsDTO
    breakdown: List[SavingsBucketDTO] = Field(default_factory=list)


class ByokProviderStatusDTO(BaseModel):
    provider: str
    configured: bool
    key_last4: Optional[str] = None
    fingerprint_prefix: Optional[str] = None
    updated_at: Optional[str] = None


class ByokStatusDTO(BaseModel):
    providers: List[ByokProviderStatusDTO] = Field(default_factory=list)
    baseline_provider: Optional[str] = None
    baseline_model: Optional[str] = None
    requests_per_minute: Optional[int] = None


class ByokUpdateResponseDTO(BaseModel):
    updated_providers: List[str] = Field(default_factory=list)
    baseline_provider: Optional[str] = None
    baseline_model: Optional[str] = None
    requests_per_minute: Optional[int] = None


class ByokDeleteResponseDTO(BaseModel):
    deleted_count: int


class WhoAmIBaselineDTO(BaseModel):
    provider: str
    model: str
    source: str


class WhoAmIRateLimitConfigDTO(BaseModel):
    requests_per_minute: int
    daily_cap_scope: str
    daily_token_cap: Optional[int] = None
    daily_cost_cap: Optional[float] = None


class WhoAmIBreakerConfigDTO(BaseModel):
    failure_threshold: int
    window_seconds: int
    cooldown_seconds: int
    scope: str


class WhoAmIResponseDTO(BaseModel):
    api_key_id: Optional[str] = None
    user_id: Optional[str] = None
    plan_tier: Optional[str] = None
    storage_policy: str
    redact_pii: bool
    baseline: WhoAmIBaselineDTO
    rate_limits: WhoAmIRateLimitConfigDTO
    breakers: WhoAmIBreakerConfigDTO


class FileBaseDTO(BaseModel):
    file_id: str
    original_filename: str
    mime_type: str
    size_bytes: int
    status: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    ingestion_meta: Dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: Optional[str] = None
    expires_at: Optional[str] = None


class FileUploadResponseDTO(FileBaseDTO):
    deduplicated: bool = False


class FileStatusResponseDTO(FileBaseDTO):
    deduplicated: bool = False
