"""Chat endpoint for single AI model requests."""

import asyncio
import json
import os
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import StreamingResponse
from orchestrator.core import CortexOrchestrator
from models.user_context import UserContext
from server.schemas.requests import ChatRequest
from server.schemas.responses import ChatResponseDTO
from server.dependencies import get_api_key, get_orchestrator
from server.utils import validate_and_trim_context, clamp_max_tokens
from utils.web_research import maybe_enrich_prompt_with_web

router = APIRouter(prefix="/v1", tags=["Chat"])
STREAM_LINE_DELAY_S = 0.1

DEFAULT_MODELS = {
    "openai": "gpt-4o",
    "gemini": "gemini-2.5-flash",
    "deepseek": "deepseek-chat",
    "grok": "grok-4-latest",
}


def _default_model_for_provider(provider: str) -> str:
    env_key = f"DEFAULT_{provider.upper()}_MODEL"
    return os.getenv(env_key, DEFAULT_MODELS[provider])


def _pick_smart_provider(prompt: str, *, smart_mode: bool, research_mode: bool) -> str:
    text = (prompt or "").lower()

    if not smart_mode:
        return "gemini"

    if research_mode:
        return "openai"

    code_signals = (
        "code", "bug", "debug", "stack trace", "python", "javascript", "typescript",
        "sql", "api", "refactor", "algorithm", "function", "class ", "exception",
    )
    deep_reasoning_signals = (
        "analyze", "analysis", "tradeoff", "architecture", "design", "compare",
        "step by step", "explain why", "root cause", "research", "cite",
    )
    creative_signals = ("poem", "story", "creative", "brainstorm", "tagline", "tweet")

    if any(signal in text for signal in code_signals):
        return "deepseek"
    if any(signal in text for signal in deep_reasoning_signals) or len(text) > 900:
        return "openai"
    if any(signal in text for signal in creative_signals):
        return "grok"
    return "gemini"


def _resolve_chat_target(request: ChatRequest) -> tuple[str, str]:
    manual_provider = (request.provider or "").strip().lower()
    manual_model = (request.model or "").strip()

    if manual_provider:
        return manual_provider, (manual_model or _default_model_for_provider(manual_provider))

    routing = request.routing
    smart_mode = True if routing is None else bool(routing.smart_mode)
    research_mode = False if routing is None else bool(routing.research_mode)
    provider = _pick_smart_provider(
        request.prompt,
        smart_mode=smart_mode,
        research_mode=research_mode,
    )
    return provider, _default_model_for_provider(provider)


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


def _iter_stream_lines(text: str):
    """Split response text into line chunks while preserving newline boundaries."""
    if not text:
        return []
    lines = text.splitlines(keepends=True)
    if len(lines) <= 1:
        # If the model returns one long paragraph, chunk it for smoother streaming.
        chunk_size = 120
        return [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
    return lines


def _to_ndjson(event: dict) -> str:
    """Serialize one stream event as NDJSON."""
    return json.dumps(event, ensure_ascii=False) + "\n"


@router.post("/chat", response_model=ChatResponseDTO)
async def chat(
    request: ChatRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key)
):
    """Send a prompt to a single AI model and get a response."""
    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    routing = request.routing
    research_mode = bool(routing and routing.research_mode)
    effective_prompt, _research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )
    target_provider, target_model = _resolve_chat_target(request)

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)

    response = await asyncio.to_thread(
        orchestrator.ask,
        prompt=effective_prompt,
        model_type=target_provider,
        context=context,
        model_name=target_model,
        token_tracker=None,
        **kwargs
    )

    dto = ChatResponseDTO.from_unified_response(response)

    # Persist to history DB (best-effort — don't fail the request if it errors)
    try:
        from server.database import save_chat
        save_chat(
            prompt=request.prompt,
            provider=dto.provider,
            model=dto.model,
            response=dto.text,
            latency_ms=dto.latency_ms,
            tokens=dto.token_usage.total_tokens if dto.token_usage else None,
            cost=dto.estimated_cost,
            mode="chat",
        )
    except Exception:
        pass

    return dto


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    orchestrator: CortexOrchestrator = Depends(get_orchestrator),
    api_key: str = Depends(get_api_key)
):
    """Stream a single-model chat response as NDJSON events."""
    request.context = validate_and_trim_context(request.context)
    context = _build_user_context(request.context)
    routing = request.routing
    research_mode = bool(routing and routing.research_mode)
    effective_prompt, research_meta = await maybe_enrich_prompt_with_web(
        request.prompt,
        enabled=research_mode,
    )
    target_provider, target_model = _resolve_chat_target(request)

    kwargs = {}
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = clamp_max_tokens(request.max_tokens)

    async def event_stream():
        yield _to_ndjson({
            "type": "start",
            "mode": "chat",
            "provider": target_provider,
            "model": target_model,
            "research_mode": research_mode,
            "web_sources": research_meta.get("source_count", 0),
            "web_source_items": research_meta.get("sources", []),
        })

        try:
            response = await asyncio.to_thread(
                orchestrator.ask,
                prompt=effective_prompt,
                model_type=target_provider,
                context=context,
                model_name=target_model,
                token_tracker=None,
                **kwargs
            )

            dto = ChatResponseDTO.from_unified_response(response)
            stream_text = dto.text or ""
            if not stream_text and dto.error:
                stream_text = f"Error: {dto.error.message}"

            for line in _iter_stream_lines(stream_text):
                yield _to_ndjson({"type": "line", "index": 0, "text": line})
                await asyncio.sleep(STREAM_LINE_DELAY_S)

            yield _to_ndjson({
                "type": "response_done",
                "index": 0,
                "response": jsonable_encoder(dto),
            })
            yield _to_ndjson({"type": "done", "mode": "chat"})

            # Persist to history DB (best-effort — don't fail stream if it errors)
            try:
                from server.database import save_chat
                save_chat(
                    prompt=request.prompt,
                    provider=dto.provider,
                    model=dto.model,
                    response=dto.text,
                    latency_ms=dto.latency_ms,
                    tokens=dto.token_usage.total_tokens if dto.token_usage else None,
                    cost=dto.estimated_cost,
                    mode="chat",
                )
            except Exception:
                pass

        except Exception as exc:
            yield _to_ndjson({"type": "error", "message": str(exc)})

    return StreamingResponse(
        event_stream(),
        media_type="application/x-ndjson",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
