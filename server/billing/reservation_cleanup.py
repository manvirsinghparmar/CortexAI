"""Automatic lifecycle management for active and stale credit reservations."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, datetime, timedelta
from threading import Lock
from uuid import UUID

from db.session import SessionLocal
from server.billing.metering_service import expire_stale_reservations
from db import billing_repository as repository


@dataclass(frozen=True)
class ReservationCleanupStats:
    inspected: int
    released: int
    credits_released: int
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


_active_lock = Lock()
_active_reservations: set[UUID] = set()


def register_active_reservation(reservation_id: UUID) -> None:
    with _active_lock:
        _active_reservations.add(reservation_id)


def unregister_active_reservation(reservation_id: UUID) -> None:
    with _active_lock:
        _active_reservations.discard(reservation_id)


def active_reservation_ids() -> tuple[UUID, ...]:
    with _active_lock:
        return tuple(_active_reservations)


def heartbeat_active_reservations() -> int:
    """Persist activity for reservations owned by this API process."""

    reservation_ids = active_reservation_ids()
    if not reservation_ids:
        return 0
    db = SessionLocal()
    try:
        touched = repository.touch_usage_reservation_activity(db, reservation_ids)
        db.commit()
        return touched
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_cleanup_cycle(*, stale_after_seconds: int = 1800) -> ReservationCleanupStats:
    if stale_after_seconds <= 0:
        raise ValueError("stale_after_seconds must be positive")
    db = SessionLocal()
    try:
        outcome = expire_stale_reservations(
            db,
            older_than=datetime.now(UTC) - timedelta(seconds=stale_after_seconds),
        )
        db.commit()
        return ReservationCleanupStats(
            inspected=outcome.inspected,
            released=outcome.released,
            credits_released=outcome.credits_released,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
