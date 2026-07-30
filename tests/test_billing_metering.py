from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Uuid,
    create_engine,
    func,
    select,
)
from sqlalchemy.orm import sessionmaker

from db import billing_repository as repository
from server.billing.credit_calculator import ADVANCED_WEB_SEARCH_CREDITS
from server.billing.enforcement_service import (
    BillableModelUsage,
    authorize_and_reserve_usage,
    finalize_reserved_usage,
)
from server.billing.entitlement_service import ModelTargetIntent
from server.billing.errors import (
    EntitlementDeniedError,
    UsageReservationConflictError,
)
from server.billing.metering_service import (
    expire_stale_reservations,
    release_usage,
    reserve_usage,
    settle_usage,
)
from server.billing.plan_catalog import get_plan_catalog
from server.billing.subscription_service import EffectiveSubscription


@pytest.fixture()
def metering_db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    metadata = MetaData()
    users = Table(
        "users",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("email", String, unique=True),
    )
    billing_accounts = Table(
        "billing_accounts",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("owner_type", String(32), nullable=False),
        Column("owner_id", Uuid, nullable=False),
        Column("stripe_customer_id", String(255), unique=True),
        Column("currency", String(3), nullable=False, server_default="USD"),
        Column("country", String(2)),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Index("uq_billing_accounts_owner", "owner_type", "owner_id", unique=True),
    )
    usage_periods = Table(
        "usage_periods",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("billing_account_id", Uuid, ForeignKey("billing_accounts.id"), nullable=False),
        Column("subscription_id", Uuid),
        Column("plan_code", String(64), nullable=False),
        Column("starts_at", DateTime(timezone=True), nullable=False),
        Column("ends_at", DateTime(timezone=True), nullable=False),
        Column("status", String(32), nullable=False, server_default="active"),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Index("uq_usage_period_account_start", "billing_account_id", "starts_at", unique=True),
    )
    usage_counters = Table(
        "usage_counters",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("usage_period_id", Uuid, ForeignKey("usage_periods.id"), nullable=False),
        Column("meter_key", String(64), nullable=False),
        Column("used_quantity", BigInteger, nullable=False, server_default="0"),
        Column("reserved_quantity", BigInteger, nullable=False, server_default="0"),
        Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Index("uq_usage_counter_period_meter", "usage_period_id", "meter_key", unique=True),
    )
    usage_reservations = Table(
        "usage_reservations",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("billing_account_id", Uuid, ForeignKey("billing_accounts.id"), nullable=False),
        Column("usage_period_id", Uuid, ForeignKey("usage_periods.id"), nullable=False),
        Column("request_id", String(255), nullable=False),
        Column("operation_type", String(64), nullable=False),
        Column("state", String(32), nullable=False),
        Column("requested_quantities", JSON, nullable=False),
        Column("settled_quantities", JSON),
        Column("release_reason", String(255)),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("settled_at", DateTime(timezone=True)),
        Column("released_at", DateTime(timezone=True)),
        Index("uq_usage_reservations_request", "billing_account_id", "request_id", unique=True),
    )
    credit_transactions = Table(
        "credit_transactions",
        metadata,
        Column("id", Uuid, primary_key=True),
        Column("billing_account_id", Uuid, ForeignKey("billing_accounts.id"), nullable=False),
        Column("usage_period_id", Uuid, ForeignKey("usage_periods.id"), nullable=False),
        Column("reservation_id", Uuid, ForeignKey("usage_reservations.id")),
        Column("request_id", String(255), nullable=False),
        Column("operation_type", String(64), nullable=False),
        Column("item_index", Integer, nullable=False, server_default="0"),
        Column("item_type", String(32), nullable=False),
        Column("provider", String(64)),
        Column("model", String(255)),
        Column("input_tokens", BigInteger, nullable=False, server_default="0"),
        Column("output_tokens", BigInteger, nullable=False, server_default="0"),
        Column("input_credits", BigInteger, nullable=False, server_default="0"),
        Column("output_credits", BigInteger, nullable=False, server_default="0"),
        Column("fixed_credits", BigInteger, nullable=False, server_default="0"),
        Column("total_credits", BigInteger, nullable=False),
        Column("provider_cost_usd", Float, nullable=False, server_default="0"),
        Column("usage_estimated", Boolean, nullable=False, server_default="0"),
        Column("pricing_version", String(64), nullable=False),
        Column("metadata", JSON, nullable=False, server_default="{}"),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Index(
            "uq_credit_transactions_reservation_item",
            "reservation_id",
            "item_index",
            unique=True,
        ),
    )
    tables = {
        table.name: table
        for table in (
            users,
            billing_accounts,
            usage_periods,
            usage_counters,
            usage_reservations,
            credit_transactions,
        )
    }
    metadata.create_all(engine)
    import db.tables as db_tables

    monkeypatch.setattr(db_tables, "get_table", tables.__getitem__)
    monkeypatch.setenv("BILLING_ENABLED", "false")
    monkeypatch.delenv("DEV_SUBSCRIPTION_PLAN", raising=False)
    db = sessionmaker(bind=engine)()
    try:
        yield db, tables
    finally:
        db.close()
        engine.dispose()


def _effective(db, plan_code: str = "free") -> EffectiveSubscription:
    account = repository.get_or_create_billing_account_for_user(db, uuid4())
    starts_at = datetime(2026, 7, 1, tzinfo=UTC)
    ends_at = datetime(2026, 8, 1, tzinfo=UTC)
    period = repository.create_usage_period(
        db,
        billing_account_id=account["id"],
        plan_code=plan_code,
        starts_at=starts_at,
        ends_at=ends_at,
    )
    return EffectiveSubscription(
        billing_account_id=account["id"],
        usage_period_id=period["id"],
        plan=get_plan_catalog().require(plan_code),
        source="test",
        provider=None,
        provider_subscription_id=None,
        status="free",
        current_period_start=starts_at,
        current_period_end=ends_at,
        cancel_at_period_end=False,
        grace_until=None,
    )


def _user(db, tables):
    user_id = uuid4()
    db.execute(tables["users"].insert().values(id=user_id, email=f"{user_id}@example.com"))
    return user_id


def _counter(db, tables, period_id):
    return db.execute(
        select(tables["usage_counters"]).where(
            tables["usage_counters"].c.usage_period_id == period_id,
            tables["usage_counters"].c.meter_key == "ai_credits",
        )
    ).mappings().one()


def test_credit_reservation_is_idempotent_and_conflict_safe(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    first = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="same",
        operation_type="ask",
        requested_quantities={"ai_credits": 20_000},
    )
    repeated = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="same",
        operation_type="ask",
        requested_quantities={"ai_credits": 20_000},
    )
    assert repeated.id == first.id
    assert _counter(db, tables, effective.usage_period_id)["reserved_quantity"] == 20_000
    with pytest.raises(UsageReservationConflictError):
        reserve_usage(
            db,
            effective_subscription=effective,
            request_id="same",
            operation_type="ask",
            requested_quantities={"ai_credits": 20_001},
        )


def test_settle_and_release_move_only_the_unified_counter(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    settled = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="settle",
        operation_type="ask",
        requested_quantities={"ai_credits": 10_000},
    )
    settle_usage(
        db,
        reservation_id=settled.id,
        successful_quantities={"ai_credits": 3_000},
    )
    counter = _counter(db, tables, effective.usage_period_id)
    assert (counter["used_quantity"], counter["reserved_quantity"]) == (3_000, 0)

    released = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="release",
        operation_type="ask",
        requested_quantities={"ai_credits": 5_000},
    )
    release_usage(db, reservation_id=released.id, reason="provider_failed")
    counter = _counter(db, tables, effective.usage_period_id)
    assert (counter["used_quantity"], counter["reserved_quantity"]) == (3_000, 0)


def test_stale_reservations_release_credit_capacity(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    reservation = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="stale",
        operation_type="ask",
        requested_quantities={"ai_credits": 4_000},
    )
    db.execute(
        tables["usage_reservations"]
        .update()
        .where(tables["usage_reservations"].c.id == reservation.id)
        .values(created_at=datetime.now(UTC) - timedelta(hours=1))
    )
    assert expire_stale_reservations(
        db,
        older_than=datetime.now(UTC) - timedelta(minutes=30),
    ) == 1
    assert _counter(db, tables, effective.usage_period_id)["reserved_quantity"] == 0


def test_actual_model_tokens_settle_and_create_reconciliation_item(metering_db):
    db, tables = metering_db
    reservation = authorize_and_reserve_usage(
        db,
        user_id=_user(db, tables),
        request_id="ask-actual",
        operation_type="ask",
        model_targets=(ModelTargetIntent("openai", "gpt-4.1-mini", "standard"),),
        research_enabled=False,
        input_text="Explain atomic reservations.",
        max_output_tokens=500,
    )
    reserved = reservation.requested_quantities["ai_credits"]
    finalize_reserved_usage(
        db,
        reservation=reservation,
        model_usages=(
            BillableModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=100,
                output_tokens=200,
                provider_cost_usd=0.001,
            ),
        ),
        research_performed=False,
        file_analysis_performed=True,
    )
    counter = _counter(
        db,
        tables,
        repository.get_usage_reservation_by_id(db, reservation.reservation_id)[
            "usage_period_id"
        ],
    )
    assert counter["used_quantity"] == 900
    assert counter["reserved_quantity"] == 0
    assert counter["used_quantity"] < reserved
    item = db.execute(select(tables["credit_transactions"])).mappings().one()
    assert item["input_credits"] == 100
    assert item["output_credits"] == 800
    assert item["usage_estimated"] is False
    assert item["metadata"] == {
        "file_context": True,
        "prompt_optimization": False,
    }


def test_compare_partial_success_charges_only_delivered_model(metering_db):
    db, tables = metering_db
    reservation = authorize_and_reserve_usage(
        db,
        user_id=_user(db, tables),
        request_id="compare-partial",
        operation_type="compare",
        model_targets=(
            ModelTargetIntent("openai", "gpt-4.1-mini", "standard"),
            ModelTargetIntent("gemini", "gemini-2.5-flash", "standard"),
        ),
        research_enabled=False,
        input_text="Compare two approaches.",
        max_output_tokens=300,
    )
    finalize_reserved_usage(
        db,
        reservation=reservation,
        model_usages=(
            BillableModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=50,
                output_tokens=100,
            ),
        ),
        research_performed=False,
    )
    items = db.execute(select(tables["credit_transactions"])).mappings().all()
    assert [(item["provider"], item["model"]) for item in items] == [
        ("openai", "gpt-4.1-mini")
    ]
    assert sum(item["total_credits"] for item in items) == 450


def test_successful_research_remains_charged_when_model_fails(metering_db):
    db, tables = metering_db
    reservation = authorize_and_reserve_usage(
        db,
        user_id=_user(db, tables),
        request_id="research-only",
        operation_type="ask",
        model_targets=(ModelTargetIntent("openai", "gpt-4.1-mini", "standard"),),
        research_enabled=True,
        input_text="Current facts",
        max_output_tokens=200,
    )
    finalize_reserved_usage(
        db,
        reservation=reservation,
        model_usages=(),
        research_performed=True,
    )
    item = db.execute(select(tables["credit_transactions"])).mappings().one()
    assert item["item_type"] == "research"
    assert item["total_credits"] == ADVANCED_WEB_SEARCH_CREDITS


def test_missing_provider_usage_is_estimated_and_marked(metering_db):
    db, tables = metering_db
    reservation = authorize_and_reserve_usage(
        db,
        user_id=_user(db, tables),
        request_id="estimated",
        operation_type="ask",
        model_targets=(ModelTargetIntent("openai", "gpt-4.1-mini", "standard"),),
        research_enabled=False,
        input_text="A short prompt",
        max_output_tokens=200,
    )
    finalize_reserved_usage(
        db,
        reservation=reservation,
        model_usages=(
            BillableModelUsage(
                provider="openai",
                model="gpt-4.1-mini",
                input_tokens=0,
                output_tokens=0,
                output_text="A short answer.",
            ),
        ),
        research_performed=False,
    )
    item = db.execute(select(tables["credit_transactions"])).mappings().one()
    assert item["usage_estimated"] is True
    assert item["total_credits"] > 0


def test_insufficient_credits_prevents_reservation(metering_db):
    db, tables = metering_db
    user_id = _user(db, tables)
    account = repository.get_or_create_billing_account_for_user(db, user_id)
    starts_at = datetime(2026, 7, 1, tzinfo=UTC)
    period = repository.create_usage_period(
        db,
        billing_account_id=account["id"],
        plan_code="free",
        starts_at=starts_at,
        ends_at=datetime(2026, 8, 1, tzinfo=UTC),
    )
    counter = repository.get_or_create_usage_counter(db, period["id"], "ai_credits")
    db.execute(
        tables["usage_counters"]
        .update()
        .where(tables["usage_counters"].c.id == counter["id"])
        .values(used_quantity=99_999)
    )
    with pytest.raises(EntitlementDeniedError) as exc_info:
        authorize_and_reserve_usage(
            db,
            user_id=user_id,
            request_id="too-expensive",
            operation_type="ask",
            model_targets=(ModelTargetIntent("openai", "gpt-4.1-mini", "standard"),),
            research_enabled=False,
            input_text="Cannot fit",
            max_output_tokens=100,
        )
    assert exc_info.value.denial.code == "insufficient_credits"
    assert exc_info.value.denial.required > exc_info.value.denial.remaining
    assert exc_info.value.denial.remaining == 1
    assert db.execute(select(tables["usage_reservations"])).all() == []


def test_smart_routing_reserves_allowed_worst_case_and_settles_actual(metering_db):
    db, tables = metering_db
    reservation = authorize_and_reserve_usage(
        db,
        user_id=_user(db, tables),
        request_id="smart",
        operation_type="ask",
        model_targets=(ModelTargetIntent("openai", "gpt-4.1-mini", "standard"),),
        research_enabled=False,
        smart_routing=True,
        input_text="Route this",
        max_output_tokens=100,
    )
    assert reservation.allowed_billing_classes == frozenset({"economical", "standard"})
    reserved = reservation.requested_quantities["ai_credits"]
    finalize_reserved_usage(
        db,
        reservation=reservation,
        model_usages=(
            BillableModelUsage(
                provider="deepseek",
                model="deepseek-chat",
                input_tokens=20,
                output_tokens=40,
            ),
        ),
        research_performed=False,
    )
    persisted = repository.get_usage_reservation_by_id(db, reservation.reservation_id)
    assert persisted["settled_quantities"]["ai_credits"] == 50
    assert reserved > 50
