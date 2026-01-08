"""Compare endpoint for multi-model requests."""

import asyncio
from fastapi import APIRouter, Depends, HTTPException, status
from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext
from server.schemas.requests import CompareRequest
from server.schemas.responses import CompareResponseDTO
from server.dependencies import get_api_key, get_orchestrator
from utils.logger import get_logger

router = APIRouter(prefix="/v1", tags=["Compare"])
logger = get_logger(__name__)

MAX_COMPARE_TARGETS = 4


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


@router.post("/compare", response_model=CompareResponseDTO)
async def compare(
    request: CompareRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key)
):
    """Send a prompt to multiple AI models and compare responses."""
    if len(request.targets) > MAX_COMPARE_TARGETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum {MAX_COMPARE_TARGETS} targets allowed"
        )

    try:
        context = _build_user_context(request.context)

        models_list = [
            {"provider": t.provider, "model": t.model or ""}
            for t in request.targets
        ]

        kwargs = {}
        if request.temperature is not None:
            kwargs["temperature"] = request.temperature
        if request.max_tokens is not None:
            kwargs["max_tokens"] = request.max_tokens

        response = await asyncio.to_thread(
            orchestrator.compare,
            prompt=request.prompt,
            models_list=models_list,
            context=context,
            timeout_s=request.timeout_s,
            token_tracker=None,
            **kwargs
        )

        return CompareResponseDTO.from_multi_unified_response(response)

    except Exception as e:
        logger.exception("Compare endpoint error")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error: {str(e)}"
        )
