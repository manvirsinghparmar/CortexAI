"""Browser-side diagnostics ingestion."""

from typing import Any

from fastapi import APIRouter, Request, Response, status

from server.schemas.requests import ClientDiagnosticsRequest
from utils.logger import get_logger

router = APIRouter(prefix="/v1", tags=["Diagnostics"])
logger = get_logger(__name__)


@router.post("/client-diagnostics", status_code=status.HTTP_204_NO_CONTENT)
async def client_diagnostics(payload: ClientDiagnosticsRequest, request: Request):
    """Accept non-sensitive browser lifecycle diagnostics.

    This endpoint is intentionally unauthenticated: the useful cases include
    reloads, auth redirects, tab discards, and render failures where auth state
    may be unavailable. The schema keeps payloads small and frontend code avoids
    prompt/response content.
    """
    user_agent = str(request.headers.get("user-agent", ""))[:240]
    client_host = request.client.host if request.client else ""
    for event in payload.events:
        logger.info(
            "frontend.diagnostic",
            extra={
                "extra_fields": {
                    "event": event.event,
                    "timestamp": event.timestamp,
                    "source": payload.source,
                    "reason": payload.reason or "",
                    "page_instance_id": event.page_instance_id
                    or payload.page_instance_id
                    or "",
                    "client_host": client_host,
                    "user_agent": user_agent,
                    "details": _trim_value(event.details),
                }
            },
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _trim_value(value: Any, depth: int = 0) -> Any:
    if depth > 3:
        return "[truncated]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value[:500]
    if isinstance(value, list):
        return [_trim_value(item, depth + 1) for item in value[:10]]
    if isinstance(value, dict):
        output: dict[str, Any] = {}
        for key, item in list(value.items())[:25]:
            output[str(key)[:80]] = _trim_value(item, depth + 1)
        return output
    return str(value)[:200]
