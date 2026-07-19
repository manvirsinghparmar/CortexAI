from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime, timedelta
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text, update
from sqlalchemy.orm import sessionmaker

from db import billing_repository as repository
from server.billing.errors import UsageAllowanceExceededError
from server.billing.metering_service import reserve_usage, settle_usage
from server.billing.plan_catalog import get_plan_catalog
from server.billing.subscription_service import EffectiveSubscription

POSTGRES_URL = os.getenv("BILLING_TEST_DATABASE_URL")

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not POSTGRES_URL,
        reason="BILLING_TEST_DATABASE_URL is required for PostgreSQL billing integration tests",
    ),
]


@pytest.fixture()
def postgres_runtime(monkeypatch):
    assert POSTGRES_URL is not None
    monkeypatch.setenv("DATABASE_URL", POSTGRES_URL)
    monkeypatch.setenv("DB_SCHEMA", "public")

    import db.engine as db_engine
    import db.tables as db_tables

    if db_engine._ENGINE is not None:
        db_engine._ENGINE.dispose()
    db_engine._ENGINE = None
    db_tables.DB_SCHEMA = "public"
    db_tables._tables_cache.clear()
    db_tables.metadata.clear()

    engine = create_engine(POSTGRES_URL)
    try:
        yield engine
    finally:
        engine.dispose()
        if db_engine._ENGINE is not None:
            db_engine._ENGINE.dispose()
        db_engine._ENGINE = None
        db_tables._tables_cache.clear()
        db_tables.metadata.clear()


def _delete_test_account(engine, account_id) -> None:
    with engine.begin() as connection:
        connection.execute(
            text("DELETE FROM usage_reservations WHERE billing_account_id = :account_id"),
            {"account_id": account_id},
        )
        connection.execute(
            text(
                "DELETE FROM usage_counters WHERE usage_period_id IN "
                "(SELECT id FROM usage_periods WHERE billing_account_id = :account_id)"
            ),
            {"account_id": account_id},
        )
        connection.execute(
            text("DELETE FROM usage_periods WHERE billing_account_id = :account_id"),
            {"account_id": account_id},
        )
        connection.execute(
            text("DELETE FROM subscriptions WHERE billing_account_id = :account_id"),
            {"account_id": account_id},
        )
        connection.execute(
            text("DELETE FROM billing_accounts WHERE id = :account_id"),
            {"account_id": account_id},
        )


def test_billing_schema_is_queryable_through_reflection(postgres_runtime):
    from db.tables import get_table

    for table_name in (
        "billing_accounts",
        "subscriptions",
        "usage_periods",
        "usage_counters",
        "usage_reservations",
        "billing_webhook_events",
    ):
        table = get_table(table_name)
        assert table.name == table_name
        assert table.schema == "public"


def test_lock_usage_counters_serializes_concurrent_reservation_paths(postgres_runtime):
    session_factory = sessionmaker(bind=postgres_runtime)
    setup_session = session_factory()
    account = repository.get_or_create_billing_account_for_user(setup_session, uuid4())
    starts_at = datetime(2026, 7, 1, tzinfo=UTC)
    period = repository.create_usage_period(
        setup_session,
        billing_account_id=account["id"],
        plan_code="free",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(days=31),
    )
    repository.get_or_create_usage_counter(
        setup_session,
        period["id"],
        "model_responses",
    )
    setup_session.commit()
    setup_session.close()

    first_has_lock = threading.Event()
    release_first = threading.Event()
    second_has_lock = threading.Event()
    failures: Queue[BaseException] = Queue()

    def first_transaction() -> None:
        session = session_factory()
        try:
            repository.lock_usage_counters(
                session,
                period["id"],
                ["model_responses"],
            )
            first_has_lock.set()
            if not release_first.wait(timeout=5):
                raise TimeoutError("Timed out waiting to release the first counter lock")
            session.commit()
        except BaseException as exc:
            session.rollback()
            failures.put(exc)
        finally:
            session.close()

    def second_transaction() -> None:
        session = session_factory()
        try:
            if not first_has_lock.wait(timeout=5):
                raise TimeoutError("First transaction never acquired the counter lock")
            repository.lock_usage_counters(
                session,
                period["id"],
                ["model_responses"],
            )
            second_has_lock.set()
            session.commit()
        except BaseException as exc:
            session.rollback()
            failures.put(exc)
        finally:
            session.close()

    first_thread = threading.Thread(target=first_transaction)
    second_thread = threading.Thread(target=second_transaction)
    try:
        first_thread.start()
        assert first_has_lock.wait(timeout=5)
        second_thread.start()
        time.sleep(0.25)
        assert not second_has_lock.is_set()
        release_first.set()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)
        assert second_has_lock.is_set()
        assert failures.empty(), list(failures.queue)
    finally:
        release_first.set()
        first_thread.join(timeout=5)
        second_thread.join(timeout=5)
        _delete_test_account(postgres_runtime, account["id"])


def test_concurrent_metering_prevents_overuse_and_settles_the_winner(postgres_runtime):
    from db.tables import get_table

    session_factory = sessionmaker(bind=postgres_runtime)
    setup_session = session_factory()
    account = repository.get_or_create_billing_account_for_user(setup_session, uuid4())
    starts_at = datetime(2026, 7, 1, tzinfo=UTC)
    period = repository.create_usage_period(
        setup_session,
        billing_account_id=account["id"],
        plan_code="free",
        starts_at=starts_at,
        ends_at=starts_at + timedelta(days=31),
    )
    counter = repository.get_or_create_usage_counter(
        setup_session,
        period["id"],
        "model_responses",
    )
    usage_counters = get_table("usage_counters")
    setup_session.execute(
        update(usage_counters).where(usage_counters.c.id == counter["id"]).values(used_quantity=29)
    )
    setup_session.commit()
    setup_session.close()

    effective = EffectiveSubscription(
        billing_account_id=account["id"],
        usage_period_id=period["id"],
        plan=get_plan_catalog().require("free"),
        source="test",
        provider=None,
        provider_subscription_id=None,
        status="free",
        current_period_start=starts_at,
        current_period_end=starts_at + timedelta(days=31),
        cancel_at_period_end=False,
        grace_until=None,
    )
    start = threading.Barrier(2)
    outcomes: Queue[tuple[str, object]] = Queue()

    def reserve(request_id: str) -> None:
        session = session_factory()
        try:
            start.wait(timeout=5)
            reservation = reserve_usage(
                session,
                effective_subscription=effective,
                request_id=request_id,
                operation_type="ask",
                requested_quantities={"model_responses": 1},
            )
            session.commit()
            outcomes.put(("reserved", reservation.id))
        except UsageAllowanceExceededError as exc:
            session.rollback()
            outcomes.put(("denied", exc))
        except BaseException as exc:
            session.rollback()
            outcomes.put(("failed", exc))
        finally:
            session.close()

    threads = [
        threading.Thread(target=reserve, args=("req-concurrent-1",)),
        threading.Thread(target=reserve, args=("req-concurrent-2",)),
    ]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=10)
        assert all(not thread.is_alive() for thread in threads)

        results = [outcomes.get_nowait(), outcomes.get_nowait()]
        assert sorted(result[0] for result in results) == ["denied", "reserved"]
        reservation_id = next(value for state, value in results if state == "reserved")

        verification = session_factory()
        try:
            before_settlement = repository.get_or_create_usage_counter(
                verification,
                period["id"],
                "model_responses",
            )
            assert before_settlement["used_quantity"] == 29
            assert before_settlement["reserved_quantity"] == 1

            settle_usage(
                verification,
                reservation_id=reservation_id,
                successful_quantities={"model_responses": 1},
            )
            verification.commit()
            after_settlement = repository.get_or_create_usage_counter(
                verification,
                period["id"],
                "model_responses",
            )
            assert after_settlement["used_quantity"] == 30
            assert after_settlement["reserved_quantity"] == 0
        finally:
            verification.close()
    finally:
        for thread in threads:
            thread.join(timeout=5)
        _delete_test_account(postgres_runtime, account["id"])
