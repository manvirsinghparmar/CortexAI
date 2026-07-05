"""Usage and savings reporting helpers."""

from __future__ import annotations

import csv
import io
import os
from datetime import date, timedelta
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from db import get_savings_aggregates, get_table, get_usage_aggregates

VALID_GROUP_BY = {"day", "provider", "model"}
SMART_ROUTING_MODES = {"cheap", "smart", "strong"}
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


def resolve_summary_date_range(from_value: str | None, to_value: str | None) -> tuple[date, date, str]:
    """
    Resolve the UsageSummary period.

    The dashboard contract is period-scoped and defaults to the last 30
    inclusive calendar days. Activity bars are derived separately as the last
    14 days ending at the resolved `to` date.
    """
    explicit_from, explicit_to = parse_date_range(from_value, to_value)
    used_default = explicit_from is None and explicit_to is None

    date_to = explicit_to or date.today()
    date_from = explicit_from or (date_to - timedelta(days=29))
    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="'from' date must be before or equal to 'to' date.",
        )

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

    label = "Last 30 days" if used_default else f"{date_from.isoformat()} to {date_to.isoformat()}"
    return date_from, date_to, label


def _apply_request_date_range(stmt, created_col, *, date_from: date, date_to: date):
    return stmt.where(
        created_col >= date_from,
        created_col < (date_to + timedelta(days=1)),
    )


def _smart_count_expr(routing_mode_col):
    return case((routing_mode_col.in_(tuple(SMART_ROUTING_MODES)), 1), else_=0)


def _percentile(values: list[float], pct: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    if len(ordered) == 1:
        return float(ordered[0])

    position = (len(ordered) - 1) * pct
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(ordered) - 1)
    fraction = position - lower_index
    return float(ordered[lower_index] + (ordered[upper_index] - ordered[lower_index]) * fraction)


def _title_token(value: str) -> str:
    lower = value.lower()
    if lower == "gpt":
        return "GPT"
    if lower == "ai":
        return "AI"
    if lower == "llama":
        return "Llama"
    if lower == "deepseek":
        return "DeepSeek"
    return value[:1].upper() + value[1:]


def _collapse_numeric_version(parts: list[str]) -> list[str]:
    if len(parts) >= 2 and parts[-2].isdigit() and parts[-1].isdigit():
        return [*parts[:-2], f"{parts[-2]}.{parts[-1]}"]
    return parts


def _display_model_name(provider: str, model_id: str) -> str:
    normalized = (model_id or "").replace("_", "-").strip("-")
    if not normalized:
        return "Unknown model"

    parts = [part for part in normalized.split("-") if part]
    if not parts:
        return normalized

    if parts[0].lower() == "gpt" and len(parts) >= 2:
        suffix = " ".join(_title_token(part) for part in parts[2:])
        return f"GPT-{parts[1]}{f' {suffix}' if suffix else ''}"

    if provider.lower() == "claude" and parts[0].lower() == "claude":
        parts = [parts[0], *_collapse_numeric_version(parts[1:])]
    else:
        parts = _collapse_numeric_version(parts)

    return " ".join(_title_token(part) for part in parts)


def _sum_tokens_for_period(
    db_session: Session,
    *,
    user_id: UUID,
    date_from: date,
    date_to: date,
) -> int:
    llm_requests = get_table("llm_requests")
    llm_responses = get_table("llm_responses")
    stmt = (
        select(func.coalesce(func.sum(llm_responses.c.total_tokens), 0))
        .select_from(
            llm_requests.outerjoin(
                llm_responses,
                llm_responses.c.llm_request_id == llm_requests.c.id,
            )
        )
        .where(llm_requests.c.user_id == user_id)
    )
    stmt = _apply_request_date_range(
        stmt,
        llm_requests.c.created_at,
        date_from=date_from,
        date_to=date_to,
    )
    return int(db_session.execute(stmt).scalar_one() or 0)


def build_usage_summary(
    db_session: Session,
    *,
    user_id: UUID,
    date_from: date,
    date_to: date,
    label: str,
) -> dict:
    llm_requests = get_table("llm_requests")
    llm_responses = get_table("llm_responses")
    routing_decisions = get_table("routing_decisions")
    request_response_join = llm_requests.outerjoin(
        llm_responses,
        llm_responses.c.llm_request_id == llm_requests.c.id,
    )
    telemetry_join = request_response_join.outerjoin(
        routing_decisions,
        routing_decisions.c.llm_request_id == llm_requests.c.id,
    )
    smart_expr = _smart_count_expr(routing_decisions.c.routing_mode)

    totals_stmt = (
        select(
            func.count(llm_requests.c.id).label("requests"),
            func.coalesce(func.sum(llm_responses.c.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(llm_responses.c.estimated_cost), 0.0).label("cost"),
            func.coalesce(func.sum(smart_expr), 0).label("smart"),
        )
        .select_from(telemetry_join)
        .where(llm_requests.c.user_id == user_id)
    )
    totals_stmt = _apply_request_date_range(
        totals_stmt,
        llm_requests.c.created_at,
        date_from=date_from,
        date_to=date_to,
    )
    totals = dict(db_session.execute(totals_stmt).one()._mapping)
    total_requests = int(totals.get("requests") or 0)
    total_tokens = int(totals.get("tokens") or 0)
    total_spend = float(totals.get("cost") or 0.0)
    smart_routed_total = int(totals.get("smart") or 0)

    latency_stmt = (
        select(llm_responses.c.latency_ms)
        .select_from(request_response_join)
        .where(
            llm_requests.c.user_id == user_id,
            llm_responses.c.latency_ms.is_not(None),
        )
    )
    latency_stmt = _apply_request_date_range(
        latency_stmt,
        llm_requests.c.created_at,
        date_from=date_from,
        date_to=date_to,
    )
    latency_values = [float(row[0]) for row in db_session.execute(latency_stmt).fetchall()]
    avg_latency = sum(latency_values) / len(latency_values) if latency_values else 0.0
    p95_latency = _percentile(latency_values, 0.95)
    min_latency = min(latency_values) if latency_values else 0.0

    previous_span_days = (date_to - date_from).days + 1
    previous_to = date_from - timedelta(days=1)
    previous_from = previous_to - timedelta(days=previous_span_days - 1)
    previous_tokens = _sum_tokens_for_period(
        db_session,
        user_id=user_id,
        date_from=previous_from,
        date_to=previous_to,
    )
    if previous_tokens == 0:
        tokens_delta_pct = 100.0 if total_tokens > 0 else 0.0
    else:
        tokens_delta_pct = ((total_tokens - previous_tokens) / previous_tokens) * 100.0

    model_stmt = (
        select(
            llm_requests.c.provider.label("provider"),
            llm_requests.c.model.label("modelId"),
            func.count(llm_requests.c.id).label("replies"),
            func.coalesce(func.sum(smart_expr), 0).label("viaSmart"),
        )
        .select_from(telemetry_join)
        .where(llm_requests.c.user_id == user_id)
        .group_by(llm_requests.c.provider, llm_requests.c.model)
        .order_by(func.count(llm_requests.c.id).desc(), llm_requests.c.provider, llm_requests.c.model)
    )
    model_stmt = _apply_request_date_range(
        model_stmt,
        llm_requests.c.created_at,
        date_from=date_from,
        date_to=date_to,
    )
    models = []
    for row in db_session.execute(model_stmt).fetchall():
        item = dict(row._mapping)
        provider = str(item.get("provider") or "unknown")
        model_id = str(item.get("modelId") or "unknown")
        models.append(
            {
                "provider": provider,
                "modelId": model_id,
                "displayName": _display_model_name(provider, model_id),
                "replies": int(item.get("replies") or 0),
                "viaSmart": int(item.get("viaSmart") or 0),
            }
        )

    session_stmt = (
        select(
            llm_requests.c.session_id.label("session_id"),
            func.max(case((llm_requests.c.route_mode == "ask", 1), else_=0)).label("has_ask"),
            func.max(case((llm_requests.c.route_mode == "compare", 1), else_=0)).label("has_compare"),
        )
        .where(
            llm_requests.c.user_id == user_id,
            llm_requests.c.session_id.is_not(None),
        )
        .group_by(llm_requests.c.session_id)
    )
    session_stmt = _apply_request_date_range(
        session_stmt,
        llm_requests.c.created_at,
        date_from=date_from,
        date_to=date_to,
    )
    session_modes = {"askOnly": 0, "compareOnly": 0, "mixed": 0}
    for row in db_session.execute(session_stmt).fetchall():
        item = dict(row._mapping)
        has_ask = bool(item.get("has_ask"))
        has_compare = bool(item.get("has_compare"))
        if has_ask and has_compare:
            session_modes["mixed"] += 1
        elif has_compare:
            session_modes["compareOnly"] += 1
        elif has_ask:
            session_modes["askOnly"] += 1

    activity_from = date_to - timedelta(days=13)
    activity_stmt = (
        select(
            func.date(llm_requests.c.created_at).label("date"),
            func.coalesce(func.sum(llm_responses.c.total_tokens), 0).label("tokens"),
        )
        .select_from(request_response_join)
        .where(llm_requests.c.user_id == user_id)
        .group_by(func.date(llm_requests.c.created_at))
    )
    activity_stmt = _apply_request_date_range(
        activity_stmt,
        llm_requests.c.created_at,
        date_from=activity_from,
        date_to=date_to,
    )
    activity_tokens = {
        str(row._mapping["date"]): int(row._mapping["tokens"] or 0)
        for row in db_session.execute(activity_stmt).fetchall()
    }
    activity_daily = [
        {
            "date": (activity_from + timedelta(days=offset)).isoformat(),
            "tokens": activity_tokens.get((activity_from + timedelta(days=offset)).isoformat(), 0),
        }
        for offset in range(14)
    ]

    return {
        "period": {
            "from": date_from.isoformat(),
            "to": date_to.isoformat(),
            "label": label,
        },
        "totalTokens": total_tokens,
        "totalRequests": total_requests,
        "totalSessions": sum(session_modes.values()),
        "avgLatencyMs": float(avg_latency),
        "p95LatencyMs": float(p95_latency),
        "minLatencyMs": float(min_latency),
        "avgCostPerRequest": total_spend / total_requests if total_requests else 0.0,
        "totalSpend": total_spend,
        "tokensDeltaPct": float(tokens_delta_pct),
        "smartRoutedTotal": smart_routed_total,
        "models": models,
        "sessionModes": session_modes,
        "switchedMidSession": session_modes["mixed"],
        "activityDaily": activity_daily,
    }


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
