# FastAPI Integration

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure auth in `.env`:
```ini
API_KEYS=dev-key-1,dev-key-2
```

3. Optional DB persistence:
```ini
DATABASE_URL=postgresql+psycopg://...
```

4. Optional deployment boundary controls:
```ini
SERVE_FRONTEND=false
FRONTEND_DIR=frontend
```

5. Start server:
```bash
python run_server.py --reload
```

6. Open docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints

- `GET /health`
- `GET /health/runtime`
- `GET /v1/providers`
- `GET /v1/models?provider=<optional>&enabled_only=true|false`
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
- `DELETE /v1/byok?provider=<provider-id>`
- `GET /v1/admin/request-groups/{request_group_id}/failed-attempts`

## Authentication

Protected endpoints require:
- `X-API-Key: <key-from-API_KEYS>`

Invalid or missing key returns `401`.

## API Key Persistence Policy (DB-enabled routes)

When `DATABASE_URL` is set, chat/compare persistence resolves API key ownership before model invocation.

Env flags:
- `AUTO_REGISTER_UNMAPPED_API_KEYS=false` (safe default)
- `ALLOW_UNMAPPED_API_KEY_PERSIST=false` (safe default)
- `API_KEY_FALLBACK_USER_EMAIL=api@cortexai.local`
- `API_KEY_FALLBACK_USER_NAME=API Service User`

Behavior for key present in `API_KEYS` but unmapped in `public.api_keys`:
1. If `AUTO_REGISTER_UNMAPPED_API_KEYS=true`: creates DB mapping under service user.
2. Else if `ALLOW_UNMAPPED_API_KEY_PERSIST=true`: persists with service user and `api_key_id=NULL`.
3. Else: rejects with `403`.

Guardrail:
- If `llm_requests.api_key_id` is set, `llm_requests.user_id` must match `api_keys.user_id`.
- Enforced in app logic and DB trigger migration.

## Register Dev/Test Key

Preferred zero-arg helper (IDE-friendly):
```bash
python tools/register_dev_key.py
```

Param-based helper:
```bash
python tools/create_api_key.py --email api@cortexai.local --name "API Service User" --key "dev-key-1" --label "postman-dev"
```

## Shared Request Concepts

Common request fields used by Ask and Compare:

```json
{
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ],
    "new_session": false
  },
  "routing": {
    "smart_mode": true,
    "research_mode": false
  },
  "temperature": 0.7,
  "max_tokens": 1000
}
```

Notes:
- `routing.smart_mode` defaults to `true`.
- `routing.research_mode` is a boolean in the current API contract, not `"off|auto|on"`.
- Ask and Compare can reuse the same `session_id`; session continuity is shared across both modes.
- If `session_id` is omitted in DB mode, the backend may resolve the user's most recent active session.

## Chat API

### Request shape

```json
{
  "prompt": "string (required)",
  "provider": "openai|gemini|deepseek|grok|claude (optional in smart mode)",
  "model": "string (optional when provider is set)",
  "routing": {
    "smart_mode": true,
    "research_mode": false
  },
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ],
    "new_session": false
  },
  "temperature": 0.7,
  "max_tokens": 1000
}
```

Rules:
- If `model` is provided, `provider` is required.
- In manual Ask mode, `provider` + `model` gives deterministic targeting.
- With `routing.smart_mode=true`, Ask uses the smart orchestration path.
- With `routing.research_mode=true`, Ask uses orchestrator-managed web research with fresh sources for the current turn.

### Response shape

```json
{
  "request_id": "string",
  "session_id": "string (optional)",
  "text": "string",
  "provider": "string",
  "model": "string",
  "latency_ms": 1234,
  "token_usage": {
    "prompt_tokens": 100,
    "completion_tokens": 250,
    "total_tokens": 350
  },
  "estimated_cost": 0.00123,
  "cost_currency": "USD",
  "finish_reason": "stop|length|tool|content_filter|error|null",
  "error": null,
  "web_source_items": [
    {"title": "Source title", "url": "https://example.com"}
  ],
  "timestamp": "2026-03-08T00:00:00Z"
}
```

### Streaming contract

`POST /v1/chat/stream` returns NDJSON events:
- `start`
- `line`
- `response_done`
- `done`
- `error`

Notes:
- `start` includes `session_id`, `research_mode`, and an initial `web_source_items` array.
- `response_done` includes the full `ChatResponseDTO`, including `session_id` and `web_source_items`.
- `done` includes the resolved `session_id`.

## Compare API

### Request shape

```json
{
  "prompt": "string (required)",
  "targets": [
    {"provider": "openai", "model": "gpt-5.1"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"}
  ],
  "routing": {
    "smart_mode": true,
    "research_mode": false
  },
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ],
    "new_session": false
  },
  "timeout_s": 30,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

Rules:
- 2 to 4 targets.
- Compare always uses explicit targets.
- `routing.smart_mode` is ignored in compare mode by design.
- With `routing.research_mode=true`, research runs once per compare turn and is shared across all selected targets for fairness.

Persistence:
- One `llm_requests` + `llm_responses` row per compare target response.
- Shared `llm_requests.request_group_id` per compare run.
- API response `request_group_id` is canonical and matches orchestrator/log/persistence group ID.

### Response shape

```json
{
  "request_group_id": "string",
  "session_id": "string (optional)",
  "responses": [
    {
      "request_id": "string",
      "session_id": "string (optional)",
      "text": "string",
      "provider": "string",
      "model": "string",
      "latency_ms": 1234,
      "token_usage": {
        "prompt_tokens": 100,
        "completion_tokens": 250,
        "total_tokens": 350
      },
      "estimated_cost": 0.00123,
      "cost_currency": "USD",
      "finish_reason": "stop|length|tool|content_filter|error|null",
      "error": null,
      "web_source_items": [
        {"title": "Source title", "url": "https://example.com"}
      ],
      "timestamp": "2026-03-08T00:00:00Z"
    }
  ],
  "success_count": 2,
  "error_count": 0,
  "total_tokens": 700,
  "total_cost": 0.00246,
  "timestamp": "2026-03-08T00:00:00Z"
}
```

### Streaming contract

`POST /v1/compare/stream` returns NDJSON events:
- `start`
- `response_start`
- `line`
- `response_done`
- `done`
- `error`

Notes:
- `start` includes `session_id`, `research_mode`, and target count.
- Each `response_done` includes one full `ChatResponseDTO`.
- Final `done` includes the aggregate compare payload with both `request_group_id` and `session_id`.

## Schema Migrations

Apply these when enabling updated persistence flows:

```bash
psql "$DATABASE_URL" -f db/migrations/20260218_llm_requests_api_key_owner_guard.sql
psql "$DATABASE_URL" -f db/migrations/20260218_add_request_group_id_to_llm_requests.sql
```

No new DB migration is required for shared Ask/Compare session continuity; that behavior is currently implemented in persistence/session resolution logic.

## OpenAI Compatibility Note

For newer OpenAI models (example: `gpt-5.1`) that reject `max_tokens`, client now retries with `max_completion_tokens`.

## Research Behavior

- Web research is orchestrator-managed.
- When `routing.research_mode=true`, Ask performs a fresh research pass for the current turn.
- When `routing.research_mode=true`, Compare performs one shared research pass for the compare turn.
- Response payloads expose normalized source metadata through `web_source_items`.

## Guardrails

Applied in `server/utils.py`:
- Conversation history trimmed to last 10 messages.
- Total context chars capped at 20000.
- `max_tokens` clamped to 2048.
- Empty-success payloads (`finish_reason=length` with blank text) are normalized to provider errors for retry/fallback safety.

Security/logging:
- `X-API-Key` and `Authorization` headers are redacted in auth logs.
- Structured persistence logs include `request_id`/`request_group_id`, resolved `user_id`, `api_key_id`, decision path, and status.

## Testing

Run FastAPI contract tests:
```bash
pytest tests/test_fastapi_contract_and_guardrails.py -v
```

Run persistence guardrail tests:
```bash
pytest tests/test_api_persistence_guardrails.py -v
```

Run compare orchestrator tests:
```bash
pytest tests/test_multi_compare_mode.py -v
```

---

Last updated: 2026-03-19
