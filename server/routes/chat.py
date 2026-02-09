"""Chat endpoint for single AI model requests."""

import asyncio

from fastapi import APIRouter, Depends

from models.user_context import UserContext
from orchestrator.core import CortexOrchestrator
from server.dependencies import get_api_key, get_orchestrator
from server.schemas.requests import ChatRequest
from server.schemas.responses import ChatResponseDTO
from server.utils import clamp_max_tokens, validate_and_trim_context

router = APIRouter(prefix="/v1", tags=["Chat"])


def _build_user_context(context_req):
    """Convert request context to UserContext dataclass."""
    if not context_req:
        return None

    history = []
    if context_req.conversation_history:
        history = [
            {"role": item.role, "content": item.content}
            for item in context_req.conversation_history
        ]

    return UserContext(session_id=context_req.session_id, conversation_history=history)


@router.post("/chat", response_model=ChatResponseDTO)
async def chat(
    request: ChatRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key),
):
    """Send a prompt to a single AI model and get a response."""
    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)

    response = await asyncio.to_thread(
        orchestrator.ask,
        prompt=request.prompt,
        model_type=request.provider,
        context=context,
        model_name=request.model,
        token_tracker=None,
        research_mode=request.research_mode,
        **kwargs,
    )

    return ChatResponseDTO.from_unified_response(response)
