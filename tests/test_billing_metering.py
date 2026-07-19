from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Index,
    MetaData,
    String,
    Table,
    Uuid,
    create_engine,
    func,
    select,
    update,
)
from sqlalchemy.orm import sessionmaker

from db import billing_repository as repository
from server.billing.errors import (
    UsageAllowanceExceededError,
    UsageReservationConflictError,
    UsageReservationStateError,
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
        CheckConstraint("owner_type IN ('user', 'organization')"),
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
        CheckConstraint("ends_at > starts_at"),
        Index(
            "uq_usage_period_account_start",
            "billing_account_id",
            "starts_at",
            unique=True,
        ),
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
        CheckConstraint("used_quantity >= 0 AND reserved_quantity >= 0"),
        Index(
            "uq_usage_counter_period_meter",
            "usage_period_id",
            "meter_key",
            unique=True,
        ),
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
        CheckConstraint("state IN ('reserved', 'settled', 'released', 'expired')"),
        Index(
            "uq_usage_reservations_request",
            "billing_account_id",
            "request_id",
            unique=True,
        ),
    )
    tables = {
        table.name: table
        for table in (
            billing_accounts,
            usage_periods,
            usage_counters,
            usage_reservations,
        )
    }
    metadata.create_all(engine)

    import db.tables as db_tables

    monkeypatch.setattr(db_tables, "get_table", tables.__getitem__)
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
        status="active" if plan_code != "free" else "free",
        current_period_start=starts_at,
        current_period_end=ends_at,
        cancel_at_period_end=False,
        grace_until=None,
    )


def _counter(db, tables, effective, meter):
    return (
        db.execute(
            select(tables["usage_counters"]).where(
                tables["usage_counters"].c.usage_period_id == effective.usage_period_id,
                tables["usage_counters"].c.meter_key == meter,
            )
        )
        .mappings()
        .one()
    )


@pytest.mark.unit
def test_reserve_is_exactly_idempotent_and_rejects_reused_request_ids(metering_db):
    db, tables = metering_db
    effective = _effective(db)

    first = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-idempotent",
        operation_type="ask",
        requested_quantities={"model_responses": 1},
    )
    duplicate = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-idempotent",
        operation_type="ask",
        requested_quantities={"model_responses": 1},
    )

    assert duplicate.id == first.id
    assert _counter(db, tables, effective, "model_responses")["reserved_quantity"] == 1

    with pytest.raises(UsageReservationConflictError):
        reserve_usage(
            db,
            effective_subscription=effective,
            request_id="req-idempotent",
            operation_type="compare",
            requested_quantities={"model_responses": 2},
        )


@pytest.mark.unit
def test_allowance_denial_does_not_partially_reserve_other_meters(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    for meter in ("advanced_model_responses", "model_responses"):
        repository.get_or_create_usage_counter(db, effective.usage_period_id, meter)
    db.execute(
        update(tables["usage_counters"])
        .where(
            tables["usage_counters"].c.usage_period_id == effective.usage_period_id,
            tables["usage_counters"].c.meter_key == "advanced_model_responses",
        )
        .values(used_quantity=effective.plan.allowances.advanced_model_responses)
    )

    with pytest.raises(UsageAllowanceExceededError) as exc_info:
        reserve_usage(
            db,
            effective_subscription=effective,
            request_id="req-denied",
            operation_type="ask",
            requested_quantities={
                "model_responses": 1,
                "advanced_model_responses": 1,
            },
        )

    assert exc_info.value.meter == "advanced_model_responses"
    assert exc_info.value.remaining == 0
    assert _counter(db, tables, effective, "model_responses")["reserved_quantity"] == 0
    assert (
        repository.get_usage_reservation(
            db,
            effective.billing_account_id,
            "req-denied",
        )
        is None
    )


@pytest.mark.unit
def test_partial_settlement_moves_only_successful_units_to_used(metering_db):
    db, tables = metering_db
    effective = _effective(db, "plus")
    reservation = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-partial",
        operation_type="compare",
        requested_quantities={
            "model_responses": 2,
            "advanced_model_responses": 2,
        },
    )

    settled = settle_usage(
        db,
        reservation_id=reservation.id,
        successful_quantities={
            "model_responses": 1,
            "advanced_model_responses": 1,
        },
        settlement_metadata={"successful_targets": [0]},
    )
    duplicate = settle_usage(
        db,
        reservation_id=reservation.id,
        successful_quantities={
            "model_responses": 1,
            "advanced_model_responses": 1,
        },
    )

    assert settled.state == "settled"
    assert duplicate.id == settled.id
    for meter in ("model_responses", "advanced_model_responses"):
        counter = _counter(db, tables, effective, meter)
        assert counter["used_quantity"] == 1
        assert counter["reserved_quantity"] == 0

    with pytest.raises(UsageReservationConflictError):
        settle_usage(
            db,
            reservation_id=reservation.id,
            successful_quantities={"model_responses": 2},
        )
    with pytest.raises(UsageReservationStateError):
        release_usage(db, reservation_id=reservation.id, reason="provider_error")


@pytest.mark.unit
def test_release_is_idempotent_and_never_increments_used_quantity(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    reservation = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-release",
        operation_type="ask",
        requested_quantities={"model_responses": 1},
    )

    released = release_usage(db, reservation_id=reservation.id, reason="provider_error")
    duplicate = release_usage(db, reservation_id=reservation.id, reason="retry")
    counter = _counter(db, tables, effective, "model_responses")

    assert released.state == "released"
    assert duplicate.id == released.id
    assert duplicate.release_reason == "provider_error"
    assert counter["used_quantity"] == 0
    assert counter["reserved_quantity"] == 0


@pytest.mark.unit
def test_stale_expiry_releases_only_reservations_before_cutoff(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    stale = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-stale",
        operation_type="ask",
        requested_quantities={"model_responses": 1},
    )
    active = reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-active",
        operation_type="ask",
        requested_quantities={"model_responses": 1},
    )
    now = datetime.now(UTC)
    db.execute(
        update(tables["usage_reservations"])
        .where(tables["usage_reservations"].c.id == stale.id)
        .values(created_at=now - timedelta(hours=2))
    )

    expired_count = expire_stale_reservations(
        db,
        older_than=now - timedelta(minutes=30),
    )

    stale_record = repository.get_usage_reservation_by_id(db, stale.id)
    active_record = repository.get_usage_reservation_by_id(db, active.id)
    assert expired_count == 1
    assert stale_record["state"] == "expired"
    assert stale_record["release_reason"] == "stale_reservation_expired"
    assert active_record["state"] == "reserved"
    assert _counter(db, tables, effective, "model_responses")["reserved_quantity"] == 1
    assert (
        expire_stale_reservations(
            db,
            older_than=now - timedelta(minutes=30),
        )
        == 0
    )


@pytest.mark.unit
def test_metering_changes_follow_the_caller_owned_transaction(metering_db):
    db, tables = metering_db
    effective = _effective(db)
    repository.get_or_create_usage_counter(db, effective.usage_period_id, "model_responses")
    db.commit()

    reserve_usage(
        db,
        effective_subscription=effective,
        request_id="req-rollback",
        operation_type="ask",
        requested_quantities={"model_responses": 1},
    )
    assert _counter(db, tables, effective, "model_responses")["reserved_quantity"] == 1
    db.rollback()

    assert _counter(db, tables, effective, "model_responses")["reserved_quantity"] == 0
    assert (
        repository.get_usage_reservation(
            db,
            effective.billing_account_id,
            "req-rollback",
        )
        is None
    )
