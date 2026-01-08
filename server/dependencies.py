"""FastAPI dependencies for authentication and orchestrator access."""

import os
from fastapi import Header, HTTPException, status
from typing import Optional


async def get_api_key(x_api_key: Optional[str] = Header(None)):
    """Validate API key from X-API-Key header."""
    valid_keys_str = os.getenv("API_KEYS", "")
    if not valid_keys_str:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="API authentication not configured"
        )

    valid_keys = [k.strip() for k in valid_keys_str.split(",") if k.strip()]

    if not x_api_key or x_api_key not in valid_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key"
        )

    return x_api_key


def get_orchestrator():
    """Dependency to get orchestrator instance (singleton pattern)."""
    from orchestrator.core import CortexOrchestrator
    if not hasattr(get_orchestrator, "_instance"):
        get_orchestrator._instance = CortexOrchestrator()
    return get_orchestrator._instance
