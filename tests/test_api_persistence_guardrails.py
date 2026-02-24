from contextlib import contextmanager
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
import tempfile
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import (
    JSON,
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
    insert,
    select,
    text,
)
from sqlalchemy.orm import sessionmaker

import db.repository as repo
from models.unified_response import MultiUnifiedResponse, TokenUsage, UnifiedResponse
from server import dependencies as deps
from server import persistence as persistence_service
from server.app import create_app
from server.routes import chat as chat_route
from server.routes import compare as compare_route
from server.routes import history as history_route
from server.utils import redact_sensitive_headers


class FakeOrchestrator:
    def __init__(self):
        self.ask_calls = 0
        self.compare_calls = 0

    def ask(self, prompt: str, model_type: str | None = None, context=None, **kwargs) -> UnifiedResponse:
        self.ask_calls += 1
        return UnifiedResponse(
            request_id="req_guardrail_ask_1",
            text="ok",
            provider=model_type or "openai",
            model=kwargs.get("model_name") or kwargs.get("model") or "gpt-4o-mini",
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={
                "routing": {
                    "mode": "smart",
                    "initial_tier": "T1",
                    "final_tier": "T1",
                    "attempt_count": 1,
                    "fallback_used": False,
                    "attempts": [
                        {
                            "attempt_number": 1,
                            "tier": "T1",
                            "provider": model_type or "openai",
                            "model": kwargs.get("model_name") or kwargs.get("model") or "gpt-4o-mini",
                            "validation": "ok",
                            "latency_ms": 10,
                        }
                    ],
                }
            },
        )

    def compare(self, prompt: str, models_list, context=None, **kwargs):
        self.compare_calls += 1
        r1 = UnifiedResponse(
            request_id="req_guardrail_cmp_1",
            text="A",
            provider=models_list[0]["provider"],
            model=models_list[0].get("model") or "gpt-4o-mini",
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={"routing": {"mode": "explicit", "attempts": []}},
        )
        r2 = UnifiedResponse(
            request_id="req_guardrail_cmp_2",
            text="B",
            provider=models_list[1]["provider"],
            model=models_list[1].get("model") or "gemini-2.5-flash-lite",
            latency_ms=12,
            token_usage=TokenUsage(prompt_tokens=6, completion_tokens=4, total_tokens=10),
            estimated_cost=0.00002,
            finish_reason="stop",
            error=None,
            metadata={"routing": {"mode": "explicit", "attempts": []}},
        )
        return MultiUnifiedResponse.from_responses(
            request_group_id="11111111-1111-1111-1111-111111111111",
            prompt=prompt,
            responses=[r1, r2],
        )


@dataclass
class DummySession:
    committed: int = 0
    rolled_back: int = 0

    def commit(self):
        self.committed += 1

    def rollback(self):
        self.rolled_back += 1


def _fake_db_uow_factory(session_obj):
    @contextmanager
    def _fake_db_uow(*, commit_on_success=True):
        yield session_obj

    return _fake_db_uow


@pytest.fixture()
def fastapi_client(monkeypatch):
    monkeypatch.setenv("API_KEYS", "dev-key-1")

    app = create_app()
    chat_route.API_DB_ENABLED = False
    compare_route.API_DB_ENABLED = False
    history_route.API_DB_ENABLED = False
    if hasattr(deps.get_orchestrator, "_instance"):
        delattr(deps.get_orchestrator, "_instance")

    fake_orch = FakeOrchestrator()
    app.dependency_overrides[deps.get_orchestrator] = lambda: fake_orch
    return TestClient(app), fake_orch


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


def _reset_db_runtime_state(*, schema_name: str = "public") -> None:
    import db.engine as db_engine
    import db.tables as db_tables

    with suppress(Exception):
        if db_engine._ENGINE is not None:
            db_engine._ENGINE.dispose()

    db_engine._ENGINE = None
    db_tables.DB_SCHEMA = schema_name
    db_tables._tables_cache.clear()
    db_tables.metadata.clear()


def _bootstrap_api_db_schema(database_url: str) -> None:
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

    Table(
        "routing_decisions",
        metadata,
        Column(
            "id",
            Uuid,
            primary_key=True,
            nullable=False,
            server_default=text("(lower(hex(randomblob(16))))"),
        ),
        Column("llm_request_id", Uuid, nullable=False, unique=True),
        Column("prompt_category", String, nullable=False),
        Column("research_mode", String, nullable=False),
        Column("routing_mode", String, nullable=False),
        Column("initial_tier", String),
        Column("final_tier", String),
        Column("attempt_count", Integer, nullable=False, default=1),
        Column("fallback_used", Boolean, nullable=False, default=False),
        Column("decision_reasons", JSON),
        Column("features", JSON),
        Column("trace", JSON),
    )

    Table(
        "routing_attempts",
        metadata,
        Column("routing_decision_id", Uuid, nullable=False),
        Column("attempt_number", Integer, nullable=False),
        Column("tier", String),
        Column("provider", String),
        Column("model", String),
        Column("validation", String),
        Column("latency_ms", Integer),
        Column("error_type", String),
        Column("error_message", String),
        PrimaryKeyConstraint("routing_decision_id", "attempt_number"),
    )

    metadata.create_all(engine)
    engine.dispose()


class DBModeCompareOrchestrator:
    def ask(self, prompt: str, model_type: str | None = None, context=None, **kwargs) -> UnifiedResponse:
        return UnifiedResponse(
            request_id=f"ask_{uuid4()}",
            text="ok",
            provider=model_type or "openai",
            model=kwargs.get("model_name") or kwargs.get("model") or "gpt-4o-mini",
            latency_ms=5,
            token_usage=TokenUsage(prompt_tokens=2, completion_tokens=3, total_tokens=5),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={},
        )

    def compare(self, prompt: str, models_list, context=None, **kwargs):
        request_group_id = str(uuid4())
        first_model = models_list[0].get("model") or "gpt-4o-mini"
        second_model = models_list[1].get("model") or "gemini-2.5-flash"

        r1 = UnifiedResponse(
            request_id=f"cmp_{uuid4()}",
            text="A",
            provider=models_list[0]["provider"],
            model=first_model,
            latency_ms=10,
            token_usage=TokenUsage(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            estimated_cost=0.00001,
            finish_reason="stop",
            error=None,
            metadata={
                "routing": {
                    "mode": "smart",
                    "initial_tier": "T1",
                    "final_tier": "T1",
                    "attempt_count": 1,
                    "fallback_used": False,
                    "attempts": [
                        {
                            "attempt_number": 1,
                            "tier": "T1",
                            "provider": models_list[0]["provider"],
                            "model": first_model,
                            "validation": "ok",
                            "latency_ms": 10,
                        }
                    ],
                }
            },
        )

        r2 = UnifiedResponse(
            request_id=f"cmp_{uuid4()}",
            text="B",
            provider=models_list[1]["provider"],
            model=second_model,
            latency_ms=12,
            token_usage=TokenUsage(prompt_tokens=6, completion_tokens=4, total_tokens=10),
            estimated_cost=0.00002,
            finish_reason="stop",
            error=None,
            metadata={
                "routing": {
                    "mode": "smart",
                    "initial_tier": "T1",
                    "final_tier": "T2",
                    "attempt_count": 2,
                    "fallback_used": True,
                    "attempts": [
                        {
                            "attempt_number": 1,
                            "tier": "T1",
                            "provider": "openai",
                            "model": "gpt-4o-mini",
                            "validation": "rate_limit",
                            "error_type": "rate_limit",
                            "error_message": "429 Too Many Requests",
                            "latency_ms": 9,
                        },
                        {
                            "attempt_number": 2,
                            "tier": "T2",
                            "provider": models_list[1]["provider"],
                            "model": second_model,
                            "validation": "ok",
                            "latency_ms": 11,
                        },
                    ],
                }
            },
        )

        return MultiUnifiedResponse.from_responses(
            request_group_id=request_group_id,
            prompt=prompt,
            responses=[r1, r2],
        )


@pytest.fixture()
def db_mode_fastapi_client(monkeypatch):
    from server.routes import admin as admin_route

    db_file = Path(tempfile.gettempdir()) / f"api_compare_group_{uuid4().hex}.sqlite"
    with suppress(FileNotFoundError):
        db_file.unlink()
    db_url = f"sqlite+pysqlite:///{db_file.as_posix()}"

    monkeypatch.setenv("DATABASE_URL", db_url)
    monkeypatch.setenv("DB_SCHEMA", "main")
    monkeypatch.setenv("API_KEYS", "dev-key-1")
    monkeypatch.setenv("AUTO_REGISTER_UNMAPPED_API_KEYS", "true")
    monkeypatch.delenv("DAILY_TOKEN_CAP", raising=False)
    monkeypatch.delenv("DAILY_COST_CAP", raising=False)
    monkeypatch.delenv("DAILY_CAP_SCOPE", raising=False)

    _reset_db_runtime_state(schema_name="main")
    _bootstrap_api_db_schema(db_url)

    old_persistence_db = persistence_service.API_DB_ENABLED
    old_chat_db = chat_route.API_DB_ENABLED
    old_compare_db = compare_route.API_DB_ENABLED
    old_history_db = history_route.API_DB_ENABLED
    old_admin_db = admin_route.API_DB_ENABLED

    persistence_service.API_DB_ENABLED = True
    chat_route.API_DB_ENABLED = True
    compare_route.API_DB_ENABLED = True
    history_route.API_DB_ENABLED = True
    admin_route.API_DB_ENABLED = True

    app = create_app()
    if hasattr(deps.get_orchestrator, "_instance"):
        delattr(deps.get_orchestrator, "_instance")

    fake_orch = DBModeCompareOrchestrator()
    app.dependency_overrides[deps.get_orchestrator] = lambda: fake_orch
    client = TestClient(app)

    try:
        yield client, fake_orch
    finally:
        client.close()
        persistence_service.API_DB_ENABLED = old_persistence_db
        chat_route.API_DB_ENABLED = old_chat_db
        compare_route.API_DB_ENABLED = old_compare_db
        history_route.API_DB_ENABLED = old_history_db
        admin_route.API_DB_ENABLED = old_admin_db
        _reset_db_runtime_state(schema_name="public")
        with suppress(FileNotFoundError):
            db_file.unlink()


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
def test_chat_persists_core_artifacts_in_db_mode(fastapi_client, monkeypatch):
    client, _fake_orch = fastapi_client

    owner_user_id = uuid4()
    api_key_id = uuid4()
    session_id = uuid4()
    llm_request_pk = uuid4()

    chat_route.API_DB_ENABLED = True

    monkeypatch.setattr(
        chat_route,
        "_resolve_and_enforce_caps",
        lambda **_kwargs: chat_route.ApiKeyPersistenceResolution(
            user_id=owner_user_id,
            api_key_id=api_key_id,
            decision_path="mapped",
        ),
    )

    dummy = DummySession()
    monkeypatch.setattr(persistence_service, "db_uow", _fake_db_uow_factory(dummy))
    monkeypatch.setattr(persistence_service, "get_or_create_api_session", lambda *_args, **_kwargs: session_id)

    calls: dict[str, list] = {
        "save_message": [],
        "create_llm_request": [],
        "create_llm_response": [],
        "routing": [],
        "usage": [],
    }

    monkeypatch.setattr(
        persistence_service,
        "save_message",
        lambda _db, _session_id, role, content: calls["save_message"].append((role, content)),
    )

    def _capture_create_llm_request(_db, **kwargs):
        calls["create_llm_request"].append(kwargs)
        return llm_request_pk

    monkeypatch.setattr(persistence_service, "create_llm_request", _capture_create_llm_request)
    monkeypatch.setattr(
        persistence_service,
        "create_llm_response",
        lambda _db, _llm_request_id, _response: calls["create_llm_response"].append(_llm_request_id),
    )
    monkeypatch.setattr(
        persistence_service,
        "persist_routing_telemetry",
        lambda *_args, **_kwargs: calls["routing"].append(True),
    )
    monkeypatch.setattr(persistence_service, "update_session_timestamp", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        persistence_service,
        "upsert_usage_daily",
        lambda _db, **kwargs: calls["usage"].append(kwargs),
    )
    monkeypatch.setattr(persistence_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)

    response = client.post(
        "/v1/chat",
        headers={"X-API-Key": "dev-key-1"},
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4o-mini"},
    )

    assert response.status_code == 200
    assert len(calls["create_llm_request"]) == 1
    assert len(calls["create_llm_response"]) == 1
    assert len(calls["routing"]) == 1
    assert len(calls["usage"]) == 1
    assert len(calls["save_message"]) >= 1

    req_kwargs = calls["create_llm_request"][0]
    assert req_kwargs["user_id"] == owner_user_id
    assert req_kwargs["api_key_id"] == api_key_id
    assert req_kwargs["session_id"] == session_id
    assert req_kwargs["route_mode"] == "ask"


@pytest.mark.integration
def test_compare_persists_grouped_rows_and_usage_in_db_mode(fastapi_client, monkeypatch):
    client, _fake_orch = fastapi_client

    owner_user_id = uuid4()
    api_key_id = uuid4()
    session_id = uuid4()

    compare_route.API_DB_ENABLED = True

    monkeypatch.setattr(
        compare_route,
        "_resolve_and_enforce_caps",
        lambda **_kwargs: compare_route.ApiKeyPersistenceResolution(
            user_id=owner_user_id,
            api_key_id=api_key_id,
            decision_path="mapped",
        ),
    )

    dummy = DummySession()
    monkeypatch.setattr(persistence_service, "db_uow", _fake_db_uow_factory(dummy))
    monkeypatch.setattr(persistence_service, "get_or_create_api_session", lambda *_args, **_kwargs: session_id)

    llm_req_calls = []
    usage_calls = []

    monkeypatch.setattr(persistence_service, "save_message", lambda *_args, **_kwargs: None)

    def _capture_llm_req(_db, **kwargs):
        llm_req_calls.append(kwargs)
        return uuid4()

    monkeypatch.setattr(persistence_service, "create_llm_request", _capture_llm_req)
    monkeypatch.setattr(persistence_service, "create_llm_response", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(persistence_service, "persist_routing_telemetry", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(persistence_service, "save_compare_summary", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(persistence_service, "update_session_timestamp", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        persistence_service,
        "upsert_usage_daily",
        lambda _db, **kwargs: usage_calls.append(kwargs),
    )
    monkeypatch.setattr(persistence_service, "update_api_key_last_used", lambda *_args, **_kwargs: None)

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

    assert len(llm_req_calls) == 2
    assert all(call["user_id"] == owner_user_id for call in llm_req_calls)
    assert all(call["api_key_id"] == api_key_id for call in llm_req_calls)
    assert all(call["route_mode"] == "compare" for call in llm_req_calls)
    assert all(str(call["request_group_id"]) == body["request_group_id"] for call in llm_req_calls)

    assert len(usage_calls) == 1
    assert usage_calls[0]["total_tokens"] == body["total_tokens"]
    assert usage_calls[0]["estimated_cost"] == body["total_cost"]


@pytest.mark.integration
def test_compare_request_group_id_matches_response_and_persisted_rows(db_mode_fastapi_client):
    client, _fake_orch = db_mode_fastapi_client

    response = client.post(
        "/v1/compare",
        headers={"X-API-Key": "dev-key-1"},
        json={
            "prompt": "Compare persistence group id consistency",
            "targets": [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    request_group_id = body["request_group_id"]
    request_ids = {item["request_id"] for item in body["responses"]}

    from db.session import SessionLocal
    from db.tables import get_table

    db_session = SessionLocal()
    try:
        llm_requests = get_table("llm_requests")
        rows = db_session.execute(
            select(llm_requests.c.request_id, llm_requests.c.request_group_id).where(
                llm_requests.c.request_id.in_(request_ids)
            )
        ).fetchall()
    finally:
        db_session.close()

    assert len(rows) == len(body["responses"])
    persisted_request_ids = {row[0] for row in rows}
    persisted_group_ids = {str(UUID(str(row[1]))) for row in rows}

    assert persisted_request_ids == request_ids
    assert persisted_group_ids == {str(UUID(request_group_id))}


@pytest.mark.integration
def test_admin_failed_attempts_view_by_request_group_id(db_mode_fastapi_client):
    client, _fake_orch = db_mode_fastapi_client

    compare_response = client.post(
        "/v1/compare",
        headers={"X-API-Key": "dev-key-1"},
        json={
            "prompt": "Compare and inspect failed attempts",
            "targets": [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
            ],
        },
    )
    assert compare_response.status_code == 200
    request_group_id = compare_response.json()["request_group_id"]

    debug_response = client.get(
        f"/v1/admin/request-groups/{request_group_id}/failed-attempts",
        headers={"X-API-Key": "dev-key-1"},
    )
    assert debug_response.status_code == 200

    payload = debug_response.json()
    assert payload["request_group_id"] == request_group_id
    assert payload["count"] >= 1
    assert len(payload["items"]) == payload["count"]
    assert all(item["request_group_id"] == request_group_id for item in payload["items"])
    assert any(
        (item.get("validation") not in (None, "ok"))
        or item.get("error_type")
        or item.get("error_message")
        for item in payload["items"]
    )


@pytest.mark.integration
def test_daily_caps_enforced_in_api_db_mode(fastapi_client, monkeypatch):
    client, fake_orch = fastapi_client

    chat_route.API_DB_ENABLED = True
    monkeypatch.setenv("DAILY_TOKEN_CAP", "1")
    monkeypatch.delenv("DAILY_COST_CAP", raising=False)
    monkeypatch.setenv("DAILY_CAP_SCOPE", "user")

    user_id = uuid4()
    api_key_id = uuid4()

    class _CapSession:
        pass

    monkeypatch.setattr(persistence_service, "db_uow", _fake_db_uow_factory(_CapSession()))

    monkeypatch.setattr(
        persistence_service,
        "check_usage_limit",
        lambda *_args, **_kwargs: {
            "allowed": False,
            "current_tokens": 100,
            "current_cost": 5.0,
            "reason": "Daily token limit exceeded (100/1)",
        },
    )

    monkeypatch.setattr(
        chat_route,
        "_resolve_and_enforce_caps",
        lambda **_kwargs: (
            persistence_service.enforce_usage_caps(user_id=user_id, api_key_id=api_key_id),
            chat_route.ApiKeyPersistenceResolution(
                user_id=user_id,
                api_key_id=api_key_id,
                decision_path="mapped",
            ),
        )[1],
    )

    response = client.post(
        "/v1/chat",
        headers={"X-API-Key": "dev-key-1"},
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4o-mini"},
    )

    assert response.status_code == 429
    assert fake_orch.ask_calls == 0


@pytest.mark.integration
def test_stream_routes_persist_once_in_db_mode(fastapi_client, monkeypatch):
    client, _fake_orch = fastapi_client

    chat_route.API_DB_ENABLED = True
    compare_route.API_DB_ENABLED = True

    monkeypatch.setattr(
        chat_route,
        "_resolve_and_enforce_caps",
        lambda **_kwargs: chat_route.ApiKeyPersistenceResolution(
            user_id=uuid4(),
            api_key_id=uuid4(),
            decision_path="mapped",
        ),
    )
    chat_persist_calls = []
    monkeypatch.setattr(
        chat_route,
        "_persist_chat_interaction",
        lambda **kwargs: chat_persist_calls.append(kwargs),
    )

    monkeypatch.setattr(
        compare_route,
        "_resolve_and_enforce_caps",
        lambda **_kwargs: compare_route.ApiKeyPersistenceResolution(
            user_id=uuid4(),
            api_key_id=uuid4(),
            decision_path="mapped",
        ),
    )
    compare_persist_calls = []
    monkeypatch.setattr(
        compare_route,
        "_persist_compare_interaction",
        lambda **kwargs: compare_persist_calls.append(kwargs),
    )

    chat_resp = client.post(
        "/v1/chat/stream",
        headers={"X-API-Key": "dev-key-1"},
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4o-mini"},
    )
    assert chat_resp.status_code == 200
    assert len(chat_persist_calls) == 1

    cmp_resp = client.post(
        "/v1/compare/stream",
        headers={"X-API-Key": "dev-key-1"},
        json={
            "prompt": "hello",
            "targets": [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
            ],
        },
    )
    assert cmp_resp.status_code == 200
    assert len(compare_persist_calls) == 1


@pytest.mark.integration
def test_api_works_without_db_and_history_endpoints_still_function(fastapi_client, monkeypatch):
    client, fake_orch = fastapi_client

    chat_route.API_DB_ENABLED = False
    compare_route.API_DB_ENABLED = False
    history_route.API_DB_ENABLED = False

    sqlite_saves = []
    monkeypatch.setattr(
        "server.database.save_chat",
        lambda **kwargs: sqlite_saves.append(kwargs),
    )

    monkeypatch.setattr(
        history_route,
        "get_history",
        lambda limit=100: [
            {
                "id": 1,
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "mode": "chat",
                "prompt": "hello",
                "provider": "openai",
                "model": "gpt-4o-mini",
                "response": "ok",
                "latency_ms": 10,
                "tokens": 5,
                "cost": 0.00001,
            }
        ],
    )
    monkeypatch.setattr(history_route, "delete_history_entry", lambda _entry_id: True)

    cleared = []
    monkeypatch.setattr(history_route, "clear_all_history", lambda: cleared.append(True))

    chat_response = client.post(
        "/v1/chat",
        headers={"X-API-Key": "dev-key-1"},
        json={"prompt": "hello", "provider": "openai", "model": "gpt-4o-mini"},
    )
    assert chat_response.status_code == 200

    compare_response = client.post(
        "/v1/compare",
        headers={"X-API-Key": "dev-key-1"},
        json={
            "prompt": "hello",
            "targets": [
                {"provider": "openai", "model": "gpt-4o-mini"},
                {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
            ],
        },
    )
    assert compare_response.status_code == 200

    history_list = client.get("/v1/history", headers={"X-API-Key": "dev-key-1"})
    assert history_list.status_code == 200
    assert isinstance(history_list.json(), list)

    history_delete = client.delete("/v1/history/1", headers={"X-API-Key": "dev-key-1"})
    assert history_delete.status_code == 204

    history_clear = client.delete("/v1/history", headers={"X-API-Key": "dev-key-1"})
    assert history_clear.status_code == 204

    assert fake_orch.ask_calls >= 1
    assert fake_orch.compare_calls >= 1
    assert len(sqlite_saves) >= 1
    assert cleared == [True]


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
def test_go_live_hardening_migration_has_savings_status_and_reporting_indexes():
    migration_path = Path("db/migrations/20260222_go_live_hardening.sql")
    sql = migration_path.read_text(encoding="utf-8")

    assert "ADD COLUMN IF NOT EXISTS response_status" in sql
    assert "ADD COLUMN IF NOT EXISTS error_code" in sql
    assert "idx_llm_requests_user_created_at" in sql
    assert "idx_llm_requests_api_key_created_at" in sql
    assert "idx_llm_savings_user_created_at" in sql
    assert "idx_llm_savings_api_key_created_at" in sql


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
