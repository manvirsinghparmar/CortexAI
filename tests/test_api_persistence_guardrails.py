from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Boolean, Column, MetaData, String, Table, create_engine, insert, select
from sqlalchemy.orm import sessionmaker

import db.repository as repo
from models.unified_response import TokenUsage, UnifiedResponse
from server import dependencies as deps
from server.app import create_app
from server.routes import chat as chat_route
from server.utils import redact_sensitive_headers


class FakeOrchestrator:
    def __init__(self):
        self.ask_calls = 0

    def ask(self, prompt: str, model_type: str | None = None, context=None, **kwargs) -> UnifiedResponse:
        self.ask_calls += 1
        return UnifiedResponse(
            request_id="req_guardrail_1",
            text="ok",
            provider=model_type or "openai",
            model=kwargs.get("model_name") or kwargs.get("model") or "gpt-4o-mini",
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

    def compare(self, prompt: str, models_list, context=None, **kwargs):
        r1 = UnifiedResponse(
            request_id="req_cmp_guardrail_1",
            text="A",
            provider=models_list[0]["provider"],
            model=models_list[0].get("model") or "gpt-4o-mini",
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        r2 = UnifiedResponse(
            request_id="req_cmp_guardrail_2",
            text="B",
            provider=models_list[1]["provider"],
            model=models_list[1].get("model") or "gemini-2.5-flash-lite",
            latency_ms=12,
            token_usage=TokenUsage(prompt_tokens=6, completion_tokens=4, total_tokens=10),
            estimated_cost=0.00002,
            finish_reason="stop",
            error=None,
            metadata={},
        )
        return FakeMultiUnifiedResponse(request_group_id="11111111-1111-1111-1111-111111111111", responses=[r1, r2])


@dataclass(frozen=True)
class FakeMultiUnifiedResponse:
    request_group_id: str
    responses: list[UnifiedResponse]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success_count(self) -> int:
        return sum(1 for r in self.responses if r.is_success)

    @property
    def error_count(self) -> int:
        return sum(1 for r in self.responses if r.is_error)

    @property
    def total_tokens(self) -> int:
        return sum(r.token_usage.total_tokens for r in self.responses)

    @property
    def total_cost(self) -> float:
        return sum(r.estimated_cost for r in self.responses)


@pytest.fixture()
def fastapi_client(monkeypatch):
    monkeypatch.setenv("API_KEYS", "dev-key-1")

    app = create_app()
    if hasattr(deps.get_orchestrator, "_instance"):
        delattr(deps.get_orchestrator, "_instance")

    fake_orch = FakeOrchestrator()
    app.dependency_overrides[deps.get_orchestrator] = lambda: fake_orch
    return TestClient(app), fake_orch


def _make_fake_db_generator(session_obj):
    def _fake_get_db():
        yield session_obj

    return _fake_get_db


def _sqlite_repo_fixture(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()

    users = Table(
        "users",
        metadata,
        Column("id", String, primary_key=True, default=lambda: str(uuid4())),
        Column("email", String, unique=True),
        Column("display_name", String),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("auth_provider", String),
        Column("auth_subject", String),
        Column("auth_issuer", String),
    )

    api_keys = Table(
        "api_keys",
        metadata,
        Column("id", String, primary_key=True, default=lambda: str(uuid4())),
        Column("user_id", String, nullable=False),
        Column("key_hash", String, nullable=False, unique=True),
        Column("label", String),
        Column("is_active", Boolean, nullable=False, default=True),
        Column("key_prefix", String),
        Column("key_last4", String),
    )

    metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    db_session = SessionLocal()

    import db.tables as db_tables

    def _fake_get_table(name: str):
        if name == "users":
            return users
        if name == "api_keys":
            return api_keys
        raise ValueError(name)

    monkeypatch.setattr(db_tables, "get_table", _fake_get_table)
    return db_session, users, api_keys


@pytest.mark.unit
def test_create_api_key_returns_existing_owner_when_user_differs(monkeypatch):
    db_session, _users, api_keys = _sqlite_repo_fixture(monkeypatch)

    owner_user_id = str(uuid4())
    requested_user_id = str(uuid4())
    key_hash = repo.compute_api_key_hash("shared-dev-key")
    existing_api_key_id = str(uuid4())

    db_session.execute(
        insert(api_keys).values(
            id=existing_api_key_id,
            user_id=owner_user_id,
            key_hash=key_hash,
            label="existing",
            is_active=True,
            key_prefix="shared-dev-k",
            key_last4="-key",
        )
    )

    api_key_id, resolved_owner_user_id = repo.create_api_key(
        db_session,
        user_id=requested_user_id,
        raw_api_key="shared-dev-key",
        label="new-attempt",
    )

    assert api_key_id == existing_api_key_id
    assert resolved_owner_user_id == owner_user_id
    db_session.close()


@pytest.mark.unit
def test_get_or_create_service_user_uses_dedicated_identity(monkeypatch):
    db_session, users, _api_keys = _sqlite_repo_fixture(monkeypatch)

    cli_user_id = str(uuid4())
    db_session.execute(
        insert(users).values(
            id=cli_user_id,
            email="cli@cortexai.local",
            display_name="CLI User",
            is_active=True,
            auth_provider="cli",
            auth_subject="local-cli",
            auth_issuer="cortexai",
        )
    )

    service_user_id = repo.get_or_create_service_user(
        db_session,
        email="api@cortexai.local",
        display_name="API Service User",
    )
    service_user_id_2 = repo.get_or_create_service_user(
        db_session,
        email="api@cortexai.local",
        display_name="API Service User",
    )

    service_row = db_session.execute(
        select(users.c.auth_provider, users.c.auth_subject, users.c.auth_issuer).where(
            users.c.id == service_user_id
        )
    ).first()

    assert service_user_id == service_user_id_2
    assert service_user_id != cli_user_id
    assert service_row is not None
    assert service_row.auth_provider == "service"
    assert service_row.auth_subject == "api-service"
    assert service_row.auth_issuer == "cortexai"
    db_session.close()


@pytest.mark.integration
def test_chat_rejects_unmapped_key_by_default(fastapi_client, monkeypatch):
    client, fake_orch = fastapi_client

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

    monkeypatch.setattr(chat_route, "API_DB_ENABLED", True)
    monkeypatch.delenv("AUTO_REGISTER_UNMAPPED_API_KEYS", raising=False)
    monkeypatch.delenv("ALLOW_UNMAPPED_API_KEY_PERSIST", raising=False)
    monkeypatch.setattr(chat_route, "get_db", _make_fake_db_generator(DummySession()))
    monkeypatch.setattr(chat_route, "get_user_by_api_key", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        chat_route,
        "get_or_create_service_user",
        lambda *_args, **_kwargs: pytest.fail("service fallback should not run"),
    )

    response = client.post(
        "/v1/chat",
        headers={"X-API-Key": "dev-key-1"},
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4o-mini"},
    )

    assert response.status_code == 403
    assert fake_orch.ask_calls == 0


@pytest.mark.integration
def test_chat_persists_owner_and_request_id_match(fastapi_client, monkeypatch):
    client, _fake_orch = fastapi_client

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

    owner_user_id = uuid4()
    api_key_id = uuid4()
    persisted: dict[str, object] = {}

    monkeypatch.setattr(chat_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        chat_route,
        "_resolve_api_key_for_request",
        lambda *, api_key, request_id: chat_route.ApiKeyPersistenceResolution(
            user_id=owner_user_id,
            api_key_id=api_key_id,
            decision_path="mapped",
        ),
    )
    monkeypatch.setattr(chat_route, "get_db", _make_fake_db_generator(DummySession()))

    def _capture_create_llm_request(
        db_session,
        *,
        user_id,
        request_id,
        route_mode,
        provider,
        model,
        prompt,
        session_id,
        api_key_id,
        input_tokens_est,
        store_prompt,
    ):
        persisted["user_id"] = user_id
        persisted["request_id"] = request_id
        persisted["api_key_id"] = api_key_id
        return uuid4()

    monkeypatch.setattr(chat_route, "create_llm_request", _capture_create_llm_request)
    monkeypatch.setattr(chat_route, "create_llm_response", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(chat_route, "create_routing_decision", lambda *_args, **_kwargs: uuid4())
    monkeypatch.setattr(chat_route, "create_routing_attempts", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(chat_route, "upsert_usage_daily", lambda *_args, **_kwargs: None)

    response = client.post(
        "/v1/chat",
        headers={"X-API-Key": "dev-key-1"},
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4o-mini"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == persisted["request_id"]
    assert persisted["user_id"] == owner_user_id
    assert persisted["api_key_id"] == api_key_id


@pytest.mark.integration
def test_compare_persists_grouped_requests(fastapi_client, monkeypatch):
    client, _fake_orch = fastapi_client

    class DummySession:
        def commit(self):
            return None

        def rollback(self):
            return None

    owner_user_id = uuid4()
    api_key_id = uuid4()
    persisted_rows: list[dict[str, object]] = []

    import server.routes.compare as compare_route

    monkeypatch.setattr(compare_route, "API_DB_ENABLED", True)
    monkeypatch.setattr(
        compare_route,
        "_resolve_api_key_for_request",
        lambda *, api_key, request_id: compare_route.ApiKeyPersistenceResolution(
            user_id=owner_user_id,
            api_key_id=api_key_id,
            decision_path="mapped",
        ),
    )
    monkeypatch.setattr(compare_route, "get_db", _make_fake_db_generator(DummySession()))

    def _capture_compare_llm_request(
        db_session,
        *,
        user_id,
        request_id,
        route_mode,
        provider,
        model,
        prompt,
        session_id,
        request_group_id,
        api_key_id,
        input_tokens_est,
        store_prompt,
    ):
        persisted_rows.append(
            {
                "user_id": user_id,
                "request_id": request_id,
                "route_mode": route_mode,
                "request_group_id": request_group_id,
                "api_key_id": api_key_id,
            }
        )
        return uuid4()

    monkeypatch.setattr(compare_route, "create_llm_request", _capture_compare_llm_request)
    monkeypatch.setattr(compare_route, "create_llm_response", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(compare_route, "create_routing_decision", lambda *_args, **_kwargs: uuid4())
    monkeypatch.setattr(compare_route, "create_routing_attempts", lambda *_args, **_kwargs: 0)
    monkeypatch.setattr(compare_route, "upsert_usage_daily", lambda *_args, **_kwargs: None)

    response = client.post(
        "/v1/compare",
        headers={"X-API-Key": "dev-key-1"},
        json={
            "prompt": "Compare these models",
            "targets": [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(persisted_rows) == 2
    assert all(row["route_mode"] == "compare" for row in persisted_rows)
    assert all(row["user_id"] == owner_user_id for row in persisted_rows)
    assert all(row["api_key_id"] == api_key_id for row in persisted_rows)
    assert all(str(row["request_group_id"]) == body["request_group_id"] for row in persisted_rows)


@pytest.mark.unit
def test_trigger_migration_contains_owner_guard():
    migration_path = Path("db/migrations/20260218_llm_requests_api_key_owner_guard.sql")
    sql = migration_path.read_text(encoding="utf-8")

    assert "enforce_llm_request_api_key_owner_match" in sql
    assert "CREATE TRIGGER trg_llm_requests_enforce_api_key_owner" in sql
    assert "llm_requests.user_id" in sql
    assert "api_keys.user_id" in sql


@pytest.mark.unit
def test_request_group_id_migration_exists_and_has_indexes():
    migration_path = Path("db/migrations/20260218_add_request_group_id_to_llm_requests.sql")
    sql = migration_path.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS request_group_id uuid" in sql
    assert "idx_llm_requests_request_group_id" in sql
    assert "idx_llm_requests_user_request_group_id" in sql


@pytest.mark.unit
def test_redact_sensitive_headers_masks_auth_values():
    headers = {
        "X-API-Key": "dev-key-1",
        "Authorization": "Bearer abc",
        "Content-Type": "application/json",
    }

    redacted = redact_sensitive_headers(headers)

    assert redacted["X-API-Key"] == "[REDACTED]"
    assert redacted["Authorization"] == "[REDACTED]"
    assert redacted["Content-Type"] == "application/json"
