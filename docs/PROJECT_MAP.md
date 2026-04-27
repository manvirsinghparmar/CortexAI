# CortexAI Project Map

This map is the quick "where do I change X?" reference for the current API-first CortexAI codebase.

## Runtime Entrypoints

- API server: `run_server.py`
- Main FastAPI app wiring: `server/app.py`
- Frontend runtime config renderer: `server/frontend_runtime_config.py` (`GET /runtime-config.js`)
- Browser E2E harness bootstrap: `e2e/server/run_e2e_server.py`

## API Contracts

- Routes: `server/routes/`
- Request/response DTOs: `server/schemas/`
- Error mapping and route guardrails: `server/utils.py`

## Orchestration and Routing

- Core orchestration path: `orchestrator/core.py`
- Smart routing planner: `orchestrator/smart_router.py`
- Tier selection: `orchestrator/tier_decider.py`
- Candidate ranking: `orchestrator/model_selector.py`
- Fallback decisions: `orchestrator/fallback_manager.py`

## Provider Clients

- Client registry: `api/client_registry.py`
- Base contract: `api/base_client.py`
- Providers:
  - `api/openai_client.py`
  - `api/google_gemini_client.py`
  - `api/deepseek_client.py`
  - `api/grok_client.py`
  - `api/claude_client.py`

## Config Sources of Truth

- Provider catalog and defaults: `config/providers.yaml`
- Smart-router model tiers and metadata: `config/model_registry.yaml`
- Cost tables: `config/pricing.py`

## Persistence and Reporting

- SQLAlchemy table reflection and repository access: `db/`
- Persistence service: `server/persistence.py`
- Usage reporting: `server/usage_reporting.py`
- Savings reporting: `server/savings.py`
- DB migrations: `db/migrations/`

## Frontend and Browser Tests

- Static frontend: `frontend/` (`runtime-config.example.js` for static-only hosting)
- Playwright E2E suite: `e2e/specs/`
- Playwright config: `e2e/playwright.config.mjs`

## CI and Workflows

- Main CI: `.github/workflows/ci.yml`
  - Detects frontend/backend/shared path changes.
  - Runs blocking Ruff/MyPy checks against changed Python files with pinned dev tools.
  - Runs Black as an advisory changed-file format check until a repo-wide baseline is applied.
  - Runs Gitleaks as a pinned CLI directory scan of the checked-out tree.
- Targeted backend regression pack: `.github/workflows/incident-regression-38.yml`
- Live browser E2E: `.github/workflows/live-e2e.yml`

## Common Change Paths

- Add/modify an API endpoint:
  1. Update `server/routes/`
  2. Update `server/schemas/`
  3. Add/adjust tests
  4. Update `README.md` and related docs

- Change routing behavior:
  1. Update files in `orchestrator/`
  2. Validate with routing/fallback tests
  3. Update routing docs (`README.md`, `docs/SMART_ROUTING_DIAGRAM.md`)

- Change token/cost behavior:
  1. Update provider clients and/or `server/utils.py`
  2. Keep `config/pricing.py` and `config/model_registry.yaml` aligned
  3. Update contract docs and tests

- Change DB schema:
  1. Add SQL migration under `db/migrations/`
  2. Update repository/table usage under `db/` + `server/`
  3. Follow `docs/runbooks/db-migrations.md`

- Investigate production logging incidents on AWS EC2:
  1. Follow `docs/runbooks/aws-ec2-logging.md`
  2. Correlate CloudFront/WAF logs with `request_id`/`X-Amz-Cf-Id`
  3. Use upload (`upload.*`) and research (`research.*`) event families for root cause

---

Last updated: 2026-04-24
