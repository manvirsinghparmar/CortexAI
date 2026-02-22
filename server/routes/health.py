"""Health check endpoint."""

from datetime import datetime

from fastapi import APIRouter

from server.schemas.responses import HealthResponseDTO

router = APIRouter(tags=["Health"])


@router.get("/health", response_model=HealthResponseDTO)
async def health_check():
    """Health check endpoint."""
    return HealthResponseDTO(
        status="healthy", timestamp=datetime.utcnow().isoformat() + "Z", version="1.0.0"
    )
