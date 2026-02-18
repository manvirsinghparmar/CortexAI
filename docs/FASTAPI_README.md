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

4. Start server:
```bash
python run_server.py --reload
```

5. Open docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints

- `GET /health`
- `POST /v1/chat`
- `POST /v1/compare`

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

## Chat API

### Request shape

```json
{
  "prompt": "string (required)",
  "provider": "openai|gemini|deepseek|grok (optional in smart mode)",
  "model": "string (optional)",
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ]
  },
  "temperature": 0.7,
  "max_tokens": 1000,
  "research_mode": "off|auto|on",
  "routing_mode": "smart|cheap|strong",
  "routing_constraints": {
    "max_cost_usd": 0.01
  }
}
```

## Compare API

### Request shape

```json
{
  "prompt": "string (required)",
  "targets": [
    {"provider": "openai", "model": "gpt-5.1"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"}
  ],
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ]
  },
  "timeout_s": 30,
  "temperature": 0.7,
  "max_tokens": 1000,
  "research_mode": "off|auto|on"
}
```

Rules:
- 2 to 4 targets.
- Context rejected when targets > 2.

Persistence:
- One `llm_requests` + `llm_responses` row per compare target response.
- Shared `llm_requests.request_group_id` per compare run.
- API response `request_group_id` is canonical and matches orchestrator/log/persistence group ID.

## Schema Migrations

Apply these when enabling updated persistence flows:

```bash
psql "$DATABASE_URL" -f db/migrations/20260218_llm_requests_api_key_owner_guard.sql
psql "$DATABASE_URL" -f db/migrations/20260218_add_request_group_id_to_llm_requests.sql
```

## OpenAI Compatibility Note

For newer OpenAI models (example: `gpt-5.1`) that reject `max_tokens`, client now retries with `max_completion_tokens`.

## Guardrails

Applied in `server/utils.py`:
- Conversation history trimmed to last 10 messages.
- Total context chars capped at 8000.
- `max_tokens` clamped to 1024.

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

Last updated: 2026-02-18
