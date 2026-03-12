"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter

from server.runtime_checks import check_claude_runtime
from server.schemas.responses import HealthResponseDTO

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponseDTO)
async def health_check():
    """Health check endpoint."""
    return HealthResponseDTO(
        status="healthy", timestamp=datetime.utcnow().isoformat() + "Z", version="1.0.0"
    )


@router.get("/health/runtime")
async def runtime_health_check():
    """Runtime diagnostics for interpreter and Claude readiness."""
    check = check_claude_runtime()
    return {
        "status": "healthy" if check.ready else "degraded",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "python_executable": check.python_executable,
        "claude": {
            "sdk_module": check.sdk_module,
            "sdk_available": check.sdk_available,
            "api_key_env": check.api_key_env,
            "api_key_present": check.api_key_present,
        },
    }
