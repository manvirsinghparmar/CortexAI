"""Admin/debug endpoints for DB-backed request diagnostics."""

from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query, Request

from server import persistence as persistence_service
from server.dependencies import get_auth
from server.schemas.responses import FailedAttemptDTO, FailedAttemptsByGroupDTO

router = APIRouter(prefix="/v1/admin", tags=["Admin"])

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_get_failed_attempts_by_request_group = persistence_service.get_failed_attempts_by_request_group


@router.get(
    "/request-groups/{request_group_id}/failed-attempts",
    response_model=FailedAttemptsByGroupDTO,
)
async def get_failed_attempts(
    request_group_id: UUID,
    request: Request,
    limit: int = Query(default=100, ge=1, le=500),
    auth=Depends(get_auth),
):
    """
    Return failed routing attempts for one compare request_group_id.

    The result is always scoped to the authenticated key owner.
    """
    if not API_DB_ENABLED:
        return FailedAttemptsByGroupDTO(
            request_group_id=str(request_group_id),
            count=0,
            items=[],
        )

    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    rows = _get_failed_attempts_by_request_group(
        auth=auth,
        request_id=req_id,
        request_group_id=request_group_id,
        limit=limit,
    )

    items = [FailedAttemptDTO(**row) for row in rows]
    return FailedAttemptsByGroupDTO(
        request_group_id=str(request_group_id),
        count=len(items),
        items=items,
    )
