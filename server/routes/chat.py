"""Chat endpoint for single AI model requests."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext
from server.schemas.requests import ChatRequest
from server.schemas.responses import ChatResponseDTO
from server.dependencies import get_api_key, get_orchestrator
from utils.logger import get_logger

router = APIRouter(prefix="/v1", tags=["Chat"])
logger = get_logger(__name__)


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

    return UserContext(
        session_id=context_req.session_id,
        conversation_history=history
    )


@router.post("/chat", response_model=ChatResponseDTO)
async def chat(
    request: ChatRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key)
):
    """Send a prompt to a single AI model and get a response."""
    try:
        context = _build_user_context(request.context)

        kwargs = {}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        response = await asyncio.to_thread(
            orchestrator.ask,
            prompt=request.prompt,
            model_type=request.provider,
            context=context,
            model_name=request.model,
            token_tracker=None,
            **kwargs
        )

        return ChatResponseDTO.from_unified_response(response)

    except Exception as e:
        logger.exception("Chat endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
