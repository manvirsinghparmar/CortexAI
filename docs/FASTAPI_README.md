# FastAPI Integration

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```
`requirements.txt` already includes `tavily-python` for research-enabled Ask/Compare flows.

2. Configure auth in `.env`:
```ini
API_KEYS=dev-key-1,dev-key-2
```

3. Configure required DB persistence:
```ini
DATABASE_URL=postgresql+psycopg://...
```

Notes:
- `DATABASE_URL` is required at startup.
- PostgreSQL URLs are required by default (`postgresql://` or `postgresql+psycopg://`).
- Dev-only override: `ALLOW_NON_POSTGRES_DATABASE_URL=true`.

4. Optional deployment boundary controls:
```ini
SERVE_FRONTEND=false
FRONTEND_DIR=frontend
# Optional frontend runtime-config override for cross-origin API calls
# FRONTEND_RUNTIME_API_BASE=https://kudlo.triobrain.com
# Optional explicit browser flag override (otherwise inherits ENABLE_DEV_SESSION_LOGIN)
# FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN=false
# Optional browser-visible dev-login token (local only)
# FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN=
# Optional prompt optimization
# ENABLE_PROMPT_OPTIMIZATION=false
# ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=false
# PROMPT_OPTIMIZER_PROVIDER=gemini
# PROMPT_OPTIMIZER_MODEL=
# PROMPT_OPTIMIZER_MAX_RETRIES=3
```

5. Start server:
```bash
python run_server.py --reload
```

6. Open docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Frontend composer keyboard UX: `Enter` sends prompt, `Shift+Enter` inserts newline.
- Frontend history sidebar cards show mode, local date/time, title, and usage cost in a compact layout; sidebar token counts are hidden.
- Frontend attachment UX: sent Ask/Compare turns show uploaded files as flat metadata-backed file cards with original filename, size/type detail, optional image thumbnail preview, and `Ready for analysis` readiness text.
- Frontend Compare selectors expose compact per-model remove controls attached to each selector only when three models are active; the controls fade in on selector hover/focus, keep at least two active models, and send only active selected models in compare requests.
- Frontend Compare response cards use compact icon-only footers; aggregate tokens, usage, and success counts remain in the summary bar.
- Frontend response card controls render as a minimal icon row for Resources, copy, and feedback actions.

## Endpoints

- `GET /health`
- `GET /health/runtime`
- `GET /runtime-config.js`
- `GET /v1/providers`
- `GET /v1/models?provider=<optional>&enabled_only=true|false`
- `POST /v1/files/upload`
- `GET /v1/files/{file_id}`
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

Protected `/v1/*` endpoints accept any one of:
- `cortex_session` cookie
- `Authorization: Bearer <gateway-bearer-token>`
- `X-API-Key: <key-from-API_KEYS>`

Invalid or missing credentials return `401`.

Session-scoped endpoints are session-scoped:
- `/v1/chat*`
- `/v1/compare*`
- `/v1/files/*`
- `/v1/providers`
- `/v1/models`
- `/v1/optimize`
- `/v1/history*`
- accepted auth: `cortex_session` cookie or `Authorization: Bearer <gateway-bearer-token>`
- API-key-only auth is rejected with `403` (`session_auth_required`)

Local-only session bootstrap helper:
- `POST /v1/auth/dev-login`
- disabled by default (`ENABLE_DEV_SESSION_LOGIN=false`)
- blocked when `APP_ENV`, `ENVIRONMENT`, or `ENV` is `prod`/`production`
- optional shared secret: `DEV_SESSION_LOGIN_TOKEN` via header `X-Dev-Login-Token`

## Frontend Runtime Config

When `SERVE_FRONTEND=true`, backend serves `GET /runtime-config.js` dynamically:
- `apiBase` defaults to current request origin.
- Override API base with `FRONTEND_RUNTIME_API_BASE` (useful for split-origin deployments).
- `enableDevSessionLogin` defaults from `ENABLE_DEV_SESSION_LOGIN`.
- Optional override for browser config: `FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN`.
- In production-like runtimes (`APP_ENV/ENVIRONMENT/ENV=prod|production`), dev-login bootstrap is forced off.
- Frontend startup completes Cognito/local dev-session bootstrap before calling session-scoped catalog endpoints (`/v1/providers`, `/v1/models`) so Ask and Compare selectors hydrate from the full enabled model registry.
- Response is sent with no-cache headers so config changes apply immediately.

## API Key Persistence Policy

In required DB runtime mode, API-key flows can resolve key ownership before model invocation.
Session-scoped chat/compare/files flows resolve persisted user identity from session/bearer auth.

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

Prompt optimization:
- `POST /v1/optimize` is gated by `ENABLE_PROMPT_OPTIMIZATION=true`.
- `/v1/optimize` is the UI optimization path; chat/compare do not auto-optimize by default.
- Set `ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=true` only when chat/compare should automatically rewrite prompts without the explicit optimize endpoint.
- `PROMPT_OPTIMIZER_MODEL` must match the configured `PROMPT_OPTIMIZER_PROVIDER`.
- Optimizer output is parsed as schema-constrained JSON and rejected when it appears to answer the prompt instead of rewriting it.
- Rejected or disabled optimization returns the original prompt with `was_optimized=false`.

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
- Server logs emit `chat.stream.*` lifecycle events from inside the response body generator, including provider-call start/completion and terminal stream reason.

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
- Server logs emit `compare.stream.*` lifecycle events from inside the response body generator, including per-target provider-call progress and terminal stream reason.

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
- Injected sources are primary evidence for current/source-dependent facts; models may still use non-conflicting baseline knowledge for background context.
- Response payloads expose normalized source metadata through `web_source_items`.

## Guardrails

Applied in `server/utils.py`:
- Conversation history trimmed to last 10 messages.
- Total context chars capped at 20000.
- `max_tokens` clamped to 2048.
- Empty-success payloads (`finish_reason=length` with blank text) are normalized to provider errors for retry/fallback safety.
- Provider-native availability failures are sanitized before DTO/stream output. Upstream 503/high-demand/overloaded errors are tagged as `error.details.kind="transient_capacity"` and rendered as `This model is temporarily busy. Try again shortly or switch to another model.` instead of raw provider JSON.
- Smart Ask keeps the existing automatic fallback loop for retryable provider failures. Manual Ask and Compare keep the user-selected model targets and return safe per-model errors when those explicit targets are unavailable.

Security/logging:
- `X-API-Key` and `Authorization` headers are redacted in auth logs.
- Middleware sets/returns `X-Request-ID` and emits request lifecycle events (`http.request.start|complete|exception`) for correlation.
- The browser frontend sends `X-Request-ID` on Ask/Compare/Optimize calls and logs stream read failures to the developer console with request id, server request id, status, elapsed time, classified kind, and received event count.
- Structured persistence logs include `request_id`/`request_group_id`, resolved `user_id`, `api_key_id`, decision path, and status.
- Research logs include `research.*` events with hashed prompt/query fields (raw Tavily query text is not logged).
- Tavily emits `research.network.diagnostics` entries (DNS + TCP reachability to Tavily host) plus normalized failure `error_kind` values for EC2 network troubleshooting.
- Attachment pipeline logs include `upload.*` + `storage.*` events for upload, storage, metadata write, sync/deferred ingestion, and rollback/error paths.
- Upload route adds `upload.route.*` events with edge/proxy request context (`X-Amz-Cf-Id`, `X-Forwarded-*`, content-length vs payload-size checks) to help isolate CloudFront/WAF/origin issues.
- Auth failures log `auth.failed` with method/path and auth-header presence flags (while redacting sensitive values).
- Circuit-breaker telemetry includes `circuit.failure.recorded`, `circuit.transition.open`, `circuit.open.blocked`, and `circuit.transition.closed`.
- File upload/status APIs sanitize client-facing `error_message` values to avoid leaking bucket names, object keys, or storage internals.
- Frontend attachment upload failures are sanitized before rendering (network/size/type/timeout/generic) so raw backend/storage error text is not shown to end users; raw errors remain available in browser console logs for debugging.
- Frontend model response errors are also sanitized during live stream finalization and history hydration, so older raw provider error payloads are not replayed in response cards. Transient model-capacity failures render with the amber `.model-soft-error` treatment.
- Logging destinations are configurable for EC2/containers via `LOG_DESTINATION=file|stdout|both`; see `docs/LOGGING.md`.

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

Last updated: 2026-04-11
