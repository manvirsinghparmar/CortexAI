from __future__ import annotations

import os
import threading
import time
from datetime import UTC, datetime, timedelta
from queue import Queue
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from db import billing_repository as repository

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
