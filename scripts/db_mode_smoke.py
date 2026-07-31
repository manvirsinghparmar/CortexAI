#!/usr/bin/env python3
"""DB mode smoke test for FastAPI persistence."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    Integer,
    MetaData,
    PrimaryKeyConstraint,
    String,
    Table,
    Uuid,
    create_engine,
    func,
    select,
    text,
)

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _bootstrap_sqlite_schema(database_url: str) -> None:
    engine = create_engine(database_url)
    metadata = MetaData()

    Table(
        "users",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("email", String, unique=True),
        Column("display_name", String),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("auth_provider", String),
        Column("auth_subject", String),
        Column("auth_issuer", String),
    )

    Table(
        "api_keys",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("user_id", Uuid, nullable=False),
        Column("key_hash", String, nullable=False, unique=True),
        Column("label", String),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("key_prefix", String),
        Column("key_last4", String),
        Column("last_used_at", DateTime),
    )

    Table(
        "sessions",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("user_id", Uuid, nullable=False),
        Column("title", String),
        Column("mode", String, nullable=False, default="ask"),
        Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
        Column("updated_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    )

    Table(
        "messages",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("session_id", Uuid, nullable=False),
        Column("role", String, nullable=False),
        Column("content", String, nullable=False),
        Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    )

    Table(
        "llm_requests",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("user_id", Uuid, nullable=False),
        Column("session_id", Uuid),
        Column("request_id", String, nullable=False),
        Column("route_mode", String, nullable=False),
        Column("provider", String, nullable=False),
        Column("model", String, nullable=False),
        Column("prompt_sha256", String, nullable=False),
        Column("prompt_stored", Boolean, nullable=False, default=False),
        Column("prompt_text", String),
        Column("input_tokens_est", Integer),
        Column("api_key_id", Uuid),
        Column("request_group_id", Uuid),
        Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    )

    Table(
        "llm_responses",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("llm_request_id", Uuid, nullable=False),
        Column("text", String),
        Column("finish_reason", String),
        Column("latency_ms", Integer),
        Column("prompt_tokens", Integer, nullable=False, default=0),
        Column("completion_tokens", Integer, nullable=False, default=0),
        Column("total_tokens", Integer, nullable=False, default=0),
        Column("estimated_cost", Float, nullable=False, default=0.0),
        Column("error_type", String),
        Column("error_message", String),
        Column("created_at", DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP")),
    )

    Table(
        "usage_daily",
        metadata,
        Column("user_id", Uuid, nullable=False),
        Column("usage_date", Date, nullable=False),
        Column("total_requests", Integer, nullable=False, default=0),
        Column("total_tokens", Integer, nullable=False, default=0),
        Column("total_cost", Float, nullable=False, default=0.0),
        PrimaryKeyConstraint("user_id", "usage_date"),
    )

    metadata.create_all(engine)


def main() -> int:
    db_file = Path(tempfile.gettempdir()) / "cortexai_release_gate_smoke.db"
    if db_file.exists():
        db_file.unlink()

    os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_file.as_posix()}"
    os.environ["DB_SCHEMA"] = "main"
    os.environ["API_KEYS"] = os.getenv("API_KEYS", "release-gate-key")
    os.environ["AUTO_REGISTER_UNMAPPED_API_KEYS"] = "true"

    _bootstrap_sqlite_schema(os.environ["DATABASE_URL"])
    smoke_user_id = uuid4()
    smoke_engine = create_engine(os.environ["DATABASE_URL"])
    with smoke_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO users "
                "(id, email, display_name, is_active, auth_provider, auth_subject) "
                "VALUES (:id, :email, :display_name, 1, :auth_provider, :auth_subject)"
            ),
            {
                "id": smoke_user_id.hex,
                "email": "release-gate@example.test",
                "display_name": "Release Gate",
                "auth_provider": "release_gate",
                "auth_subject": str(smoke_user_id),
            },
        )

    from fastapi.testclient import TestClient

    from models.unified_response import TokenUsage, UnifiedResponse
    from server import dependencies as deps
    from server.app import create_app
    from server.billing.enforcement_service import ReservedRequestUsage
    from server.routes import chat as chat_route

    class _FakeOrchestrator:
        def ask(
            self, prompt: str, model_type: str | None = None, context=None, **kwargs
        ) -> UnifiedResponse:
            return UnifiedResponse(
                request_id="release-gate-smoke-1",
                text="db-smoke-ok",
                provider=model_type or "openai",
                model=kwargs.get("model_name") or kwargs.get("model") or "gpt-4o-mini",
                latency_ms=5,
                token_usage=TokenUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
                estimated_cost=0.00001,
                finish_reason="stop",
                error=None,
                metadata={},
            )

    app = create_app()
    app.dependency_overrides[deps.get_orchestrator] = lambda: _FakeOrchestrator()
    app.dependency_overrides[deps.get_auth] = lambda: deps.AuthResult(
        api_key=None,
        cognito_claims=None,
        # SQLite reflection exposes UUID columns as strings in this deliberately
        # minimal smoke schema.
        user_id=smoke_user_id.hex,
    )
    # This smoke covers core request/response persistence using a deliberately
    # minimal SQLite schema. Subscription persistence has its own complete
    # schema, repository, metering, and route suites.
    smoke_reservation = ReservedRequestUsage(
        reservation_id=uuid4(),
        request_id="release-gate-smoke-1",
        operation_type="ask",
        requested_quantities={"ai_credits": 100_000},
        allowed_billing_classes=frozenset({"economical", "standard", "advanced", "premium"}),
        current_plan="pro",
        reset_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
    )
    chat_route._reserve_subscription_usage = lambda **_kwargs: smoke_reservation
    chat_route._finalize_subscription_usage = lambda **_kwargs: None
    chat_route._release_subscription_usage = lambda **_kwargs: None
    client = TestClient(app)

    response = client.post(
        "/v1/chat",
        json={"prompt": "db mode smoke", "provider": "openai", "model": "gpt-4o-mini"},
    )
    if response.status_code != 200:
        raise RuntimeError(f"DB smoke chat failed: {response.status_code} {response.text}")

    from db.session import SessionLocal
    from db.tables import get_table

    db_session = SessionLocal()
    try:
        llm_requests = get_table("llm_requests")
        usage_daily = get_table("usage_daily")

        llm_request_count = db_session.execute(
            select(func.count()).select_from(llm_requests)
        ).scalar_one()
        usage_daily_count = db_session.execute(
            select(func.count()).select_from(usage_daily)
        ).scalar_one()
    finally:
        db_session.close()

    if int(llm_request_count or 0) < 1:
        raise RuntimeError("DB smoke failed: expected at least 1 llm_requests row")
    if int(usage_daily_count or 0) < 1:
        raise RuntimeError("DB smoke failed: expected at least 1 usage_daily row")

    print(f"DB smoke passed (llm_requests={llm_request_count}, usage_daily={usage_daily_count})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
