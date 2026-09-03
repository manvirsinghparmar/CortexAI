#!/usr/bin/env python3
"""End-to-end B2B API checklist for CortexAI.

This script validates a running server with authenticated API calls and optional
direct DB assertions. It is designed for pre-prod launch verification.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any

create_engine: Any
text: Any
try:
    from sqlalchemy import create_engine as _create_engine
    from sqlalchemy import text as _text

    create_engine = _create_engine
    text = _text
except Exception:  # pragma: no cover - optional runtime dependency
    create_engine = None
    text = None

REPO_ROOT = Path(__file__).resolve().parents[1]


class CheckFailed(Exception):
    pass


class CheckSkipped(Exception):
    pass


@dataclass
class HttpResult:
    status: int
    headers: dict[str, str]
    text: str
    json_body: Any | None


@dataclass
class CheckOutcome:
    name: str
    status: str
    detail: str
    duration_s: float


class E2EB2BChecklist:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.base_url = args.base_url.rstrip("/")
        self.api_key = args.api_key
        self.default_headers = {
            "X-API-Key": self.api_key,
            "X-Request-ID": f"e2e-{int(time.time())}",
            "Content-Type": "application/json",
        }

        self.database_url = args.database_url or os.getenv("DATABASE_URL")
        self.db_schema = (args.db_schema or os.getenv("DB_SCHEMA", "public")).strip()
        self.db_mode = False
        self.db_engine = None
        self.available_paths: set[str] = set()
        self.missing_b2b_surface = False

        self.whoami: dict[str, Any] = {}
        self.chat_resp: dict[str, Any] = {}
        self.compare_resp: dict[str, Any] = {}
        self.compare_stream_group_id: str | None = None
        self.byok_plain_openai = f"sk-e2e-openai-{int(time.time())}-1234"

        self.results: list[CheckOutcome] = []

    # ---------- helpers ----------
    def _log(self, msg: str) -> None:
        print(f"[e2e] {msg}")

    def _pass(self, name: str, detail: str, start: float) -> None:
        elapsed = time.time() - start
        self.results.append(
            CheckOutcome(name=name, status="PASS", detail=detail, duration_s=elapsed)
        )
        self._log(f"PASS {name} ({elapsed:.2f}s) - {detail}")

    def _fail(self, name: str, detail: str, start: float) -> None:
        elapsed = time.time() - start
        self.results.append(
            CheckOutcome(name=name, status="FAIL", detail=detail, duration_s=elapsed)
        )
        self._log(f"FAIL {name} ({elapsed:.2f}s) - {detail}")

    def _skip(self, name: str, detail: str, start: float) -> None:
        elapsed = time.time() - start
        self.results.append(
            CheckOutcome(name=name, status="SKIP", detail=detail, duration_s=elapsed)
        )
        self._log(f"SKIP {name} ({elapsed:.2f}s) - {detail}")

    def _run_check(self, name: str, fn) -> None:
        start = time.time()
        try:
            fn()
            self._pass(name, "ok", start)
        except CheckSkipped as exc:
            self._skip(name, str(exc), start)
        except Exception as exc:
            self._fail(name, str(exc), start)

    def _ensure(self, condition: bool, message: str) -> None:
        if not condition:
            raise CheckFailed(message)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout_s: float | None = None,
    ) -> HttpResult:
        timeout = timeout_s if timeout_s is not None else self.args.timeout_s
        query = ""
        if params:
            query = "?" + urllib.parse.urlencode(params, doseq=True)
        url = f"{self.base_url}{path}{query}"

        req_headers = dict(self.default_headers)
        if headers:
            req_headers.update(headers)

        payload = None
        if json_body is not None:
            payload = json.dumps(json_body).encode("utf-8")

        req = urllib.request.Request(
            url=url, method=method.upper(), data=payload, headers=req_headers
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body_bytes = resp.read()
                text_body = body_bytes.decode("utf-8", errors="replace")
                parsed_json = None
                content_type = str(resp.headers.get("Content-Type") or "")
                if (
                    "application/json" in content_type
                    or text_body.strip().startswith("{")
                    or text_body.strip().startswith("[")
                ):
                    try:
                        parsed_json = json.loads(text_body)
                    except Exception:
                        parsed_json = None
                return HttpResult(
                    status=int(resp.status),
                    headers={k.lower(): v for k, v in resp.headers.items()},
                    text=text_body,
                    json_body=parsed_json,
                )
        except urllib.error.HTTPError as exc:
            text_body = exc.read().decode("utf-8", errors="replace")
            parsed_json = None
            try:
                parsed_json = json.loads(text_body)
            except Exception:
                parsed_json = None
            return HttpResult(
                status=int(exc.code),
                headers={k.lower(): v for k, v in exc.headers.items()},
                text=text_body,
                json_body=parsed_json,
            )

    def _stream_ndjson(self, path: str, *, json_body: dict[str, Any]) -> list[dict[str, Any]]:
        url = f"{self.base_url}{path}"
        req_headers = dict(self.default_headers)
        req_headers["Accept"] = "application/x-ndjson"
        req = urllib.request.Request(
            url=url,
            method="POST",
            data=json.dumps(json_body).encode("utf-8"),
            headers=req_headers,
        )

        events: list[dict[str, Any]] = []
        with urllib.request.urlopen(req, timeout=self.args.timeout_s) as resp:
            self._ensure(int(resp.status) == 200, f"stream status expected 200, got {resp.status}")
            for raw in resp:
                line = raw.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except Exception as exc:
                    raise CheckFailed(f"invalid NDJSON line: {line[:160]} ({exc})") from exc
                if isinstance(event, dict):
                    events.append(event)
                if isinstance(event, dict) and event.get("type") in {"done", "error"}:
                    break
                if len(events) >= self.args.max_stream_events:
                    break
        return events

    def _today_window(self) -> tuple[str, str]:
        today = date.today()
        start = today - timedelta(days=1)
        return start.isoformat(), today.isoformat()

    def _table_ref(self, name: str) -> str:
        if (self.database_url or "").lower().startswith("sqlite"):
            return name
        schema = self.db_schema or "public"
        return f"{schema}.{name}"

    def _db_ready(self) -> bool:
        return bool(self.database_url and create_engine and text)

    def _ensure_db_engine(self) -> None:
        if self.db_engine is not None:
            return
        if not self._db_ready():
            raise CheckSkipped("DATABASE_URL/SQLAlchemy not available for DB assertions")
        self.db_engine = create_engine(self.database_url)

    # ---------- checks ----------
    def check_health(self) -> None:
        res = self._request("GET", "/health")
        self._ensure(res.status == 200, f"/health expected 200, got {res.status}: {res.text[:200]}")
        body = res.json_body or {}
        self._ensure(body.get("status") == "healthy", f"/health unexpected payload: {body}")

    def check_openapi_surface(self) -> None:
        res = self._request("GET", "/openapi.json")
        if res.status != 200:
            raise CheckSkipped(
                f"/openapi.json unavailable (status={res.status}); skipping surface validation"
            )

        body = res.json_body if isinstance(res.json_body, dict) else {}
        paths_obj = body.get("paths")
        if not isinstance(paths_obj, dict):
            raise CheckSkipped("/openapi.json missing paths object")

        self.available_paths = set(paths_obj.keys())
        required_base = {"/v1/chat", "/v1/compare", "/v1/history"}
        missing_base = sorted(required_base - self.available_paths)
        self._ensure(not missing_base, f"required core paths missing in OpenAPI: {missing_base}")

        required_b2b = {
            "/v1/whoami",
            "/v1/usage",
            "/v1/savings",
            "/v1/byok",
            "/v1/byok/status",
            "/v1/admin/request-groups/{request_group_id}/failed-attempts",
        }
        missing_b2b = sorted(required_b2b - self.available_paths)
        if missing_b2b:
            self.missing_b2b_surface = True
            msg = (
                "running server does not expose full B2B route surface. "
                f"Missing: {missing_b2b}. "
                "This usually means an older/stale server process is running; restart/deploy latest build."
            )
            if self.args.allow_missing_b2b_routes:
                raise CheckSkipped(msg)
            raise CheckFailed(msg)

    def check_whoami(self) -> None:
        if self.missing_b2b_surface:
            raise CheckSkipped(
                "skipped because B2B route surface is missing on this running server"
            )
        res = self._request("GET", "/v1/whoami")
        self._ensure(
            res.status == 200,
            "/v1/whoami expected 200, got "
            f"{res.status}: {res.text[:200]} (endpoint likely missing on running server build)",
        )
        body = res.json_body or {}
        required = {"storage_policy", "baseline", "rate_limits", "breakers"}
        missing = sorted(required - set(body.keys()))
        self._ensure(not missing, f"/v1/whoami missing keys: {missing}")
        self.whoami = body
        self.db_mode = bool(body.get("user_id"))

        if not self.db_mode and not self.args.allow_no_db_mode:
            raise CheckFailed(
                "DB mode appears disabled (user_id/api_key_id missing). "
                "Set DATABASE_URL and mapped API key, or run with --allow-no-db-mode."
            )

    def check_chat(self) -> None:
        payload = {
            "prompt": "e2e checklist chat probe",
            "provider": self.args.chat_provider,
            "model": self.args.chat_model,
            "routing": {"smart_mode": False, "research_mode": False},
        }
        res = self._request("POST", "/v1/chat", json_body=payload)
        self._ensure(
            res.status == 200, f"/v1/chat expected 200, got {res.status}: {res.text[:240]}"
        )
        body = res.json_body or {}
        self._ensure(bool(body.get("request_id")), "chat response missing request_id")
        self._ensure(bool(body.get("provider")), "chat response missing provider")
        self._ensure(bool(body.get("model")), "chat response missing model")
        self.chat_resp = body

    def check_chat_stream(self) -> None:
        if self.args.skip_stream:
            raise CheckSkipped("--skip-stream enabled")
        payload = {
            "prompt": "e2e checklist chat stream probe",
            "provider": self.args.chat_provider,
            "model": self.args.chat_model,
        }
        events = self._stream_ndjson("/v1/chat/stream", json_body=payload)
        types = [event.get("type") for event in events if isinstance(event, dict)]
        self._ensure("start" in types, "chat stream missing start event")
        self._ensure("done" in types, "chat stream missing done event")

    def check_compare(self) -> None:
        payload = {
            "prompt": "e2e checklist compare probe",
            "targets": [
                {"provider": self.args.chat_provider, "model": self.args.chat_model},
                {"provider": self.args.compare_provider, "model": self.args.compare_model},
            ],
        }
        res = self._request(
            "POST", "/v1/compare", json_body=payload, timeout_s=max(self.args.timeout_s, 90.0)
        )
        self._ensure(
            res.status == 200, f"/v1/compare expected 200, got {res.status}: {res.text[:240]}"
        )
        body = res.json_body or {}
        self._ensure(
            bool(body.get("request_group_id")),
            "compare response missing request_group_id",
        )
        responses = body.get("responses") or []
        self._ensure(
            isinstance(responses, list) and len(responses) >= 2, "compare expected >=2 responses"
        )
        self.compare_resp = body

    def check_compare_stream(self) -> None:
        if self.args.skip_stream:
            raise CheckSkipped("--skip-stream enabled")
        payload = {
            "prompt": "e2e checklist compare stream probe",
            "targets": [
                {"provider": self.args.chat_provider, "model": self.args.chat_model},
                {"provider": self.args.compare_provider, "model": self.args.compare_model},
            ],
        }
        events = self._stream_ndjson("/v1/compare/stream", json_body=payload)
        types = [event.get("type") for event in events if isinstance(event, dict)]
        self._ensure("start" in types, "compare stream missing start event")
        self._ensure("done" in types, "compare stream missing done event")

        done_event = next((event for event in events if event.get("type") == "done"), {})
        compare_blob = done_event.get("compare") if isinstance(done_event, dict) else None
        if isinstance(compare_blob, dict) and compare_blob.get("request_group_id"):
            self.compare_stream_group_id = str(compare_blob["request_group_id"])

    def check_admin_failed_attempts(self) -> None:
        if self.missing_b2b_surface:
            raise CheckSkipped(
                "skipped because B2B route surface is missing on this running server"
            )
        request_group_id = self.compare_resp.get("request_group_id")
        if not request_group_id:
            raise CheckFailed("missing compare request_group_id from prior step")
        res = self._request(
            "GET",
            f"/v1/admin/request-groups/{request_group_id}/failed-attempts",
            params={"limit": 200},
        )
        self._ensure(
            res.status == 200,
            f"/v1/admin/request-groups/{{id}}/failed-attempts expected 200, got {res.status}: {res.text[:240]}",
        )
        body = res.json_body or {}
        self._ensure(
            body.get("request_group_id") == request_group_id,
            "admin response request_group_id mismatch",
        )

    def check_history(self) -> None:
        res = self._request("GET", "/v1/history", params={"limit": 10})
        self._ensure(
            res.status == 200, f"/v1/history expected 200, got {res.status}: {res.text[:200]}"
        )
        body = res.json_body
        self._ensure(isinstance(body, list), "/v1/history expected list payload")

    def check_reporting(self) -> None:
        if self.missing_b2b_surface:
            raise CheckSkipped(
                "skipped because B2B route surface is missing on this running server"
            )
        start_date, end_date = self._today_window()
        usage = self._request(
            "GET",
            "/v1/usage",
            params={"from": start_date, "to": end_date, "group_by": "day"},
        )
        savings = self._request(
            "GET",
            "/v1/savings",
            params={"from": start_date, "to": end_date, "group_by": "provider"},
        )

        if not self.db_mode:
            self._ensure(
                usage.status == 501,
                f"/v1/usage expected 501 when DB mode is off, got {usage.status}",
            )
            self._ensure(
                savings.status == 501,
                f"/v1/savings expected 501 when DB mode is off, got {savings.status}",
            )
            raise CheckSkipped("DB mode off; reporting endpoints correctly returned 501")

        self._ensure(
            usage.status == 200, f"/v1/usage expected 200, got {usage.status}: {usage.text[:200]}"
        )
        self._ensure(
            savings.status == 200,
            f"/v1/savings expected 200, got {savings.status}: {savings.text[:200]}",
        )

        usage_body = usage.json_body or {}
        savings_body = savings.json_body or {}
        self._ensure(
            "totals" in usage_body and "breakdown" in usage_body,
            "usage payload missing totals/breakdown",
        )
        self._ensure(
            "totals" in savings_body and "breakdown" in savings_body,
            "savings payload missing totals/breakdown",
        )

    def check_exports(self) -> None:
        if self.missing_b2b_surface:
            raise CheckSkipped(
                "skipped because B2B route surface is missing on this running server"
            )
        start_date, end_date = self._today_window()
        usage = self._request(
            "GET",
            "/v1/usage/export",
            params={"format": "csv", "from": start_date, "to": end_date, "group_by": "provider"},
            headers={"Content-Type": "application/json"},
        )
        savings = self._request(
            "GET",
            "/v1/savings/export",
            params={"format": "csv", "from": start_date, "to": end_date, "group_by": "day"},
            headers={"Content-Type": "application/json"},
        )

        if not self.db_mode:
            self._ensure(
                usage.status == 501,
                f"/v1/usage/export expected 501 when DB mode is off, got {usage.status}",
            )
            self._ensure(
                savings.status == 501,
                f"/v1/savings/export expected 501 when DB mode is off, got {savings.status}",
            )
            raise CheckSkipped("DB mode off; export endpoints correctly returned 501")

        self._ensure(usage.status == 200, f"/v1/usage/export expected 200, got {usage.status}")
        self._ensure(
            savings.status == 200, f"/v1/savings/export expected 200, got {savings.status}"
        )

        usage_cols = usage.headers.get("x-export-columns")
        savings_cols = savings.headers.get("x-export-columns")
        self._ensure(
            usage_cols == "bucket,requests,tokens,cost",
            f"unexpected usage export columns: {usage_cols}",
        )
        self._ensure(
            savings_cols == "bucket,requests,actual_cost,baseline_cost,savings_amount,savings_pct",
            f"unexpected savings export columns: {savings_cols}",
        )

        usage_first_line = (usage.text.splitlines() or [""])[0]
        savings_first_line = (savings.text.splitlines() or [""])[0]
        self._ensure(usage_first_line == "bucket,requests,tokens,cost", "usage CSV header mismatch")
        self._ensure(
            savings_first_line
            == "bucket,requests,actual_cost,baseline_cost,savings_amount,savings_pct",
            "savings CSV header mismatch",
        )

    def check_byok_lifecycle(self) -> None:
        if self.missing_b2b_surface:
            raise CheckSkipped(
                "skipped because B2B route surface is missing on this running server"
            )
        if self.args.skip_byok:
            raise CheckSkipped("--skip-byok enabled")
        if not self.db_mode:
            raise CheckSkipped("DB mode off; BYOK lifecycle is DB-only")

        set_payload = {
            "provider_keys": {"openai": self.byok_plain_openai},
            "baseline_provider": self.args.chat_provider,
            "baseline_model": self.args.chat_model,
            "requests_per_minute": max(self.args.expected_min_rpm, 5),
        }
        set_res = self._request("POST", "/v1/byok", json_body=set_payload)
        self._ensure(
            set_res.status == 200,
            f"/v1/byok set expected 200, got {set_res.status}: {set_res.text[:240]}",
        )

        status_res = self._request("GET", "/v1/byok/status")
        self._ensure(
            status_res.status == 200,
            f"/v1/byok/status expected 200, got {status_res.status}: {status_res.text[:240]}",
        )
        status_body = status_res.json_body or {}
        providers = {item.get("provider"): item for item in status_body.get("providers") or []}
        self._ensure("openai" in providers, "BYOK status missing openai provider")
        self._ensure(
            self.byok_plain_openai not in status_res.text, "BYOK status leaked plaintext key"
        )

        del_res = self._request("DELETE", "/v1/byok", params={"provider": "openai"})
        self._ensure(
            del_res.status == 200,
            f"/v1/byok delete expected 200, got {del_res.status}: {del_res.text[:240]}",
        )

    def check_rate_limit_behavior(self) -> None:
        if self.missing_b2b_surface:
            raise CheckSkipped(
                "skipped because B2B route surface is missing on this running server"
            )
        if self.args.skip_rate_limit:
            raise CheckSkipped("--skip-rate-limit enabled")
        if not self.db_mode:
            raise CheckSkipped("DB mode off; rate-limit exercise skipped")

        current_rpm = int((self.whoami.get("rate_limits") or {}).get("requests_per_minute") or 60)
        lower_payload = {"provider_keys": {}, "requests_per_minute": 1}
        set_low = self._request("POST", "/v1/byok", json_body=lower_payload)
        self._ensure(
            set_low.status == 200,
            f"failed to lower requests_per_minute for rate-limit test: {set_low.status} {set_low.text[:200]}",
        )

        try:
            p = {
                "prompt": "rate-limit-check",
                "provider": self.args.chat_provider,
                "model": self.args.chat_model,
            }
            first = self._request("POST", "/v1/chat", json_body=p)
            second = self._request("POST", "/v1/chat", json_body=p)
            self._ensure(
                first.status == 200,
                f"first chat for rate-limit check expected 200, got {first.status}",
            )
            self._ensure(
                second.status == 429,
                f"second chat expected 429, got {second.status}: {second.text[:220]}",
            )

            detail = second.json_body.get("detail") if isinstance(second.json_body, dict) else None
            if isinstance(detail, dict):
                self._ensure(
                    detail.get("code") == "rate_limited", f"unexpected 429 code payload: {detail}"
                )
        finally:
            restore_payload = {
                "provider_keys": {},
                "requests_per_minute": max(current_rpm, self.args.expected_min_rpm),
            }
            _ = self._request("POST", "/v1/byok", json_body=restore_payload)

    def check_db_assertions(self) -> None:
        if self.args.skip_db_assertions:
            raise CheckSkipped("--skip-db-assertions enabled")
        if not self.db_mode:
            raise CheckSkipped("DB mode off; DB assertions skipped")
        if not self._db_ready():
            raise CheckSkipped("DATABASE_URL and SQLAlchemy are required for DB assertions")

        self._ensure_db_engine()
        assert self.db_engine is not None
        assert text is not None

        chat_request_id = str(self.chat_resp.get("request_id") or "")
        compare_group_id = str(self.compare_resp.get("request_group_id") or "")
        compare_request_ids = [
            str(item.get("request_id"))
            for item in (self.compare_resp.get("responses") or [])
            if item.get("request_id")
        ]
        user_id = str(self.whoami.get("user_id") or "")
        api_key_id = str(self.whoami.get("api_key_id") or "")

        llm_requests = self._table_ref("llm_requests")
        llm_responses = self._table_ref("llm_responses")
        usage_daily = self._table_ref("usage_daily")
        byok_table = self._table_ref("byok_provider_keys")

        with self.db_engine.connect() as conn:
            req_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {llm_requests} WHERE request_id = :rid"),
                {"rid": chat_request_id},
            ).scalar_one()
            self._ensure(int(req_count or 0) >= 1, "llm_requests row missing for chat request_id")

            resp_count = conn.execute(
                text(f"""
                    SELECT COUNT(*)
                    FROM {llm_responses} r
                    JOIN {llm_requests} q ON q.id = r.llm_request_id
                    WHERE q.request_id = :rid
                    """),
                {"rid": chat_request_id},
            ).scalar_one()
            self._ensure(int(resp_count or 0) >= 1, "llm_responses row missing for chat request_id")

            for rid in compare_request_ids:
                group = conn.execute(
                    text(
                        f"SELECT request_group_id FROM {llm_requests} WHERE request_id = :rid LIMIT 1"
                    ),
                    {"rid": rid},
                ).scalar_one_or_none()
                self._ensure(group is not None, f"compare llm_request missing for request_id={rid}")
                self._ensure(
                    str(group) == compare_group_id, "compare request_group_id mismatch in DB"
                )

            usage_count = conn.execute(
                text(f"SELECT COUNT(*) FROM {usage_daily} WHERE user_id = :uid"),
                {"uid": user_id},
            ).scalar_one()
            self._ensure(int(usage_count or 0) >= 1, "usage_daily row missing for user")

            if not self.args.skip_byok and api_key_id:
                byok_row = conn.execute(
                    text(
                        f"SELECT encrypted_key, key_last4 FROM {byok_table} WHERE api_key_id = :kid AND provider = 'openai'"
                    ),
                    {"kid": api_key_id},
                ).first()
                if byok_row is not None:
                    enc, last4 = byok_row
                    self._ensure(
                        str(enc) != self.byok_plain_openai, "BYOK encrypted_key matches plaintext"
                    )
                    self._ensure(
                        str(last4 or "") == self.byok_plain_openai[-4:], "BYOK key_last4 mismatch"
                    )

    # ---------- orchestration ----------
    def run(self) -> int:
        checks = [
            ("health", self.check_health),
            ("openapi_surface", self.check_openapi_surface),
            ("whoami", self.check_whoami),
            ("chat", self.check_chat),
            ("chat_stream", self.check_chat_stream),
            ("compare", self.check_compare),
            ("compare_stream", self.check_compare_stream),
            ("admin_failed_attempts", self.check_admin_failed_attempts),
            ("history", self.check_history),
            ("reporting", self.check_reporting),
            ("exports", self.check_exports),
            ("byok_lifecycle", self.check_byok_lifecycle),
            ("db_assertions", self.check_db_assertions),
            ("rate_limit_behavior", self.check_rate_limit_behavior),
        ]
        for name, fn in checks:
            self._run_check(name, fn)

        passed = sum(1 for item in self.results if item.status == "PASS")
        failed = [item for item in self.results if item.status == "FAIL"]
        skipped = sum(1 for item in self.results if item.status == "SKIP")
        total = len(self.results)

        self._log("-" * 80)
        self._log(f"Summary: total={total} pass={passed} fail={len(failed)} skip={skipped}")
        for item in self.results:
            self._log(f"{item.status:4} | {item.name:24} | {item.detail}")

        if failed:
            self._log("Checklist failed.")
            return 1
        self._log("Checklist passed.")
        return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CortexAI B2B end-to-end API checklist.")
    parser.add_argument("--base-url", default=os.getenv("E2E_BASE_URL", "http://127.0.0.1:8000"))
    parser.add_argument(
        "--api-key",
        default=(
            os.getenv("E2E_API_KEY") or (os.getenv("API_KEYS", "dev-key-1").split(",")[0].strip())
        ),
    )
    parser.add_argument("--database-url", default=os.getenv("E2E_DATABASE_URL"))
    parser.add_argument("--db-schema", default=os.getenv("E2E_DB_SCHEMA"))
    parser.add_argument("--timeout-s", type=float, default=float(os.getenv("E2E_TIMEOUT_S", "60")))
    parser.add_argument("--chat-provider", default=os.getenv("E2E_CHAT_PROVIDER", "openai"))
    parser.add_argument("--chat-model", default=os.getenv("E2E_CHAT_MODEL", "gpt-4o-mini"))
    parser.add_argument("--compare-provider", default=os.getenv("E2E_COMPARE_PROVIDER", "gemini"))
    parser.add_argument(
        "--compare-model", default=os.getenv("E2E_COMPARE_MODEL", "gemini-2.5-flash-lite")
    )
    parser.add_argument("--max-stream-events", type=int, default=300)
    parser.add_argument("--expected-min-rpm", type=int, default=10)
    parser.add_argument("--allow-no-db-mode", action="store_true")
    parser.add_argument("--allow-missing-b2b-routes", action="store_true")
    parser.add_argument("--skip-stream", action="store_true")
    parser.add_argument("--skip-byok", action="store_true")
    parser.add_argument("--skip-db-assertions", action="store_true")
    parser.add_argument("--skip-rate-limit", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not args.api_key:
        print("[e2e] missing API key. Set --api-key or E2E_API_KEY/API_KEYS.")
        return 2

    runner = E2EB2BChecklist(args)
    return runner.run()


if __name__ == "__main__":
    raise SystemExit(main())
