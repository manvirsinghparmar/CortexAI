# CortexAI Context Pack

## Project Snapshot

- Product: CortexAI B2B LLM gateway (API + optional static frontend + CLI tooling).
- Backend stack: FastAPI + SQLAlchemy/repository pattern + PostgreSQL.
- Orchestration: provider abstraction with smart routing/fallback across OpenAI, Gemini, DeepSeek, Grok, and Claude.
- Frontend stack: legacy static HTML/CSS/JS app in `frontend/` plus React/Vite app in `frontend-react/`.
- E2E stack: Playwright tests in `e2e/`.

## Runtime Commands

```bash
python run_app.py
python run_server.py --reload
python scripts/serve_frontend.py --host 127.0.0.1 --port 8080 --dir frontend
npm ci --prefix frontend-react
npm run --prefix frontend-react build
```

## Core Invariants

- `DATABASE_URL` is required for startup and should point to PostgreSQL.
- Most `/v1/*` endpoints accept API key, Cognito bearer, or session cookie auth.
- Session-scoped routes (`/v1/chat*`, `/v1/compare*`, `/v1/files/*`, `/v1/providers`, `/v1/models`, `/v1/optimize`, `/v1/history*`) reject API-key-only auth.
- Local dev can mint session cookies via `POST /v1/auth/dev-login` only when `ENABLE_DEV_SESSION_LOGIN=true` (blocked in production-like envs).
- Frontend startup waits for Cognito/local dev-session bootstrap before session-scoped startup fetches so Ask/Compare model selectors and the history sidebar can hydrate from `/v1/providers`, `/v1/models`, and `/v1/history`.
- React account actions live in the top-right account icon menu. Keep the persisted light/dark theme switch available there, and keep `Log off` available as a session-clear fallback even when the icon is labelled `Guest account`; it clears the API session cookie, resets active React chat/history state, and redirects to the Cognito Hosted UI logout URL when `/v1/auth/cognito-config` provides one.
- In monolith mode (`SERVE_FRONTEND=true`), `GET /runtime-config.js` is generated at runtime and sent with no-cache headers.
- `run_app.py` is the local full-app runner: it starts FastAPI with `SERVE_FRONTEND=false`, launches the React/Vite dev server, and passes `CORTEX_API_PROXY_TARGET` / `FRONTEND_RUNTIME_API_BASE` so Vite and runtime config point to the selected API host/port.
- The full-app runner preflights both ports before starting children and must terminate full process trees on Windows so failed startup cannot orphan Vite.
- `FRONTEND_DIR` explicitly selects the static frontend directory. Set it to `frontend-react/dist` after building React; `REACT_FRONTEND=true` is a convenience switch when `FRONTEND_DIR` is unset.
- React dependencies belong in `frontend-react/package.json` and `frontend-react/package-lock.json`, never in Python `requirements.txt`.
- Ask and Compare support shared session continuity via `session_id`.
- History persistence remains row-oriented: React groups sidebar threads by `session_id` and reconstructs multi-model Compare turns by `request_group_id` when restoring a session.
- Compare targets are explicit; smart routing flags are ignored in compare mode by design.
- Compare web research is prepared once per compare turn and shared across selected targets.
- Tavily research uses a deterministic local search-options resolver before provider calls.
- Prompt optimization for the UI goes through explicit `POST /v1/optimize`; chat/compare auto-optimization is off by default and requires `ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=true`.
- Frontend follows the Alabaster Minimal shell: a quiet 272px desktop navigation rail that can collapse to a narrow icon rail.
- Frontend-only development falls back to a bundled display model catalog when `/v1/models` is unavailable.

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
- Frontend behavior changes: `frontend/` for legacy UI or `frontend-react/` for React UI, plus contract checks (`frontend/*.test.mjs`, `npm run --prefix frontend-react build`, `e2e/` as needed).

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
  - `npm run --prefix frontend-react build` when React UI is touched
  - `npm run --prefix frontend-react test` when React component logic/tests are touched
- Full browser E2E:
  - `npm run --prefix e2e test`
- Frontend-only responsive browser suites:
  - `npm run --prefix e2e test:mobile`
  - `npm run --prefix e2e test:desktop-ipad`
  - These suites start isolated Vite servers and mock frontend API contracts; they do not require PostgreSQL or live provider credentials.

## Delivery Defaults

- Keep handlers thin and move logic into service modules.
- Preserve backward compatibility for public API contracts unless migration is explicitly requested.
- Update docs for behavior changes:
  - `README.md`
  - `docs/postman/CortexAI_B2B.postman_collection.json`
  - runbooks/ADRs when architecture decisions change.
