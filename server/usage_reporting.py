"""Usage and savings reporting helpers."""

from __future__ import annotations

import csv
import io
import os
from datetime import date
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from db import get_savings_aggregates, get_usage_aggregates

VALID_GROUP_BY = {"day", "provider", "model"}
USAGE_CSV_COLUMNS = ("bucket", "requests", "tokens", "cost")
SAVINGS_CSV_COLUMNS = (
    "bucket",
    "requests",
    "actual_cost",
    "baseline_cost",
    "savings_amount",
    "savings_pct",
)


def _max_report_range_days() -> int | None:
    """
    Maximum inclusive date span for usage/savings reports.

    Set REPORT_MAX_RANGE_DAYS<=0 to disable range limiting.
    """
    raw = os.getenv("REPORT_MAX_RANGE_DAYS", "366")
    try:
        value = int(raw)
    except Exception:
        return 366
    if value <= 0:
        return None
    return value


def parse_date(value: str | None, *, field_name: str) -> date | None:
    if value is None:
        return None
    try:
        return date.fromisoformat(value)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid {field_name} date '{value}'. Expected YYYY-MM-DD.",
        ) from exc


def parse_date_range(from_value: str | None, to_value: str | None) -> tuple[date | None, date | None]:
    date_from = parse_date(from_value, field_name="from")
    date_to = parse_date(to_value, field_name="to")
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'from' date must be before or equal to 'to' date.",
        )

    if date_from and date_to:
        max_days = _max_report_range_days()
        if max_days is not None:
            span_days = (date_to - date_from).days + 1
            if span_days > max_days:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Date range too large ({span_days} days). "
                        f"Maximum allowed is {max_days} days."
                    ),
                )
    return date_from, date_to


def normalize_group_by(group_by: str | None) -> str:
    value = (group_by or "day").strip().lower()
    if value not in VALID_GROUP_BY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid group_by '{group_by}'. Use one of: day, provider, model.",
        )
    return value


def build_usage_report(
    db_session: Session,
    *,
    user_id: UUID,
    date_from: date | None,
    date_to: date | None,
    group_by: str,
) -> dict:
    rows = get_usage_aggregates(
        db_session,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
    )
    totals = {
        "requests": sum(int(item.get("requests") or 0) for item in rows),
        "tokens": sum(int(item.get("tokens") or 0) for item in rows),
        "cost": sum(float(item.get("cost") or 0.0) for item in rows),
    }
    return {
        "from": str(date_from) if date_from else None,
        "to": str(date_to) if date_to else None,
        "group_by": group_by,
        "totals": totals,
        "breakdown": rows,
    }


def build_savings_report(
    db_session: Session,
    *,
    user_id: UUID,
    date_from: date | None,
    date_to: date | None,
    group_by: str,
) -> dict:
    rows = get_savings_aggregates(
        db_session,
        user_id=user_id,
        date_from=date_from,
        date_to=date_to,
        group_by=group_by,
    )
    total_requests = sum(int(item.get("requests") or 0) for item in rows)
    total_successful = sum(int(item.get("successful_requests") or 0) for item in rows)
    total_failed = sum(int(item.get("failed_requests") or 0) for item in rows)
    total_actual = sum(float(item.get("actual_cost") or 0.0) for item in rows)
    total_baseline = sum(float(item.get("baseline_cost") or 0.0) for item in rows)
    total_savings = sum(float(item.get("savings_amount") or 0.0) for item in rows)
    total_savings_pct = (total_savings / total_baseline) if total_baseline > 0 else 0.0
    return {
        "from": str(date_from) if date_from else None,
        "to": str(date_to) if date_to else None,
        "group_by": group_by,
        "totals": {
            "requests": total_requests,
            "successful_requests": total_successful,
            "failed_requests": total_failed,
            "actual_cost": total_actual,
            "baseline_cost": total_baseline,
            "savings_amount": total_savings,
            "savings_pct": total_savings_pct,
        },
        "breakdown": rows,
    }


def usage_report_csv(report: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(USAGE_CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in report.get("breakdown", []):
        writer.writerow(
            {
                "bucket": row.get("bucket", "unknown"),
                "requests": int(row.get("requests") or 0),
                "tokens": int(row.get("tokens") or 0),
                "cost": f"{float(row.get('cost') or 0.0):.8f}",
            }
        )
    return output.getvalue()


def savings_report_csv(report: dict) -> str:
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=list(SAVINGS_CSV_COLUMNS), lineterminator="\n")
    writer.writeheader()
    for row in report.get("breakdown", []):
        writer.writerow(
            {
                "bucket": row.get("bucket", "unknown"),
                "requests": int(row.get("requests") or 0),
                "actual_cost": f"{float(row.get('actual_cost') or 0.0):.8f}",
                "baseline_cost": f"{float(row.get('baseline_cost') or 0.0):.8f}",
                "savings_amount": f"{float(row.get('savings_amount') or 0.0):.8f}",
                "savings_pct": f"{float(row.get('savings_pct') or 0.0):.8f}",
            }
        )
    return output.getvalue()
