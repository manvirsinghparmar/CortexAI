"""BYOK management endpoints."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from server import byok_service
from server import persistence as persistence_service
from server.dependencies import get_api_key
from server.schemas.requests import ByokUpdateRequest
from server.schemas.responses import ByokDeleteResponseDTO, ByokStatusDTO, ByokUpdateResponseDTO

router = APIRouter(prefix="/v1", tags=["BYOK"])

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_resolve_api_key_for_request = persistence_service.resolve_api_key_for_request
_db_uow = persistence_service.db_uow


def _require_db_mode() -> None:
    if API_DB_ENABLED:
        return
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="BYOK management requires DATABASE_URL (DB mode).",
    )


def _require_api_key_id(api_key_id):
    if api_key_id is not None:
        return
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="BYOK management requires a mapped api_key_id.",
    )


def _map_value_error(exc: ValueError) -> HTTPException:
    message = str(exc)
    if "MASTER_KEY" in message:
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=message,
        )
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=message,
    )


@router.post("/byok", response_model=ByokUpdateResponseDTO)
async def set_byok(
    request: Request,
    payload: ByokUpdateRequest,
    api_key: str = Depends(get_api_key),
):
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())

    try:
        with _db_uow() as db_session:
            resolution = _resolve_api_key_for_request(
                api_key=api_key,
                request_id=req_id,
                db_session=db_session,
            )
            _require_api_key_id(resolution.api_key_id)
            updated_providers = byok_service.set_byok_keys(
                db_session,
                api_key_id=resolution.api_key_id,
                provider_keys=payload.provider_keys,
                baseline_provider=payload.baseline_provider,
                baseline_model=payload.baseline_model,
                requests_per_minute=payload.requests_per_minute,
            )
            status_payload = byok_service.get_byok_status(
                db_session,
                api_key_id=resolution.api_key_id,
            )
    except ValueError as exc:
        raise _map_value_error(exc) from exc

    return ByokUpdateResponseDTO(
        updated_providers=updated_providers,
        baseline_provider=status_payload.get("baseline_provider"),
        baseline_model=status_payload.get("baseline_model"),
        requests_per_minute=status_payload.get("requests_per_minute"),
    )


@router.get("/byok/status", response_model=ByokStatusDTO)
async def byok_status(
    request: Request,
    api_key: str = Depends(get_api_key),
):
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())

    with _db_uow(commit_on_success=False) as db_session:
        resolution = _resolve_api_key_for_request(
            api_key=api_key,
            request_id=req_id,
            db_session=db_session,
        )
        _require_api_key_id(resolution.api_key_id)
        payload = byok_service.get_byok_status(
            db_session,
            api_key_id=resolution.api_key_id,
        )

    return ByokStatusDTO(**payload)


@router.delete("/byok", response_model=ByokDeleteResponseDTO)
async def delete_byok(
    request: Request,
    provider: str | None = Query(default=None),
    api_key: str = Depends(get_api_key),
):
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())

    try:
        with _db_uow() as db_session:
            resolution = _resolve_api_key_for_request(
                api_key=api_key,
                request_id=req_id,
                db_session=db_session,
            )
            _require_api_key_id(resolution.api_key_id)
            deleted_count = byok_service.delete_byok(
                db_session,
                api_key_id=resolution.api_key_id,
                provider=provider,
            )
    except ValueError as exc:
        raise _map_value_error(exc) from exc

    return ByokDeleteResponseDTO(deleted_count=deleted_count)
