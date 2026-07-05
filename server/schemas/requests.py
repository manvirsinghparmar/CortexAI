"""Pydantic request models for FastAPI endpoints."""

from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from config.provider_catalog import get_provider_ids


def _supported_provider_ids() -> tuple[str, ...]:
    return tuple(get_provider_ids())


def _supported_provider_set() -> set[str]:
    return set(_supported_provider_ids())


def _validate_provider(provider: str, *, field_name: str) -> str:
    value = str(provider or "")
    allowed = _supported_provider_set()
    if value not in allowed:
        allowed_text = ", ".join(sorted(allowed))
        raise ValueError(
            f"Unsupported {field_name} '{value}'. Supported providers: {allowed_text}"
        )
    return value


class ConversationHistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class UserContextRequest(BaseModel):
    session_id: Optional[str] = None
    conversation_history: Optional[List[ConversationHistoryItem]] = None
    new_session: bool = False


class ChatRoutingRequest(BaseModel):
    smart_mode: bool = True
    research_mode: bool = False


class AttachmentRequestItem(BaseModel):
    file_id: UUID
    usage_role: str = Field("primary", pattern="^(primary|reference)$")
    transform_mode: str = Field(
        "auto",
        pattern="^(auto|text_only|vision_pages|table_summary)$",
    )


class ChatRequest(BaseModel):
    prompt: str = Field("", min_length=0)
    provider: Optional[str] = None
    model: Optional[str] = None
    context: Optional[UserContextRequest] = None
    routing: Optional[ChatRoutingRequest] = None
    attachments: Optional[List[AttachmentRequestItem]] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_provider(value, field_name="provider")

    @model_validator(mode="after")
    def validate_provider_model_pair(self):
        if self.model and not self.provider:
            raise ValueError("provider is required when model is provided")
        has_prompt = bool(str(self.prompt or "").strip())
        has_attachments = bool(self.attachments)
        if not has_prompt and not has_attachments:
            raise ValueError("prompt is required when attachments are not provided")
        return self


class CompareTargetRequest(BaseModel):
    provider: str
    model: Optional[str] = None

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, value: str) -> str:
        return _validate_provider(value, field_name="provider")


class CompareRequest(BaseModel):
    prompt: str = Field("", min_length=0)
    targets: List[CompareTargetRequest] = Field(..., min_length=2, max_length=4)
    routing: Optional[ChatRoutingRequest] = None
    context: Optional[UserContextRequest] = None
    attachments: Optional[List[AttachmentRequestItem]] = None
    timeout_s: Optional[float] = Field(None, gt=0, le=300)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)

    @model_validator(mode="after")
    def validate_prompt_or_attachments(self):
        has_prompt = bool(str(self.prompt or "").strip())
        has_attachments = bool(self.attachments)
        if not has_prompt and not has_attachments:
            raise ValueError("prompt is required when attachments are not provided")
        return self


class ClientDiagnosticEvent(BaseModel):
    event: str = Field(..., min_length=1, max_length=64)
    timestamp: str = Field(..., min_length=1, max_length=64)
    page_instance_id: Optional[str] = Field(None, max_length=96)
    details: Dict[str, Any] = Field(default_factory=dict)


class ClientDiagnosticsRequest(BaseModel):
    source: str = Field("react", max_length=32)
    reason: Optional[str] = Field(None, max_length=64)
    page_instance_id: Optional[str] = Field(None, max_length=96)
    events: List[ClientDiagnosticEvent] = Field(default_factory=list, max_length=50)


class ByokUpdateRequest(BaseModel):
    provider_keys: Dict[str, str] = Field(default_factory=dict)
    baseline_provider: Optional[str] = None
    baseline_model: Optional[str] = None
    requests_per_minute: Optional[int] = Field(None, ge=1, le=10000)

    @field_validator("baseline_provider")
    @classmethod
    def validate_baseline_provider(cls, value: str | None) -> str | None:
        if value is None:
            return value
        return _validate_provider(value, field_name="baseline_provider")

    @model_validator(mode="after")
    def validate_payload(self):
        if (
            not self.provider_keys
            and self.baseline_provider is None
            and self.baseline_model is None
            and self.requests_per_minute is None
        ):
            raise ValueError(
                "Provide at least one of provider_keys, baseline_provider/baseline_model, or requests_per_minute"
            )

        if self.baseline_model and not self.baseline_provider:
            raise ValueError("baseline_provider is required when baseline_model is provided")
        return self
