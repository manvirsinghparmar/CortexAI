"""Pydantic request models for FastAPI endpoints."""

from pydantic import BaseModel, Field


class ConversationHistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class UserContextRequest(BaseModel):
    session_id: str | None = None
    conversation_history: list[ConversationHistoryItem] | None = None


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    provider: str | None = Field(None, pattern="^(openai|gemini|deepseek|grok)$")
    model: str | None = None
    context: UserContextRequest | None = None
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    research_mode: str | None = Field("auto", pattern="^(off|auto|on)$")
    routing_mode: str | None = Field("smart", pattern="^(smart|cheap|strong)$")
    routing_constraints: dict | None = None


class CompareTargetRequest(BaseModel):
    provider: str = Field(..., pattern="^(openai|gemini|deepseek|grok)$")
    model: str | None = None


class CompareRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    targets: list[CompareTargetRequest] = Field(..., min_length=2, max_length=4)
    context: UserContextRequest | None = None
    timeout_s: float | None = Field(None, gt=0, le=300)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, gt=0)
    research_mode: str | None = Field("auto", pattern="^(off|auto|on)$")
