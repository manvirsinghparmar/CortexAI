"""Usage and savings reporting endpoints."""

from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from server import persistence as persistence_service
from server.dependencies import get_auth
from server.schemas.responses import SavingsReportDTO, UsageReportDTO
from server.usage_reporting import (
    SAVINGS_CSV_COLUMNS,
    USAGE_CSV_COLUMNS,
    build_savings_report,
    build_usage_report,
    normalize_group_by,
    parse_date_range,
    savings_report_csv,
    usage_report_csv,
)

router = APIRouter(prefix="/v1", tags=["Reporting"])

API_DB_ENABLED = persistence_service.API_DB_ENABLED
_resolve_identity = persistence_service.resolve_identity
_db_uow = persistence_service.db_uow


def _require_db_mode() -> None:
    if API_DB_ENABLED:
        return
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Usage/savings reporting requires DATABASE_URL (DB mode).",
    )


@router.get("/usage", response_model=UsageReportDTO)
async def usage_report(
    request: Request,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    group_by: str = Query(default="day"),
    auth=Depends(get_auth),
):
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    date_from, date_to = parse_date_range(from_date, to_date)
    grouped = normalize_group_by(group_by)
    with _db_uow(commit_on_success=False) as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        report = build_usage_report(
            db_session,
            user_id=resolution.user_id,
            date_from=date_from,
            date_to=date_to,
            group_by=grouped,
        )
    return UsageReportDTO(
        from_date=report.get("from"),
        to_date=report.get("to"),
        group_by=report.get("group_by", grouped),
        totals=report.get("totals", {}),
        breakdown=report.get("breakdown", []),
    )


@router.get("/savings", response_model=SavingsReportDTO)
async def savings_report(
    request: Request,
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    group_by: str = Query(default="day"),
    auth=Depends(get_auth),
):
    _require_db_mode()
    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    date_from, date_to = parse_date_range(from_date, to_date)
    grouped = normalize_group_by(group_by)
    with _db_uow(commit_on_success=False) as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        report = build_savings_report(
            db_session,
            user_id=resolution.user_id,
            date_from=date_from,
            date_to=date_to,
            group_by=grouped,
        )
    return SavingsReportDTO(
        from_date=report.get("from"),
        to_date=report.get("to"),
        group_by=report.get("group_by", grouped),
        totals=report.get("totals", {}),
        breakdown=report.get("breakdown", []),
    )


@router.get("/usage/export")
async def usage_export(
    request: Request,
    format: str = Query(default="csv"),  # noqa: A002
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    group_by: str = Query(default="day"),
    auth=Depends(get_auth),
):
    _require_db_mode()
    if (format or "").strip().lower() != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only format=csv is currently supported.",
        )

    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    date_from, date_to = parse_date_range(from_date, to_date)
    grouped = normalize_group_by(group_by)
    with _db_uow(commit_on_success=False) as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        report = build_usage_report(
            db_session,
            user_id=resolution.user_id,
            date_from=date_from,
            date_to=date_to,
            group_by=grouped,
        )
    csv_payload = usage_report_csv(report)
    return Response(
        content=csv_payload,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=usage_report.csv",
            "X-Export-Columns": ",".join(USAGE_CSV_COLUMNS),
        },
    )


@router.get("/savings/export")
async def savings_export(
    request: Request,
    format: str = Query(default="csv"),  # noqa: A002
    from_date: str | None = Query(default=None, alias="from"),
    to_date: str | None = Query(default=None, alias="to"),
    group_by: str = Query(default="day"),
    auth=Depends(get_auth),
):
    _require_db_mode()
    if (format or "").strip().lower() != "csv":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only format=csv is currently supported.",
        )

    req_id = str(getattr(request.state, "request_id", "") or uuid4())
    date_from, date_to = parse_date_range(from_date, to_date)
    grouped = normalize_group_by(group_by)
    with _db_uow(commit_on_success=False) as db_session:
        resolution = _resolve_identity(
                auth=auth,
                request_id=req_id,
                db_session=db_session,
            )
        report = build_savings_report(
            db_session,
            user_id=resolution.user_id,
            date_from=date_from,
            date_to=date_to,
            group_by=grouped,
        )
    csv_payload = savings_report_csv(report)
    return Response(
        content=csv_payload,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=savings_report.csv",
            "X-Export-Columns": ",".join(SAVINGS_CSV_COLUMNS),
        },
    )
