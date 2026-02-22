# CortexAI - Multi-Provider LLM CLI + API

Python project for running chat/comparison workflows across OpenAI, Gemini, DeepSeek, and Grok with:
- Smart tier-based routing (`T0` to `T3`)
- Unified response contract across providers
- FastAPI endpoints for app integration
- Optional DB persistence and CLI usage caps
- Optional web research (Tavily)

## What Is In This Repo

- CLI app: `main.py`
- API server: `run_server.py` and `server/`
- Orchestration/routing: `orchestrator/`
- Provider clients: `api/`
- Shared response models: `models/`
- Config and model registry: `config/`
- Optional DB persistence: `db/`
- Tests: `tests/`

## Key Features

- Multi-provider clients with one response shape (`UnifiedResponse`)
- Smart routing modes:
  - `smart`: automatic tier/model selection
  - `cheap`: force start from cheap tier (`T0`)
  - `strong`: force start from strong tier (`T2`)
- Tier escalation/fallback on low-quality responses, timeouts, provider errors, and refusals
- Explicit model override (`provider + model`) with registry validation
- CLI multiline paste mode for code (`/paste`, finish with `/end`)
- API auth via `X-API-Key`
- Compare endpoint for side-by-side model results
- DB-backed API persistence for `/v1/chat` and `/v1/compare`
- Canonical compare `request_group_id` across API response, orchestrator logs, and DB rows
- Token/cost tracking and structured JSON logs

## Setup

1. Create and activate a virtual environment:

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create `.env` from `.env.example` and set keys:

```ini
MODEL_TYPE=openai
OPENAI_API_KEY=...
GOOGLE_GEMINI_API_KEY=...
DEEPSEEK_API_KEY=...
GROK_API_KEY=...
API_KEYS=dev-key-1,dev-key-2
```

Optional:
- `DATABASE_URL` to enable DB persistence
- `TAVILY_API_KEY` to enable web research
- `ENABLE_PROMPT_OPTIMIZATION=true` for prompt optimization
- `AUTO_REGISTER_UNMAPPED_API_KEYS` / `ALLOW_UNMAPPED_API_KEY_PERSIST` for unmapped-key persistence behavior

## Run

CLI:

```bash
python main.py
```

API:

```bash
python run_server.py --reload
```

Health check:

```bash
curl http://127.0.0.1:8000/health
```

## CLI Commands

- `help` - show commands
- `stats` - session token/cost stats
- `/paste` - enter multiline mode
- `/end` - submit multiline text
- `/cancel` - cancel multiline input
- `/reset` - clear conversation history
- `/history` - show recent conversation
- `/new` - create a new session
- `/dbstats` - show DB usage (when DB enabled)
- `exit` / `quit`

Notes:
- If pasted text looks like code and has no explicit task, CLI auto-prefixes: "Please review and refactor this code..."
- Daily token/cost caps (`DAILY_TOKEN_CAP`, `DAILY_COST_CAP`) are enforced in CLI when DB is enabled.

## API Endpoints

- `GET /health`
- `POST /v1/chat`
- `POST /v1/compare`

### `POST /v1/chat`

`provider` is optional when using smart routing.

Example (auto-routing):

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Fix this Python traceback",
    "routing_mode": "smart"
  }'
```

Example (explicit model):

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain decorators",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }'
```

### `POST /v1/compare`

- 2 to 4 targets required
- Context is rejected when more than 2 targets are sent

```bash
curl -X POST http://127.0.0.1:8000/v1/compare \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Summarize this API design",
    "targets": [
      {"provider": "openai", "model": "gpt-4.1-mini"},
      {"provider": "gemini", "model": "gemini-2.5-flash-lite"}
    ]
  }'
```

API guardrails:
- Context trimmed to last 10 messages
- Context hard limit: 8000 chars
- `max_tokens` clamped to 1024

Important:
- API currently does not enforce CLI daily usage caps.

API key DB registration (for persistence attribution):
- `python tools/create_api_key.py --email api@cortexai.local --name "API Service User" --label "postman"`
- For existing key: `python tools/create_api_key.py --email api@cortexai.local --key "dev-key-1" --label "env-dev-key"`
- Zero-arg dev helper: `python tools/register_dev_key.py`

API key persistence defaults:
- `AUTO_REGISTER_UNMAPPED_API_KEYS=false`
- `ALLOW_UNMAPPED_API_KEY_PERSIST=false`

With both defaults, unmapped keys are rejected with `403` (safer testing default).

## DB Migrations for API Persistence

```bash
psql "$DATABASE_URL" -f db/migrations/20260218_llm_requests_api_key_owner_guard.sql
psql "$DATABASE_URL" -f db/migrations/20260218_add_request_group_id_to_llm_requests.sql
```

What these add:
- Owner invariant trigger for `llm_requests.user_id` vs `api_keys.user_id` when `api_key_id` is set
- `llm_requests.request_group_id` + indexes for compare run grouping

## Smart Routing

Routing is driven by:
- `orchestrator/prompt_analyzer.py` (detects code/math/analysis/factual/strict patterns)
- `orchestrator/tier_decider.py` (maps prompt features to `T0`/`T1`/`T2`/`T3`)
- `orchestrator/model_selector.py` (tag-aware ranking + cost/context constraints)
- `orchestrator/response_validator.py` (validates quality; detects refusal patterns)
- `orchestrator/fallback_manager.py` (retry same tier vs escalate)
- `orchestrator/smart_router.py` (planning and attempt metadata)

Model inventory is in `config/model_registry.yaml`.

If `provider + model` are explicitly given:
- Routing is bypassed
- Selection is validated against registry
- Unknown/disabled model returns `bad_request`

## Discover Supported Models

List models exposed by each provider account:

```bash
list-models.cmd
```

PowerShell:

```powershell
.\list-models.ps1
```

Direct Python:

```bash
python -c "from dotenv import load_dotenv; load_dotenv(); from utils.model_utils import ModelUtils; ModelUtils.list_all_available_models()"
```

Gemini note:
- If capability metadata is missing, script prints raw models returned by API.

## Testing

Run all tests:

```bash
pytest
```

Run only non-integration tests:

```bash
pytest -m "not integration"
```

Run API integration test file (server must be running):

```bash
pytest tests/test_api.py -v
```

## Current Project Structure

```text
OpenAIProject/
  api/
    base_client.py
    openai_client.py
    google_gemini_client.py
    deepseek_client.py
    grok_client.py
  config/
    config.py
    pricing.py
    model_registry.yaml
  context/
    conversation_manager.py
  db/
    engine.py
    session.py
    tables.py
    repository.py
  models/
    unified_response.py
    multi_unified_response.py
    user_context.py
  orchestrator/
    core.py
    multi_orchestrator.py
    prompt_analyzer.py
    tier_decider.py
    model_selector.py
    response_validator.py
    fallback_manager.py
    smart_router.py
    model_registry.py
    routing_types.py
  server/
    app.py
    dependencies.py
    middleware.py
    utils.py
    routes/
      health.py
      chat.py
      compare.py
    schemas/
      requests.py
      responses.py
  tools/web/
    tavily_client.py
    tavily_service.py
    research_decider.py
    research_pack.py
    research_state.py
    research_state_store.py
    session_state.py
    intent.py
    cache.py
    contracts.py
    factory.py
  utils/
    logger.py
    token_tracker.py
    cost_calculator.py
    model_utils.py
    prompt_optimizer.py
    GeminiAvailableModels.py
  tests/
    test_fastapi_contract_and_guardrails.py
    test_routing_regression.py
    test_model_selector.py
    test_tier_decider.py
    test_prompt_analyzer.py
    test_response_validator.py
    test_fallback_manager.py
    test_registry_pricing_alignment.py
    test_model_utils.py
    test_api.py
    ...
  main.py
  run_server.py
  list-models.cmd
  list-models.ps1
  README.md
  .agent-context.md
```

## Docs

- `docs/FASTAPI_README.md`
- `docs/UNIFIED_RESPONSE_CONTRACT.md`
- `docs/LOGGING.md`
- `docs/COMPARE_MODE_GUIDE.md`
- `docs/PROJECT_MAP.md`
- `docs/CHANGELOG.md`

## Troubleshooting

`.\.venv\Scripts\python.exe` not found:
- Use your actual environment path (`venv\Scripts\python.exe`) or just `python`
- `list-models.cmd` / `list-models.ps1` already fall back to `python`

`tests/test_api.py` failing with connection error:
- Start API first: `python run_server.py`

`/v1/chat` returns auth error:
- Set `API_KEYS` in `.env`
- Send `X-API-Key` header

OpenAI `Unsupported parameter: 'max_tokens'` with newer models:
- Client now auto-retries with `max_completion_tokens`.
- Update to latest code and restart server.

---

Last updated: 2026-02-18
