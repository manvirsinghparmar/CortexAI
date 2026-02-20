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

5. Open API docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints

- `GET /health`
- `POST /v1/chat`
- `POST /v1/compare`

## Authentication

Protected endpoints require:
- `X-API-Key: <value in API_KEYS>`

Invalid or missing key returns `401`.

## Chat API

### Request shape

```json
{
  "prompt": "string (required)",
  "provider": "openai|gemini|deepseek|grok (optional)",
  "model": "string (optional)",
  "context": {
    "session_id": "uuid-string (optional)",
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
  },
  "prompt_optimization_enabled": true
}
```

### Behavior notes

- `provider` + `model` are optional in smart routing.
- `max_tokens` is clamped to `1024`.
- Context is trimmed to last 10 messages and capped at 8000 chars.
- If DB is enabled and `context.session_id` is provided, it must exist in `public.sessions.id`; otherwise DB persistence can fail due FK constraints.

## Compare API

### Request shape

```json
{
  "prompt": "string (required)",
  "targets": [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"}
  ],
  "context": {
    "session_id": "uuid-string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ]
  },
  "timeout_s": 60,
  "temperature": 0.7,
  "max_tokens": 1000,
  "research_mode": "off|auto|on",
  "prompt_optimization_enabled": false
}
```

### Rules

- 2 to 4 targets are allowed by API.
- Context is rejected when `targets > 2`.
- If `targets[].model` is omitted, backend fills provider defaults:
  - OpenAI: `DEFAULT_OPENAI_MODEL` or `gpt-4o-mini`
  - Gemini: `DEFAULT_GEMINI_MODEL` or `gemini-2.5-flash-lite`
  - DeepSeek: `DEFAULT_DEEPSEEK_MODEL` or `deepseek-chat`
  - Grok: `DEFAULT_GROK_MODEL` or `grok-4-1-fast-non-reasoning`

## UI to API Mapping

Current web UI (`ui/`) uses FastAPI directly:

- Single mode (default):
  - Endpoint: `POST /v1/chat`
  - Default smart routing ON (`routing_mode: "smart"` with no provider/model).
  - Smart routing OFF sends explicit `provider` + `model`.
- Compare mode:
  - Endpoint: `POST /v1/compare`
  - UI sends exactly 2 targets.
  - Smart routing control is hidden in compare mode.
- Toggles:
  - Prompt Optimization -> `prompt_optimization_enabled` (boolean)
  - Research Mode -> `research_mode` (`on` or `off` from UI)
- Context:
  - UI sends `conversation_history` only (no `context.session_id`) to avoid session FK issues in persistence paths.

## Persistence and IDs

- Response `request_id` maps to `public.llm_requests.request_id`.
- Compare response `request_group_id` maps to `public.llm_requests.request_group_id`.
- `X-Request-ID` is a transport correlation ID (middleware/logging), not the DB audit key.

Persistence:
- Chat: one `llm_requests` + one `llm_responses` row per response.
- Compare: one `llm_requests` + one `llm_responses` per model response, all sharing `request_group_id`.

## DB Verification Queries

Single request by `request_id`:

```sql
SELECT r.*, resp.*
FROM public.llm_requests r
LEFT JOIN public.llm_responses resp ON resp.llm_request_id = r.id
WHERE r.request_id = 'd8d75d69-6619-4b57-8205-800729ed5eb5';
```

Compare run by `request_group_id`:

```sql
SELECT r.*, resp.*
FROM public.llm_requests r
LEFT JOIN public.llm_responses resp ON resp.llm_request_id = r.id
WHERE r.request_group_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee'
ORDER BY r.created_at DESC;
```

Fetch failure reasons:

```sql
SELECT
  r.request_id,
  r.request_group_id,
  r.provider,
  r.model,
  resp.finish_reason,
  resp.error_type,
  resp.error_message
FROM public.llm_requests r
JOIN public.llm_responses resp ON resp.llm_request_id = r.id
WHERE r.request_id = 'd8d75d69-6619-4b57-8205-800729ed5eb5'
   OR r.request_group_id = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';
```

Routing decisions and attempts:

```sql
SELECT
  r.request_id,
  rd.routing_mode,
  rd.initial_tier,
  rd.final_tier,
  rd.attempt_count,
  ra.attempt_number,
  ra.provider,
  ra.model,
  ra.validation,
  ra.error_type,
  ra.error_message
FROM public.llm_requests r
LEFT JOIN public.routing_decisions rd ON rd.llm_request_id = r.id
LEFT JOIN public.routing_attempts ra ON ra.routing_decision_id = rd.id
WHERE r.request_id = 'd8d75d69-6619-4b57-8205-800729ed5eb5'
ORDER BY ra.attempt_number;
```

## API Key Persistence Policy (DB-enabled routes)

When `DATABASE_URL` is set, chat/compare persistence resolves API key ownership before model invocation.

Env flags:
- `AUTO_REGISTER_UNMAPPED_API_KEYS=false` (safe default)
- `ALLOW_UNMAPPED_API_KEY_PERSIST=false` (safe default)
- `API_KEY_FALLBACK_USER_EMAIL=api@cortexai.local`
- `API_KEY_FALLBACK_USER_NAME=API Service User`

Behavior for keys present in `API_KEYS` but unmapped in `public.api_keys`:
1. If `AUTO_REGISTER_UNMAPPED_API_KEYS=true`: key mapping is created under service user.
2. Else if `ALLOW_UNMAPPED_API_KEY_PERSIST=true`: persist under service user with `api_key_id=NULL`.
3. Else: request is rejected with `403`.

Guardrail:
- If `llm_requests.api_key_id` is set, `llm_requests.user_id` must match `api_keys.user_id`.
- Enforced in app logic and DB trigger migration.

## Register Dev/Test Key

Zero-arg helper:

```bash
python tools/register_dev_key.py
```

Param-based helper:

```bash
python tools/create_api_key.py --email api@cortexai.local --name "API Service User" --key "dev-key-1" --label "postman-dev"
```

## Schema Migrations

Apply these when enabling updated persistence flows:

```bash
psql "$DATABASE_URL" -f db/migrations/20260218_llm_requests_api_key_owner_guard.sql
psql "$DATABASE_URL" -f db/migrations/20260218_add_request_group_id_to_llm_requests.sql
```

## OpenAI Compatibility Note

For newer OpenAI models (example: `gpt-5.1`) that reject `max_tokens`, client retries with `max_completion_tokens`.

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

Last updated: 2026-02-19
