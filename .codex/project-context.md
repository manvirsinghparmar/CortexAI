# OpenAIProject Context Pack

## Project Snapshot

- Product: CortexAI B2B LLM gateway (API + optional static frontend + CLI tooling).
- Backend stack: FastAPI + SQLAlchemy/repository pattern + PostgreSQL.
- Orchestration: provider abstraction with smart routing/fallback across OpenAI, Gemini, DeepSeek, Grok, and Claude.
- Frontend stack: static HTML/CSS/JS app in `frontend/`.
- E2E stack: Playwright tests in `e2e/`.

## Runtime Commands

```bash
python run_server.py --reload
python scripts/serve_frontend.py --host 127.0.0.1 --port 8080 --dir frontend
```

## Core Invariants

- `DATABASE_URL` is required for startup and should point to PostgreSQL.
- Most `/v1/*` endpoints accept API key, Cognito bearer, or session cookie auth.
- Session-scoped routes (`/v1/chat*`, `/v1/compare*`, `/v1/files/*`, `/v1/providers`, `/v1/models`, `/v1/optimize`, `/v1/history*`) reject API-key-only auth.
- Local dev can mint session cookies via `POST /v1/auth/dev-login` only when `ENABLE_DEV_SESSION_LOGIN=true` (blocked in production-like envs).
- Frontend startup waits for Cognito/local dev-session bootstrap before catalog discovery so Ask/Compare model selectors can hydrate from session-scoped `/v1/providers` and `/v1/models`.
- In monolith mode (`SERVE_FRONTEND=true`), `GET /runtime-config.js` is generated at runtime and sent with no-cache headers.
- Ask and Compare support shared session continuity via `session_id`.
- Conversation-history guardrails are active, but oversized history is soft-trimmed instead of rejected.
- Compare targets are explicit; smart routing flags are ignored in compare mode by design.
- Frontend Compare selectors show attached per-model remove controls only for three active models, fade the controls in on selector hover/focus, keep at least two active models, and send only active selected slots after removal.
- Prompt optimization for the UI goes through explicit `POST /v1/optimize`; chat/compare auto-optimization is off by default and requires `ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=true`.
- Explicit UI prompt optimization is latency-bounded (`PROMPT_OPTIMIZER_TIMEOUT_MS`, default 5000 ms), defaults to two route-level attempts, retries unchanged output once for locally classified weak prompts, rejects answer-like or unresolved-placeholder optimizer output, and may send compact mixed user/assistant follow-up context only when the frontend detects a reference-dependent prompt without attachments. Reference-dependent optimize context is capped to the last ten mixed messages / 4,000 characters.

## High-Value Paths

- API routes: `server/routes/`
- API schemas: `server/schemas/`
- Orchestration: `orchestrator/`
- Provider clients: `api/`
- Persistence and reporting: `server/persistence.py`, `server/usage_reporting.py`, `server/savings.py`, `db/`
- Config single sources:
  - `config/providers.yaml`
  - `config/model_registry.yaml`
  - `config/pricing.py`

## Change-Impact Map

- New endpoint: route + schema + router wiring + tests + README API section.
- Provider/catalog changes: `api/`, `api/client_registry.py`, `config/providers.yaml`, provider discovery tests.
- Routing behavior changes: `orchestrator/prompt_analyzer.py`, `tier_decider.py`, `model_selector.py`, `smart_router.py`.
- DB changes: add SQL migration under `db/migrations/`, then reflect in tables/repository usage.
- Frontend behavior changes: `frontend/` plus contract checks (`frontend/*.test.mjs`, `e2e/` as needed).

## Validation Matrix

- Unit/regression baseline:
  - `python -m pytest -q`
- Release gate:
  - `python scripts/release_gate.py`
- Pricing/registry consistency:
  - `python -m pytest tests/test_registry_pricing_alignment.py -q`
- CI changed-file quality gates:
  - Ruff/MyPy run on changed Python files; Black is advisory until a formatting baseline lands.
  - Gitleaks scans the checked-out tree with the pinned CLI rather than repository history.
- Frontend local checks (when UI touched):
  - `node --test frontend/layout-smoke.test.mjs`
  - `node --test frontend/provider-discovery.e2e.test.mjs`
- Full browser E2E:
  - `npm run --prefix e2e test`

## Delivery Defaults

- Keep handlers thin and move logic into service modules.
- Preserve backward compatibility for public API contracts unless migration is explicitly requested.
- Update docs for behavior changes:
  - `README.md`
  - `docs/postman/CortexAI_B2B.postman_collection.json`
  - runbooks/ADRs when architecture decisions change.
