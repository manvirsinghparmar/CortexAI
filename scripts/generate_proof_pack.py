#!/usr/bin/env python3
"""Generate a monthly B2B proof pack (CSV + Markdown + HTML).

Outputs:
- summary.csv
- top_models.csv
- proof_pack.md
- proof_pack.html
"""

from __future__ import annotations

import argparse
import csv
import html
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv
from sqlalchemy import and_, case, func, literal, select

load_dotenv()

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from db import (
    SessionLocal,
    get_api_key_settings,
    get_table,
    get_user_by_api_key,
)
from server import rate_limit as rate_limit_service
from server import savings as savings_service

SUMMARY_COLUMNS = [
    "period_start",
    "period_end",
    "user_id",
    "api_key_id",
    "total_requests",
    "total_tokens",
    "actual_cost",
    "baseline_cost",
    "savings_amount",
    "savings_pct",
    "error_requests",
    "error_rate_pct",
    "successful_requests",
    "failed_requests",
    "baseline_provider",
    "baseline_model",
    "requests_per_minute",
    "daily_cap_scope",
    "daily_token_cap",
    "daily_cost_cap",
    "plan_tier",
]

TOP_MODELS_COLUMNS = [
    "rank",
    "provider",
    "model",
    "requests",
    "tokens",
    "actual_cost",
    "error_requests",
    "error_rate_pct",
]


@dataclass(frozen=True)
class TenantScope:
    user_id: UUID
    api_key_id: UUID | None
    scope: str


@dataclass(frozen=True)
class Period:
    start_dt: datetime
    end_dt: datetime
    start_date: date
    end_date_inclusive: date
    month_label: str


def _ensure_database_url() -> None:
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL is required for proof pack generation")


def _parse_uuid(value: str | None, arg_name: str) -> UUID | None:
    if not value:
        return None
    try:
        return UUID(str(value))
    except Exception as exc:
        raise ValueError(f"{arg_name} must be a valid UUID") from exc


def _period_from_month(month_value: str | None) -> Period:
    if month_value:
        try:
            year_str, month_str = month_value.split("-", 1)
            year = int(year_str)
            month = int(month_str)
            start = date(year, month, 1)
        except Exception as exc:
            raise ValueError("--month must be in YYYY-MM format") from exc
    else:
        today = date.today()
        start = date(today.year, today.month, 1)

    next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
    end_inclusive = next_month - timedelta(days=1)
    start_dt = datetime.combine(start, datetime.min.time())
    end_dt = datetime.combine(next_month, datetime.min.time())
    return Period(
        start_dt=start_dt,
        end_dt=end_dt,
        start_date=start,
        end_date_inclusive=end_inclusive,
        month_label=f"{start.year:04d}-{start.month:02d}",
    )


def _resolve_scope(
    db_session,
    *,
    api_key: str | None,
    api_key_id_raw: str | None,
    user_id_raw: str | None,
) -> TenantScope:
    explicit_api_key_id = _parse_uuid(api_key_id_raw, "--api-key-id")
    explicit_user_id = _parse_uuid(user_id_raw, "--user-id")

    if api_key:
        mapped = get_user_by_api_key(db_session, api_key)
        if not mapped:
            raise RuntimeError("Provided --api-key is not mapped in database")
        user_id, api_key_id = mapped
        return TenantScope(user_id=user_id, api_key_id=api_key_id, scope="api_key")

    if explicit_api_key_id is not None:
        api_keys = get_table("api_keys")
        row = db_session.execute(
            select(api_keys.c.user_id).where(api_keys.c.id == explicit_api_key_id)
        ).first()
        if not row:
            raise RuntimeError("Provided --api-key-id not found")
        user_id = row[0]
        return TenantScope(user_id=user_id, api_key_id=explicit_api_key_id, scope="api_key")

    if explicit_user_id is not None:
        return TenantScope(user_id=explicit_user_id, api_key_id=None, scope="user")

    raise RuntimeError("Provide one of --api-key, --api-key-id, or --user-id")


def _env_int(name: str) -> int | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return int(raw)
    except Exception:
        return None


def _env_float(name: str) -> float | None:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except Exception:
        return None


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _current_config_snapshot(db_session, scope: TenantScope) -> dict[str, Any]:
    settings = get_api_key_settings(db_session, scope.api_key_id) if scope.api_key_id else None
    baseline_provider, baseline_model = savings_service.resolve_baseline_for_api_key(
        db_session,
        api_key_id=scope.api_key_id,
    )
    rpm = rate_limit_service.default_requests_per_minute()
    if settings and settings.get("requests_per_minute") is not None:
        try:
            rpm = int(settings["requests_per_minute"])
        except Exception:
            pass

    return {
        "baseline_provider": baseline_provider,
        "baseline_model": baseline_model,
        "requests_per_minute": rpm,
        "daily_cap_scope": (os.getenv("DAILY_CAP_SCOPE", "api_key") or "api_key").strip().lower(),
        "daily_token_cap": _env_int("DAILY_TOKEN_CAP"),
        "daily_cost_cap": _env_float("DAILY_COST_CAP"),
        "plan_tier": os.getenv("PLAN_TIER"),
    }


def _request_filter(llm_requests, scope: TenantScope, period: Period):
    clauses = [
        llm_requests.c.created_at >= period.start_dt,
        llm_requests.c.created_at < period.end_dt,
    ]
    if scope.api_key_id is not None and "api_key_id" in {c.name for c in llm_requests.columns}:
        clauses.append(llm_requests.c.api_key_id == scope.api_key_id)
    else:
        clauses.append(llm_requests.c.user_id == scope.user_id)
    return and_(*clauses)


def _savings_filter(llm_savings, scope: TenantScope, period: Period):
    cols = {c.name for c in llm_savings.columns}
    clauses: list[Any] = []
    if "usage_date" in cols:
        clauses.extend(
            [
                llm_savings.c.usage_date >= period.start_date,
                llm_savings.c.usage_date <= period.end_date_inclusive,
            ]
        )
    elif "created_at" in cols:
        clauses.extend(
            [
                llm_savings.c.created_at >= period.start_dt,
                llm_savings.c.created_at < period.end_dt,
            ]
        )
    if scope.api_key_id is not None and "api_key_id" in cols:
        clauses.append(llm_savings.c.api_key_id == scope.api_key_id)
    else:
        clauses.append(llm_savings.c.user_id == scope.user_id)
    return and_(*clauses)


def _compute_metrics(db_session, scope: TenantScope, period: Period) -> dict[str, Any]:
    llm_requests = get_table("llm_requests")
    llm_responses = get_table("llm_responses")
    request_filter = _request_filter(llm_requests, scope, period)

    totals_stmt = (
        select(
            func.count(llm_requests.c.id).label("requests"),
            func.coalesce(func.sum(llm_responses.c.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(llm_responses.c.estimated_cost), 0.0).label("actual_cost"),
            func.coalesce(
                func.sum(
                    case(
                        (llm_responses.c.error_type.is_not(None), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("error_requests"),
        )
        .select_from(
            llm_requests.outerjoin(
                llm_responses,
                llm_responses.c.llm_request_id == llm_requests.c.id,
            )
        )
        .where(request_filter)
    )
    totals = db_session.execute(totals_stmt).first()
    totals_map = totals._mapping if totals is not None else {}

    total_requests = _safe_int(totals_map.get("requests"))
    total_tokens = _safe_int(totals_map.get("tokens"))
    actual_cost = _safe_float(totals_map.get("actual_cost"))
    error_requests = _safe_int(totals_map.get("error_requests"))
    error_rate_pct = ((error_requests / total_requests) * 100.0) if total_requests > 0 else 0.0

    baseline_cost = 0.0
    savings_amount = 0.0
    successful_requests = max(total_requests - error_requests, 0)
    failed_requests = error_requests
    savings_available = False

    try:
        llm_savings = get_table("llm_savings")
        savings_filter = _savings_filter(llm_savings, scope, period)
        savings_cols = {c.name for c in llm_savings.columns}
        failed_expr = (
            func.coalesce(
                func.sum(
                    case(
                        (
                            func.lower(func.coalesce(llm_savings.c.response_status, "success"))
                            != "success",
                            1,
                        ),
                        else_=0,
                    )
                ),
                0,
            )
            if "response_status" in savings_cols
            else literal(0)
        )
        savings_stmt = select(
            func.coalesce(func.sum(llm_savings.c.baseline_cost), 0.0).label("baseline_cost"),
            func.coalesce(func.sum(llm_savings.c.savings_amount), 0.0).label("savings_amount"),
            func.count(llm_savings.c.llm_request_id).label("rows"),
            failed_expr.label("failed_rows"),
        ).where(savings_filter)
        srow = db_session.execute(savings_stmt).first()
        smap = srow._mapping if srow is not None else {}
        if _safe_int(smap.get("rows")) > 0:
            savings_available = True
            baseline_cost = _safe_float(smap.get("baseline_cost"))
            savings_amount = _safe_float(smap.get("savings_amount"))
            failed_requests = _safe_int(smap.get("failed_rows"))
            successful_requests = max(_safe_int(smap.get("rows")) - failed_requests, 0)
    except Exception:
        savings_available = False

    savings_pct = (savings_amount / baseline_cost) if baseline_cost > 0 else 0.0

    top_models_stmt = (
        select(
            llm_requests.c.provider.label("provider"),
            llm_requests.c.model.label("model"),
            func.count(llm_requests.c.id).label("requests"),
            func.coalesce(func.sum(llm_responses.c.total_tokens), 0).label("tokens"),
            func.coalesce(func.sum(llm_responses.c.estimated_cost), 0.0).label("actual_cost"),
            func.coalesce(
                func.sum(
                    case(
                        (llm_responses.c.error_type.is_not(None), 1),
                        else_=0,
                    )
                ),
                0,
            ).label("error_requests"),
        )
        .select_from(
            llm_requests.outerjoin(
                llm_responses,
                llm_responses.c.llm_request_id == llm_requests.c.id,
            )
        )
        .where(request_filter)
        .group_by(llm_requests.c.provider, llm_requests.c.model)
        .order_by(
            func.count(llm_requests.c.id).desc(),
            llm_requests.c.provider.asc(),
            llm_requests.c.model.asc(),
        )
        .limit(10)
    )
    model_rows = db_session.execute(top_models_stmt).fetchall()
    top_models: list[dict[str, Any]] = []
    for idx, row in enumerate(model_rows, start=1):
        rm = row._mapping
        req = _safe_int(rm.get("requests"))
        err = _safe_int(rm.get("error_requests"))
        top_models.append(
            {
                "rank": idx,
                "provider": str(rm.get("provider") or ""),
                "model": str(rm.get("model") or ""),
                "requests": req,
                "tokens": _safe_int(rm.get("tokens")),
                "actual_cost": _safe_float(rm.get("actual_cost")),
                "error_requests": err,
                "error_rate_pct": (err / req * 100.0) if req > 0 else 0.0,
            }
        )

    return {
        "total_requests": total_requests,
        "total_tokens": total_tokens,
        "actual_cost": actual_cost,
        "baseline_cost": baseline_cost,
        "savings_amount": savings_amount,
        "savings_pct": savings_pct,
        "error_requests": error_requests,
        "error_rate_pct": error_rate_pct,
        "successful_requests": successful_requests,
        "failed_requests": failed_requests,
        "savings_available": savings_available,
        "top_models": top_models,
    }


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _fmt_money(value: float) -> str:
    return f"${value:,.6f}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.2f}%" if value <= 1.0 else f"{value:.2f}%"


def _markdown_summary(
    *,
    scope: TenantScope,
    period: Period,
    metrics: dict[str, Any],
    config: dict[str, Any],
) -> str:
    top_lines = []
    for row in metrics["top_models"]:
        top_lines.append(
            f"| {row['rank']} | {row['provider']} | {row['model']} | {row['requests']} | "
            f"{row['tokens']} | {_fmt_money(row['actual_cost'])} | {row['error_requests']} | {row['error_rate_pct']:.2f}% |"
        )
    if not top_lines:
        top_lines.append("| - | - | - | 0 | 0 | $0.000000 | 0 | 0.00% |")

    return (
        f"# CortexAI Proof Pack ({period.month_label})\n\n"
        f"- `user_id`: `{scope.user_id}`\n"
        f"- `api_key_id`: `{scope.api_key_id}`\n"
        f"- `scope`: `{scope.scope}`\n"
        f"- `period`: `{period.start_date}` to `{period.end_date_inclusive}`\n\n"
        "## Financial Summary\n\n"
        f"- Spend (actual): {_fmt_money(metrics['actual_cost'])}\n"
        f"- Baseline: {_fmt_money(metrics['baseline_cost'])}\n"
        f"- Savings: {_fmt_money(metrics['savings_amount'])} ({metrics['savings_pct'] * 100:.2f}%)\n\n"
        "## Reliability\n\n"
        f"- Total requests: {metrics['total_requests']}\n"
        f"- Error requests: {metrics['error_requests']}\n"
        f"- Error rate: {metrics['error_rate_pct']:.2f}%\n"
        f"- Successful / Failed (from savings rows when available): "
        f"{metrics['successful_requests']} / {metrics['failed_requests']}\n\n"
        "## Top Models Used\n\n"
        "| Rank | Provider | Model | Requests | Tokens | Cost | Error Requests | Error Rate |\n"
        "|---:|---|---|---:|---:|---:|---:|---:|\n" + "\n".join(top_lines) + "\n\n"
        "## Governance Configuration Snapshot\n\n"
        f"- Baseline active: `{config['baseline_provider']}:{config['baseline_model']}`\n"
        f"- Requests per minute: `{config['requests_per_minute']}`\n"
        f"- Daily cap scope: `{config['daily_cap_scope']}`\n"
        f"- Daily token cap: `{config['daily_token_cap']}`\n"
        f"- Daily cost cap: `{config['daily_cost_cap']}`\n"
        f"- Plan tier: `{config['plan_tier']}`\n"
    )


def _html_summary(
    *,
    scope: TenantScope,
    period: Period,
    metrics: dict[str, Any],
    config: dict[str, Any],
) -> str:
    top_rows = []
    for row in metrics["top_models"]:
        top_rows.append(
            "<tr>"
            f"<td>{row['rank']}</td>"
            f"<td>{html.escape(row['provider'])}</td>"
            f"<td>{html.escape(row['model'])}</td>"
            f"<td>{row['requests']}</td>"
            f"<td>{row['tokens']}</td>"
            f"<td>{_fmt_money(row['actual_cost'])}</td>"
            f"<td>{row['error_requests']}</td>"
            f"<td>{row['error_rate_pct']:.2f}%</td>"
            "</tr>"
        )
    if not top_rows:
        top_rows.append("<tr><td colspan='8'>No usage rows in selected period.</td></tr>")

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>CortexAI Proof Pack {period.month_label}</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111; }}
    h1, h2 {{ margin-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; margin-top: 8px; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; font-size: 14px; }}
    th {{ background: #f5f5f5; text-align: left; }}
    .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }}
    .card {{ border: 1px solid #ddd; padding: 10px; border-radius: 6px; }}
  </style>
</head>
<body>
  <h1>CortexAI Proof Pack ({period.month_label})</h1>
  <div class="card">
    <div><strong>user_id:</strong> {scope.user_id}</div>
    <div><strong>api_key_id:</strong> {scope.api_key_id}</div>
    <div><strong>scope:</strong> {scope.scope}</div>
    <div><strong>period:</strong> {period.start_date} to {period.end_date_inclusive}</div>
  </div>

  <h2>Financial Summary</h2>
  <div class="grid">
    <div class="card"><strong>Spend (actual)</strong><div>{_fmt_money(metrics['actual_cost'])}</div></div>
    <div class="card"><strong>Baseline</strong><div>{_fmt_money(metrics['baseline_cost'])}</div></div>
    <div class="card"><strong>Savings</strong><div>{_fmt_money(metrics['savings_amount'])}</div></div>
    <div class="card"><strong>Savings %</strong><div>{metrics['savings_pct'] * 100:.2f}%</div></div>
  </div>

  <h2>Reliability</h2>
  <div class="grid">
    <div class="card"><strong>Total requests</strong><div>{metrics['total_requests']}</div></div>
    <div class="card"><strong>Error requests</strong><div>{metrics['error_requests']}</div></div>
    <div class="card"><strong>Error rate</strong><div>{metrics['error_rate_pct']:.2f}%</div></div>
    <div class="card"><strong>Successful / Failed</strong><div>{metrics['successful_requests']} / {metrics['failed_requests']}</div></div>
  </div>

  <h2>Top Models Used</h2>
  <table>
    <thead>
      <tr>
        <th>Rank</th><th>Provider</th><th>Model</th><th>Requests</th><th>Tokens</th><th>Cost</th><th>Error Requests</th><th>Error Rate</th>
      </tr>
    </thead>
    <tbody>
      {''.join(top_rows)}
    </tbody>
  </table>

  <h2>Governance Configuration Snapshot</h2>
  <div class="card">
    <div><strong>Baseline active:</strong> {html.escape(config['baseline_provider'])}:{html.escape(config['baseline_model'])}</div>
    <div><strong>Requests per minute:</strong> {config['requests_per_minute']}</div>
    <div><strong>Daily cap scope:</strong> {html.escape(str(config['daily_cap_scope']))}</div>
    <div><strong>Daily token cap:</strong> {config['daily_token_cap']}</div>
    <div><strong>Daily cost cap:</strong> {config['daily_cost_cap']}</div>
    <div><strong>Plan tier:</strong> {html.escape(str(config['plan_tier']))}</div>
  </div>
</body>
</html>
"""


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate monthly tenant proof pack")
    parser.add_argument("--api-key", default=None, help="Raw API key (preferred tenant resolver)")
    parser.add_argument("--api-key-id", default=None, help="API key UUID")
    parser.add_argument("--user-id", default=None, help="User UUID (fallback scope)")
    parser.add_argument("--month", default=None, help="Month in YYYY-MM (default: current month)")
    parser.add_argument("--out-dir", default="reports/proof_packs", help="Output directory")
    parser.add_argument(
        "--tenant-label", default=None, help="Optional tenant label for output folder naming"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    _ensure_database_url()

    period = _period_from_month(args.month)

    db_session = SessionLocal()
    try:
        scope = _resolve_scope(
            db_session,
            api_key=args.api_key,
            api_key_id_raw=args.api_key_id,
            user_id_raw=args.user_id,
        )
        metrics = _compute_metrics(db_session, scope, period)
        config = _current_config_snapshot(db_session, scope)
    finally:
        db_session.close()

    tenant_tag = (args.tenant_label or str(scope.api_key_id or scope.user_id)).replace(":", "_")
    out_root = Path(args.out_dir).resolve()
    out_dir = out_root / f"{period.month_label}_{tenant_tag}"
    out_dir.mkdir(parents=True, exist_ok=True)

    summary_row = {
        "period_start": str(period.start_date),
        "period_end": str(period.end_date_inclusive),
        "user_id": str(scope.user_id),
        "api_key_id": str(scope.api_key_id) if scope.api_key_id is not None else "",
        "total_requests": metrics["total_requests"],
        "total_tokens": metrics["total_tokens"],
        "actual_cost": f"{metrics['actual_cost']:.8f}",
        "baseline_cost": f"{metrics['baseline_cost']:.8f}",
        "savings_amount": f"{metrics['savings_amount']:.8f}",
        "savings_pct": f"{metrics['savings_pct']:.8f}",
        "error_requests": metrics["error_requests"],
        "error_rate_pct": f"{metrics['error_rate_pct']:.4f}",
        "successful_requests": metrics["successful_requests"],
        "failed_requests": metrics["failed_requests"],
        "baseline_provider": config["baseline_provider"],
        "baseline_model": config["baseline_model"],
        "requests_per_minute": config["requests_per_minute"],
        "daily_cap_scope": config["daily_cap_scope"],
        "daily_token_cap": (
            config["daily_token_cap"] if config["daily_token_cap"] is not None else ""
        ),
        "daily_cost_cap": config["daily_cost_cap"] if config["daily_cost_cap"] is not None else "",
        "plan_tier": config["plan_tier"] if config["plan_tier"] is not None else "",
    }

    summary_csv = out_dir / "summary.csv"
    top_models_csv = out_dir / "top_models.csv"
    md_path = out_dir / "proof_pack.md"
    html_path = out_dir / "proof_pack.html"

    _write_csv(summary_csv, SUMMARY_COLUMNS, [summary_row])
    _write_csv(top_models_csv, TOP_MODELS_COLUMNS, metrics["top_models"])
    md_path.write_text(
        _markdown_summary(scope=scope, period=period, metrics=metrics, config=config),
        encoding="utf-8",
    )
    html_path.write_text(
        _html_summary(scope=scope, period=period, metrics=metrics, config=config),
        encoding="utf-8",
    )

    print("Proof pack generated.")
    print(f"scope: {scope.scope}")
    print(f"user_id: {scope.user_id}")
    print(f"api_key_id: {scope.api_key_id}")
    print(f"period: {period.start_date} -> {period.end_date_inclusive}")
    print(f"summary_csv: {summary_csv}")
    print(f"top_models_csv: {top_models_csv}")
    print(f"markdown: {md_path}")
    print(f"html: {html_path}")
    print()
    print("Tip: open proof_pack.html and print to PDF for customer sharing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
