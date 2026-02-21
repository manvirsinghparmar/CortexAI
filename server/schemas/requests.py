"""Pydantic request models for FastAPI endpoints."""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List


class ConversationHistoryItem(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class UserContextRequest(BaseModel):
    session_id: Optional[str] = None
    conversation_history: Optional[List[ConversationHistoryItem]] = None


class ChatRoutingRequest(BaseModel):
    smart_mode: bool = True
    research_mode: bool = False


class ChatRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    provider: Optional[str] = Field(None, pattern="^(openai|gemini|deepseek|grok)$")
    model: Optional[str] = None
    context: Optional[UserContextRequest] = None
    routing: Optional[ChatRoutingRequest] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)

    @model_validator(mode="after")
    def validate_provider_model_pair(self):
        if self.model and not self.provider:
            raise ValueError("provider is required when model is provided")
        return self


class CompareTargetRequest(BaseModel):
    provider: str = Field(..., pattern="^(openai|gemini|deepseek|grok)$")
    model: Optional[str] = None


class CompareRequest(BaseModel):
    prompt: str = Field(..., min_length=1)
    targets: List[CompareTargetRequest] = Field(..., min_length=2, max_length=4)
    routing: Optional[ChatRoutingRequest] = None
    context: Optional[UserContextRequest] = None
    timeout_s: Optional[float] = Field(None, gt=0, le=300)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, gt=0)
