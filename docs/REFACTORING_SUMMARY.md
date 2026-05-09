# Refactoring Summary (Historical Snapshot)

This file is kept as a historical record of earlier restructuring work.

## Current Source of Truth

Use the following for current architecture and implementation boundaries:

- `README.md`
- `.codex/project-context.md`
- `docs/PROJECT_MAP.md`
- `docs/FASTAPI_README.md`

## Current Architecture (High Level)

- API-first FastAPI runtime (`run_server.py`, `server/`)
- Orchestration/routing in `orchestrator/`
- Provider adapters in `api/`
- PostgreSQL persistence/reporting via `db/` and `server/*`
- Legacy static frontend in `frontend/`, React/Vite frontend in `frontend-react/`, and browser E2E in `e2e/`

## Why This Doc Is Historical

Some details in earlier refactor writeups were scoped to transitional phases and may not reflect:

- latest smart-routing and fallback behavior,
- current guardrail defaults (for example output token caps),
- current CI/workflow execution paths.

---

Last updated: 2026-05-09
