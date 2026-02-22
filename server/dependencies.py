"""FastAPI dependencies for authentication and orchestrator access."""

import os

from fastapi import Header, HTTPException, Request, status

from server.utils import redact_sensitive_headers
from utils.logger import get_logger

logger = get_logger(__name__)


async def get_api_key(request: Request, x_api_key: str | None = Header(None)):
    """Validate API key from X-API-Key header."""
    valid_keys_str = os.getenv("API_KEYS", "")
    request_id = getattr(request.state, "request_id", "unknown")
    redacted_headers = redact_sensitive_headers(dict(request.headers))

    if not valid_keys_str:
        logger.error(
            "API authentication not configured",
            extra={"extra_fields": {"request_id": request_id, "headers": redacted_headers}},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication not configured",
        )

    valid_keys = [k.strip() for k in valid_keys_str.split(",") if k.strip()]

    if not x_api_key or x_api_key not in valid_keys:
        logger.warning(
            "API authentication failed",
            extra={"extra_fields": {"request_id": request_id, "headers": redacted_headers}},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key"
        )

    return x_api_key


def get_orchestrator():
    """Dependency to get orchestrator instance (singleton pattern)."""
    from orchestrator.core import CortexOrchestrator

    if not hasattr(get_orchestrator, "_instance"):
        get_orchestrator._instance = CortexOrchestrator()
    return get_orchestrator._instance
