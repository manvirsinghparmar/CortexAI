# CortexAI - B2B LLM Gateway (CLI + API + Frontend)

CortexAI is a multi-provider orchestration gateway for OpenAI, Gemini, DeepSeek, and Grok with:
- API-first chat/compare/streaming
- smart routing + fallback
- full DB audit trail in DB mode
- BYOK tenant key support
- usage/cost/savings reporting

## Launch-Ready Capabilities

- API endpoints: `/v1/chat`, `/v1/chat/stream`, `/v1/compare`, `/v1/compare/stream`
- Integration diagnostics endpoint: `/v1/whoami`
- Request attribution: `users`, `api_keys`, `sessions`, `messages`, `llm_requests`, `llm_responses`
- Routing telemetry: `routing_decisions`, `routing_attempts`
- Governance: `usage_daily`, daily caps, per-key rate limit, circuit breaker
- Savings telemetry: per-request baseline vs actual cost (`llm_savings`)
- Reporting/export: `/v1/usage`, `/v1/savings`, CSV export endpoints
- BYOK lifecycle: set/status/delete with encrypted-at-rest secrets
- Privacy controls: metadata-only persistence and optional PII redaction
- Optional prompt optimization endpoint: `/v1/optimize`
- Release gate: compile checks + full tests + DB smoke

## Runtime Modes

- `DATABASE_URL` is required at startup:
  - `DATABASE_URL` must be PostgreSQL (`postgresql://` or `postgresql+psycopg://`).
  - FastAPI persists to repository-backed SQLAlchemy tables (same artifact family as CLI).
  - Chat history endpoints read/write only from PostgreSQL tables.
  - Daily caps, rate limits, BYOK settings, savings, and reporting endpoints are active.
  - API startup fails fast when `DATABASE_URL` is missing.
  - Optional dev override: `ALLOW_NON_POSTGRES_DATABASE_URL=true` (not recommended for production).

## Quick Start

1. Create and activate a virtual environment.
```bash
python -m venv venv
venv\Scripts\activate
```

2. Install dependencies.
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```

3. Configure `.env`.

Minimum API setup:
```ini
API_KEYS=dev-key-1
OPENAI_API_KEY=...
GOOGLE_GEMINI_API_KEY=...
DEEPSEEK_API_KEY=...
GROK_API_KEY=...
```

Enable DB mode:
```ini
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
DB_SCHEMA=public
AUTO_REGISTER_UNMAPPED_API_KEYS=true
```

## Key Environment Variables

```ini
# Governance
DAILY_TOKEN_CAP=
DAILY_COST_CAP=
DAILY_CAP_SCOPE=api_key   # api_key|user
REQUESTS_PER_MINUTE=60
REPORT_MAX_RANGE_DAYS=366 # reporting/export date-range guard (<=0 disables)

# Circuit breaker
CIRCUIT_FAILURE_THRESHOLD=5
CIRCUIT_WINDOW_SECONDS=60
CIRCUIT_COOLDOWN_SECONDS=120

# Ask smart routing controls (optional)
ENABLE_TRUE_SMART_CHAT_ROUTING=true
SMART_CHAT_MAX_COST_USD=
SMART_CHAT_MAX_TOTAL_LATENCY_MS=
SMART_CHAT_MIN_CONTEXT_LIMIT=
SMART_CHAT_PREFERRED_PROVIDER=      # openai|gemini|deepseek|grok
SMART_CHAT_ALLOWED_PROVIDERS=       # comma-separated, e.g. openai,gemini

# Storage/privacy
STORAGE_POLICY=full       # full|metadata (default: full when unset)
REDACT_PII=false          # true|false

# BYOK encryption
MASTER_KEY=replace-with-strong-random-secret

# Savings baseline
BASELINE_MODEL_ID=openai:gpt-4o-mini
# or BASELINE_PROVIDER=openai + BASELINE_MODEL=gpt-4o-mini
```

## Pricing Configuration

- Runtime token-cost estimation uses `config/pricing.py`.
- Smart-router model economics use `config/model_registry.yaml`.
- Provider metadata/defaults/allowlists use `config/providers.yaml` via `config/provider_catalog.py`.
- Keep both files in sync when provider pricing changes.
- Current pricing tables were refreshed on `2026-02-22`.
- Validation command:
```bash
python -m pytest tests/test_registry_pricing_alignment.py -q
```

## Run

```bash
python run_server.py --reload
```

Useful URLs:
- Health: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`
- Frontend: `http://127.0.0.1:8000/`

## Authentication

All `/v1/*` routes require:
```http
X-API-Key: <tenant-api-key>
```

Optional request correlation:
```http
X-Request-ID: <custom-id>
```

Integration debug snapshot:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/v1/whoami
```
Returns owner IDs (in DB mode), active storage policy, baseline model, and guardrail config snapshot.
Response includes:
- `api_key_id`, `user_id`, `plan_tier`
- `storage_policy`, `redact_pii`
- `baseline.provider`, `baseline.model`, `baseline.source`
- `rate_limits.requests_per_minute`, `rate_limits.daily_cap_scope`
- `breakers.failure_threshold`, `breakers.window_seconds`, `breakers.cooldown_seconds`

## API Endpoints

- `GET /health`
- `POST /v1/chat`
- `POST /v1/chat/stream`
- `POST /v1/compare`
- `POST /v1/compare/stream`
- `POST /v1/optimize`
- `GET /v1/history`
- `DELETE /v1/history/{entry_id}`
- `DELETE /v1/history`
- `GET /v1/whoami`
- `GET /v1/usage?from=YYYY-MM-DD&to=YYYY-MM-DD&group_by=day|provider|model`
- `GET /v1/savings?from=YYYY-MM-DD&to=YYYY-MM-DD&group_by=day|provider|model`
- `GET /v1/usage/export?format=csv&from=...&to=...&group_by=...`
- `GET /v1/savings/export?format=csv&from=...&to=...&group_by=...`
- `POST /v1/byok`
- `GET /v1/byok/status`
- `DELETE /v1/byok?provider=openai` (or omit provider to delete all)
- `GET /v1/admin/request-groups/{request_group_id}/failed-attempts`

## Routing Modes

For Ask (`/v1/chat`, `/v1/chat/stream`) requests:
- Explicit `provider` + `model`: deterministic target.
- `routing.smart_mode=true` (or omitted): true smart orchestration path (`routing_mode="smart"` with optional constraints from `SMART_CHAT_*` env vars).
- `routing.smart_mode=false`: legacy deterministic auto-pick path.
- `routing.research_mode=true`: optional web-enriched prompt flow.

For Compare (`/v1/compare`, `/v1/compare/stream`) requests:
- Targets are always explicit (`targets[]`).
- `routing.smart_mode` is ignored by design in compare mode.
- `routing.research_mode=true` is still honored.

## Compare and `request_group_id`

`/v1/compare` and `/v1/compare/stream` return a `request_group_id` that groups all per-target persisted rows.
- Each target persists its own request/response pair.
- All target rows share the same `request_group_id`.
- Use this ID to debug failed attempts via admin route.

## Streaming NDJSON Contract

`/v1/chat/stream` events:
- `start`
- `line`
- `response_done`
- `done`
- `error`

`/v1/compare/stream` events:
- `start`
- `response_start`
- `line`
- `response_done`
- `done` (contains aggregate compare payload with `request_group_id`)
- `error`

## BYOK (Bring Your Own Keys)

Security model:
- Provider secrets are encrypted at rest using `MASTER_KEY`.
- Raw provider secrets are never returned from status APIs.
- Runtime requests resolve tenant BYOK keys per provider when available.

At-rest verification (DB spot check):
```sql
SELECT provider, encrypted_key, key_last4
FROM byok_provider_keys
ORDER BY updated_at DESC
LIMIT 20;
```
Expected: `encrypted_key` should never match original plaintext keys.

`MASTER_KEY` rotation (current model):
1. Set `OLD_MASTER_KEY` outside app runtime and decrypt existing rows in a one-time admin script.
2. Re-encrypt with new `MASTER_KEY`.
3. Restart API with only the new `MASTER_KEY`.
4. Spot-check `byok_provider_keys` and run `/v1/byok/status`.

Set/update:
```bash
curl -X POST http://127.0.0.1:8000/v1/byok \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "provider_keys": {"openai": "sk-tenant-openai-key"},
    "baseline_provider": "openai",
    "baseline_model": "gpt-4o-mini",
    "requests_per_minute": 120
  }'
```

Status:
```bash
curl -H "X-API-Key: dev-key-1" http://127.0.0.1:8000/v1/byok/status
```

Delete:
```bash
curl -X DELETE -H "X-API-Key: dev-key-1" "http://127.0.0.1:8000/v1/byok?provider=openai"
```

## Usage and Savings Reporting

Usage:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/v1/usage?from=2026-02-01&to=2026-02-22&group_by=day"
```

Savings:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/v1/savings?from=2026-02-01&to=2026-02-22&group_by=model"
```

CSV export (invoicing hook):
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/v1/usage/export?format=csv&from=2026-02-01&to=2026-02-22&group_by=provider"
```

Export determinism:
- CSV column order is fixed.
- Response includes `X-Export-Columns` for schema verification in ingestion jobs.
- Large date ranges are bounded by `REPORT_MAX_RANGE_DAYS` to keep exports responsive.

## Error Codes

Common `detail.code` values:
- `usage_limit_exceeded`
- `rate_limited`
- `provider_error`
- `timeout`
- `bad_request`
- `invalid_model`
- `unauthorized`

## Minimal Python SDK Snippet

```python
import requests

class CortexClient:
    def __init__(self, base_url: str, api_key: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"X-API-Key": api_key}

    def chat(self, prompt: str, provider: str | None = None, model: str | None = None):
        payload = {"prompt": prompt}
        if provider:
            payload["provider"] = provider
        if model:
            payload["model"] = model
        r = requests.post(f"{self.base_url}/v1/chat", json=payload, headers=self.headers, timeout=60)
        r.raise_for_status()
        return r.json()

    def compare(self, prompt: str, targets: list[dict]):
        payload = {"prompt": prompt, "targets": targets}
        r = requests.post(f"{self.base_url}/v1/compare", json=payload, headers=self.headers, timeout=120)
        r.raise_for_status()
        return r.json()

    def usage(self, from_date: str, to_date: str, group_by: str = "day"):
        r = requests.get(
            f"{self.base_url}/v1/usage",
            params={"from": from_date, "to": to_date, "group_by": group_by},
            headers=self.headers,
            timeout=30,
        )
        r.raise_for_status()
        return r.json()
```

## Reliability and Guardrails

- Daily cost/token caps are enforced only in DB mode.
- Rate limiting is per API key (or key owner fallback when unmapped).
- Circuit breaker opens per `provider:model` and allows automatic fallback.
- Circuit breaker scope is currently global per `provider:model` (not tenant-scoped).
- Retry/fallback paths are bounded; no unbounded loops.

## Privacy and Retention

- default (unset): `STORAGE_POLICY=full` behavior.
- `STORAGE_POLICY=metadata`: no raw prompt/response text persistence.
- `STORAGE_POLICY=full`: content persistence enabled.
- `REDACT_PII=true`: regex redaction for emails, phones, and card-like numbers before DB storage.

## Release Gate

Use this before launch/deploy:
```bash
python scripts/release_gate.py
```

It runs:
- `python -m py_compile ...`
- `pytest -q`
- DB mode smoke test (`/v1/chat` + DB row assertions for `llm_requests` and `usage_daily`)

## Tenant Onboarding Script

One-command onboarding (create tenant user + api key + baseline + optional BYOK):
```bash
python scripts/onboard_tenant.py \
  --email founder@startup.com \
  --name "Startup Tenant" \
  --baseline-model-id openai:gpt-4o-mini \
  --requests-per-minute 60 \
  --byok-openai sk-tenant-openai-key \
  --base-url http://127.0.0.1:8000
```

The script prints:
- `user_id`, `api_key_id`
- generated or assigned API key
- ready-to-run `curl` examples including `/v1/whoami`

## Monthly Proof Pack Script

Generate customer proof pack (CSV + Markdown + HTML):
```bash
python scripts/generate_proof_pack.py --api-key dev-key-1 --month 2026-02
```

Outputs:
- `summary.csv` (spend, baseline, savings, error rate, config snapshot)
- `top_models.csv`
- `proof_pack.md`
- `proof_pack.html` (print to PDF if needed)

## Tests

Run full suite:
```bash
python -m pytest -q
```

Run B2B launch tests only:
```bash
python -m pytest tests/test_b2b_launch_features.py -q
```

Run full B2B API checklist against a live server:
```bash
python scripts/e2e_b2b_checklist.py --base-url http://127.0.0.1:8000 --api-key dev-key-1
```

Postman collection:
- `docs/postman/CortexAI_B2B.postman_collection.json`

## Project Structure

```text
OpenAIProject/
  main.py
  run_server.py
  list-models.cmd
  quick_test_optimizer.py
  README.md
  requirements.txt
  requirements-dev.txt
  pyproject.toml
  pytest.ini

  api/
    base_client.py
    deepseek_client.py
    google_gemini_client.py
    grok_client.py
    openai_client.py

  config/
    __init__.py
    config.py
    model_registry.yaml
    provider_catalog.py
    providers.yaml
    pricing.py

  context/
    __init__.py
    conversation_manager.py

  db/
    __init__.py
    engine.py
    migrations/
      20260218_add_request_group_id_to_llm_requests.sql
      20260218_llm_requests_api_key_owner_guard.sql
      20260222_b2b_launch_tables.sql
      20260222_go_live_hardening.sql
    repository.py
    session.py
    tables.py

  docs/
    CHANGELOG.md
    COMPARE_MODE_GUIDE.md
    DATABASE_INTEGRATION_COMPLETE.md
    FASTAPI_README.md
    LOGGING.md
    PROJECT_MAP.md
    REFACTORING_SUMMARY.md
    TAVILY_INTEGRATION.md
    UNIFIED_RESPONSE_CONTRACT.md
    postman/
      CortexAI_B2B.postman_collection.json

  frontend/
    index.html
    app.js
    style.css
    smart-routing-state.js
    layout-smoke.test.mjs
    smart-routing-state.test.mjs

  models/
    __init__.py
    multi_unified_response.py
    unified_response.py
    user_context.py

  orchestrator/
    __init__.py
    core.py
    fallback_manager.py
    model_registry.py
    model_selector.py
    multi_orchestrator.py
    prompt_analyzer.py
    response_validator.py
    routing_types.py
    smart_router.py
    tier_decider.py

  scripts/
    db_mode_smoke.py
    e2e_b2b_checklist.py
    generate_proof_pack.py
    onboard_tenant.py
    release_gate.py

  server/
    __init__.py
    app.py
    byok_service.py
    circuit_breaker.py
    dependencies.py
    middleware.py
    persistence.py
    privacy.py
    rate_limit.py
    savings.py
    usage_reporting.py
    utils.py
    routes/
      __init__.py
      admin.py
      byok.py
      chat.py
      compare.py
      health.py
      history.py
      optimize.py
      reporting.py
      whoami.py
    schemas/
      __init__.py
      requests.py
      responses.py

  tools/
    create_api_key.py
    register_dev_key.py
    web/
      __init__.py
      cache.py
      contracts.py
      factory.py
      intent.py
      research_decider.py
      research_pack.py
      research_state.py
      research_state_store.py
      session_state.py
      tavily_client.py
      tavily_service.py

  utils/
    __init__.py
    GeminiAvailableModels.py
    api_key_utils.py
    cost_calculator.py
    logger.py
    model_utils.py
    prompt_optimizer.py
    token_tracker.py
    web_research.py

  tests/
    __init__.py
    conftest.py
    README.md
    test_api.py
    test_api_key_hashing.py
    test_api_persistence_guardrails.py
    test_b2b_launch_features.py
    test_compare_session_totals.py
    test_conversation.py
    test_fallback_manager.py
    test_fastapi_contract_and_guardrails.py
    test_model_selector.py
    test_model_utils.py
    test_multi_compare_mode.py
    test_pricing.py
    test_prompt_analyzer.py
    test_prompt_optimizer.py
    test_registry_pricing_alignment.py
    test_response_validator.py
    test_routing_regression.py
    test_smart_router_metadata.py
    test_tier_decider.py
    test_unified_response_contract.py
    ... (additional unit/integration suites)
```

## What to Edit for Common Changes

- Add a new API endpoint: `server/routes/*.py` + wire router in `server/app.py` + request/response models in `server/schemas/`.
- Add business logic/service code: `server/*.py` (keep route handlers thin; move logic into services).
- Add or change provider behavior: `api/*.py`, orchestration flow in `orchestrator/core.py`, and provider metadata in `config/providers.yaml`.
- Change smart routing rules: `orchestrator/prompt_analyzer.py`, `orchestrator/tier_decider.py`, `orchestrator/model_selector.py`, `orchestrator/smart_router.py`.
- Add DB tables/columns/indexes: create SQL migration in `db/migrations/`, then update reflected usage in `db/tables.py` and queries in `db/repository.py`.
- Change persistence/audit behavior for FastAPI: `server/persistence.py` (shared write path for chat/compare/stream).
- Change usage/savings/BYOK behavior: `server/usage_reporting.py`, `server/savings.py`, `server/byok_service.py`, and related routes under `server/routes/`.
- Add/adjust guardrails: `server/rate_limit.py`, `server/circuit_breaker.py`, privacy policy in `server/privacy.py`.
- Add tenant/dev tooling scripts: `scripts/` (runtime checks/reporting) and `tools/` (operator/dev helpers).
- Add tests: put new tests in `tests/` (mirror by feature area) and run `python -m pytest -q` + `python scripts/release_gate.py`.
- Update API docs and examples after behavior changes: `README.md` and `docs/postman/CortexAI_B2B.postman_collection.json`.

Last updated: 2026-02-25
