# Database Integration (Historical Snapshot)

This document is retained as a historical milestone record from the initial DB integration phase.

## Current Source of Truth

For current behavior, use:

- `README.md` (runtime + endpoint overview)
- `docs/FASTAPI_README.md` (API contracts and guardrails)
- `docs/runbooks/db-migrations.md` (migration process)

## What Still Applies

- PostgreSQL-backed persistence is the standard runtime mode.
- DB migrations under `db/migrations/` are the canonical schema change path.
- Request/session/message and usage persistence remain core platform capabilities.

## What Is Superseded

- Any CLI-centric setup instructions in older snapshots.
- Any references to legacy flow that conflict with current API-first routing and persistence contracts.

---

Last updated: 2026-03-19
