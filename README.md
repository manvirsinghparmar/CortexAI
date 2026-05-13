# CortexAI - B2B LLM Gateway (CLI + API + Frontend)

CortexAI is a multi-provider orchestration gateway for OpenAI, Gemini, DeepSeek, Grok, and Claude with:
- API-first chat/compare/streaming
- smart routing + fallback
- full DB audit trail in DB mode
- BYOK tenant key support
- usage/cost/savings reporting

## Launch-Ready Capabilities

- API endpoints: `/v1/chat`, `/v1/chat/stream`, `/v1/compare`, `/v1/compare/stream`, `/v1/providers`, `/v1/models`
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
MacOS
source .venv/bin/activate

2. Install dependencies.
```bash
pip install -r requirements.txt
pip install -r requirements-dev.txt
```
`requirements.txt` includes `tavily-python`, so Research Mode works once `TAVILY_API_KEY` is set.

3. Configure `.env`.

Minimum API setup:
```ini
API_KEYS=dev-key-1
OPENAI_API_KEY=...
GOOGLE_GEMINI_API_KEY=...
DEEPSEEK_API_KEY=...
GROK_API_KEY=...
ANTHROPIC_API_KEY=...
```

Configure DB (required):
```ini
DATABASE_URL=postgresql+psycopg://user:pass@host:5432/dbname
DB_SCHEMA=public
AUTO_REGISTER_UNMAPPED_API_KEYS=true
```

## Key Environment Variables

```ini
# Governance
# DAILY_TOKEN_CAP=100000       # optional max tokens per day
# DAILY_COST_CAP=25.00         # optional max daily spend in USD
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
SMART_CHAT_PREFERRED_PROVIDER=      # openai|gemini|deepseek|grok|claude
SMART_CHAT_ALLOWED_PROVIDERS=       # comma-separated, e.g. openai,gemini

# Prompt optimization (optional)
ENABLE_PROMPT_OPTIMIZATION=false       # enables explicit POST /v1/optimize
ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=false  # opt-in auto-rewrite inside chat/compare
PROMPT_OPTIMIZER_PROVIDER=gemini    # openai|gemini|deepseek|grok|claude
PROMPT_OPTIMIZER_MODEL=             # optional; must belong to PROMPT_OPTIMIZER_PROVIDER
PROMPT_OPTIMIZER_MAX_RETRIES=3

# Storage/privacy
STORAGE_POLICY=full       # full|metadata (default: full when unset)
REDACT_PII=false          # true|false

# Attachments / object storage (feature-flagged)
ENABLE_ATTACHMENTS=false
ATTACHMENTS_OBJECT_STORAGE_BACKEND=s3
ATTACHMENTS_S3_BUCKET=
ATTACHMENTS_S3_REGION=us-east-1
ATTACHMENTS_S3_ENDPOINT_URL=      # set for MinIO/local S3, leave empty for AWS S3
ATTACHMENTS_S3_ACCESS_KEY_ID=
ATTACHMENTS_S3_SECRET_ACCESS_KEY=
ATTACHMENTS_S3_SESSION_TOKEN=
ATTACHMENTS_S3_USE_SSL=true
ATTACHMENTS_S3_FORCE_PATH_STYLE=true
ATTACHMENTS_S3_KEY_PREFIX=attachments
ATTACHMENTS_MAX_FILE_BYTES=20971520
ATTACHMENTS_FILE_TTL_HOURS=168
ATTACHMENTS_ALLOWED_MIME_TYPES=image/jpeg,image/png,image/webp,image/gif,application/pdf,text/plain,text/csv,application/json,application/vnd.openxmlformats-officedocument.wordprocessingml.document,application/vnd.openxmlformats-officedocument.presentationml.presentation,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet

# Structured logging (EC2 / CloudWatch friendly)
LOG_LEVEL=INFO
LOG_DESTINATION=both              # file|stdout|both (default: file)
LOG_CONSOLE_LEVEL=INFO
LOG_DIR=logs                      # relative paths resolve from repo root
LOG_FILE_MAX_BYTES=10485760
LOG_FILE_BACKUP_COUNT=5
LOG_NOISY_LIBRARIES_LEVEL=WARNING # httpx/urllib3/boto3/botocore logger level
# Backward compatibility: LOG_TO_CONSOLE=true implies LOG_DESTINATION=both when LOG_DESTINATION is unset

# BYOK encryption
MASTER_KEY=replace-with-strong-random-secret

# Savings baseline
BASELINE_MODEL_ID=openai:gpt-4o-mini
# or BASELINE_PROVIDER=openai + BASELINE_MODEL=gpt-4o-mini

# Component boundary controls
SERVE_FRONTEND=true      # false => API-only runtime (no static frontend mount)
FRONTEND_DIR=frontend    # optional override when SERVE_FRONTEND=true
# Frontend runtime config served by GET /runtime-config.js
FRONTEND_RUNTIME_API_BASE=                           # optional; defaults to request origin
FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN=false      # optional browser override
FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN=            # optional browser-visible local token
```

## Pricing Configuration

- Runtime token-cost estimation uses `config/pricing.py`.
- Smart-router model economics use `config/model_registry.yaml`.
- Provider metadata/defaults/allowlists use `config/providers.yaml` via `config/provider_catalog.py`.
- Keep both files in sync when provider pricing changes.
- Current pricing tables were refreshed on `2026-03-02`.
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

### Run Components Independently

API only (disable static frontend mount):
```bash
# PowerShell
$env:SERVE_FRONTEND="false"
python run_server.py --reload
```

Frontend only (serve static UI separately):
```bash
python scripts/serve_frontend.py --host 127.0.0.1 --port 8080 --dir frontend
```

Frontend runtime config (`/runtime-config.js`):
- In monolith mode (`SERVE_FRONTEND=true`), FastAPI serves `/runtime-config.js` dynamically with `Cache-Control: no-store`.
- `apiBase` defaults to current request origin. Override with `FRONTEND_RUNTIME_API_BASE` when API is on another origin.
- Browser dev-session bootstrap flag:
  - defaults from `ENABLE_DEV_SESSION_LOGIN`
  - optional explicit frontend override: `FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN`
  - forced off in production-like runtimes (`APP_ENV/ENVIRONMENT/ENV = prod|production`)
- The frontend completes Cognito/local dev-session bootstrap before fetching `/v1/providers` and `/v1/models`, so session-scoped catalog discovery can populate Ask and Compare model dropdowns.
- Optional browser token for local bootstrap: `FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN`
- For static-only hosting (`scripts/serve_frontend.py`, CDN, etc.): copy `frontend/runtime-config.example.js` to `frontend/runtime-config.js` and set `window.CORTEX_RUNTIME_CONFIG.apiBase`.
- Composer keyboard behavior: `Enter` sends the prompt, `Shift+Enter` inserts a new line.
- History sidebar cards render compact thread metadata: mode, local date/time, title, and usage cost. Token counts are hidden in the sidebar UI.
- Compare response cards use compact icon-only footers while the compare summary bar carries aggregate tokens, usage, and success counts.
- Response card controls render as a minimal icon row for Resources, copy, and feedback actions.

## Authentication

Most `/v1/*` routes accept API key, gateway bearer token, or session cookie auth.
Most `/v1/*` routes accept API key, bearer token, or session cookie auth (route-dependent).

Session-scoped routes require signed-in identity auth (not API key):
- `/v1/chat`
- `/v1/chat/stream`
- `/v1/compare`
- `/v1/compare/stream`
- `/v1/files/*`
- `/v1/providers`
- `/v1/models`
- `/v1/optimize`
- `/v1/history`
- `/v1/history/{entry_id}`

Accepted auth for session-scoped routes:
```http
Authorization: Bearer <gateway-bearer-token>
```
or `cortex_session` cookie.

API-key-only auth on session-scoped routes is rejected with `403` (`session_auth_required`).

Local development helper:
- `POST /v1/auth/dev-login` can mint a local `cortex_session` cookie when `ENABLE_DEV_SESSION_LOGIN=true`.
- It is disabled by default and rejected when runtime env is production-like (`APP_ENV/ENVIRONMENT/ENV` = `prod|production`).
- Optional token guard: set `DEV_SESSION_LOGIN_TOKEN`, then send it as `X-Dev-Login-Token`.

Optional request correlation:
```http
X-Request-ID: <custom-id>
```
The browser frontend now sends `X-Request-ID` on Ask/Compare/Optimize calls. For
streaming requests, frontend console diagnostics include the client request id
and the server-returned request id when a stream read fails.
For EC2/Linux operational logging setup and event catalog, see `docs/LOGGING.md`.
For full AWS EC2 troubleshooting steps (CloudFront/WAF/origin correlation and Linux commands), see `docs/runbooks/aws-ec2-logging.md`.

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
- `GET /health/runtime`
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
- `DELETE /v1/byok?provider=<provider-id>` (or omit provider to delete all)
- `GET /v1/admin/request-groups/{request_group_id}/failed-attempts`
- `GET /v1/auth/cognito-config` (no auth; returns public Cognito config for frontend)
- `POST /v1/auth/dev-login` (local-development helper; gated by env flags)

### Cognito (Gmail) sign-in

To enable "Sign in with Google" via Amazon Cognito:

1. **AWS Cognito**: Create a User Pool, add an App client, configure the Cognito domain, and add Google as an identity provider (see [AWS docs](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html)).
2. **Environment** (see `.env.example`):
   - `COGNITO_USER_POOL_ID` – User pool ID (e.g. `us-east-1_xxxxxxxxx`)
   - `COGNITO_CLIENT_ID` – App client ID
   - `COGNITO_REGION` – AWS region
   - `COGNITO_DOMAIN` – Hosted UI base URL (e.g. `https://your-prefix.auth.us-east-1.amazoncognito.com`)
   - `COGNITO_REDIRECT_URI` – (optional) Callback URL; defaults to current origin + pathname
3. **Frontend**: Load the app; if Cognito is enabled, a "Sign in with Google" button appears. After sign-in, the bearer token is stored and sent as `Authorization: Bearer <token>` on API requests. Sessions/history are tied to the authenticated user identity.

`/v1/models` now includes attachment capability metadata per model:
- `supports_image_input`
- `supported_attachment_mime_types`
- `max_attachment_bytes`
- `max_attachments_per_request`

## Attachment Upload Contract (Current)

`POST /v1/files/upload` accepts raw bytes in the request body.

Authentication (session-scoped routes):
- `cortex_session` cookie, or
- `Authorization: Bearer <gateway-bearer-token>`

Headers:
- `X-File-Name: <original-filename>` (optional, defaults to `file`)
- `X-File-Content-Type: <mime-type>` (optional, falls back to `Content-Type`)

Example:
```bash
curl -X POST http://127.0.0.1:8000/v1/files/upload \
  -H "Authorization: Bearer <gateway-bearer-token>" \
  -H "X-File-Name: contract.pdf" \
  -H "X-File-Content-Type: application/pdf" \
  --data-binary "@contract.pdf"
```

`GET /v1/files/{file_id}` returns file metadata and processing status for the same authenticated owner.
Attachment routes reject API-key-only auth with `403` (`session_auth_required`).

Upload status semantics:
- `ready`: file is immediately usable in chat/compare.
- `processing`: server accepted file and deferred/ongoing ingestion; client should poll status.
- `failed`: ingestion failed; `error_code`/`error_message` explain why.
- Upload API responses now sanitize `error_message` for client safety (no bucket/key/internal storage paths in response text).
- Frontend upload UX maps failures to safe user-facing messages (network issue, file too large, unsupported type, timeout, generic retry prompt) and does not render raw backend/object-storage error text.
- Sent chat/compare turns render each uploaded attachment as a flat file card using stored metadata: original filename as the primary label, size/type detail, optional image thumbnail preview, and inline readiness text such as `Ready for analysis`.
- Raw upload errors are still logged in frontend developer console for debugging.

MVP ingestion policy:
- Small files are handled inline.
- Office docs (`.docx`, `.pptx`, `.xlsx`) may return `processing` when above `ATTACHMENTS_SYNC_INGEST_MAX_BYTES`.
- Poll `GET /v1/files/{file_id}` until `ready` before sending chat/compare with that `file_id`.
- Frontend polling budget is 60 seconds; if exceeded, attachment is marked failed in UI and user can remove/retry upload.

Use attachments in chat/compare payloads by passing file references:
```json
{
  "prompt": "Analyze this file",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "attachments": [
    {
      "file_id": "11111111-1111-1111-1111-111111111111",
      "usage_role": "primary",
      "transform_mode": "auto"
    }
  ]
}
```

Current guardrail behavior:
- attachments require `DATABASE_URL` (DB mode)
- all attachment `file_id` values must belong to the same API key owner
- model compatibility is validated before orchestration starts
- same-user deduplication is hash+size based (no cross-user dedup)
- provider adapter support in this release:
  - OpenAI: images + PDF
  - Gemini: images + PDF (inline data)
  - Claude: images + PDF (base64 document/image blocks)
  - Grok: images only
  - DeepSeek: binary attachments unsupported; text-materialized attachments are accepted

Attachment metadata semantics:
- `uploaded_files.ingestion_meta` is **file-level** metadata (ingestion requirement/state, extraction stats, etc.).
- `request_attachments.resolved_artifact_meta` is **request-level** metadata (effective transform/materialization used for that specific turn).

## Routing Modes

For Ask (`/v1/chat`, `/v1/chat/stream`) requests:
- auth must be session-based (`cortex_session` cookie or `Authorization: Bearer`)
- Explicit `provider` + `model`: deterministic target.
- `routing.smart_mode=true` (or omitted): true smart orchestration path (`routing_mode="smart"` with optional constraints from `SMART_CHAT_*` env vars).
- `routing.smart_mode=false`: legacy deterministic auto-pick path.
- `routing.research_mode=true`: orchestrator-managed web research flow with fresh sources for the current turn.
- API contract note: `routing.research_mode` is boolean (`true|false`) and is mapped to orchestrator modes `on|off`.
- Smart routing tiering now considers full runtime message payload (including research/system injection), not just base prompt/history estimates.

Prompt optimization (`/v1/optimize`):
- disabled by default unless `ENABLE_PROMPT_OPTIMIZATION=true`
- this explicit endpoint is the UI optimization path; chat/compare do not auto-optimize by default
- optional orchestrator-level auto-optimization for chat/compare requires `ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=true`
- uses `PROMPT_OPTIMIZER_PROVIDER` + optional `PROMPT_OPTIMIZER_MODEL`
- optimizer model output must be valid optimizer JSON and is rejected if it appears to answer the prompt instead of rewriting it
- if optimization is disabled or rejected, the API returns the original prompt with `was_optimized=false`

For Compare (`/v1/compare`, `/v1/compare/stream`) requests:
- auth must be session-based (`cortex_session` cookie or `Authorization: Bearer`)
- Targets are always explicit (`targets[]`).
- `routing.smart_mode` is ignored by design in compare mode.
- `routing.research_mode=true` is still honored and runs once per compare turn for all selected targets.
- Frontend Compare selectors support per-model removal with compact circular controls attached to each selector; remove controls show only when three models are active, fade in on selector hover/focus, and request payloads include only active selected models.
- Frontend Compare response cards hide per-card token/resource text in side-by-side layouts and keep compact Resources/copy/feedback icons; aggregate tokens, usage, and success counts remain in the summary bar.

## Web Research Behavior (Current)

- API contract: `routing.research_mode` accepts `true|false` (mapped to `on|off`).
- Internal orchestrator modes:
- `research_mode=off`: hard stop for this turn (no research injection, no reuse).
- `research_mode=auto`: reuse prior research only when intent/topic heuristics match; otherwise search.
- `research_mode=on`: always perform fresh search for the current turn and bypass local research cache.
- When sources are injected, they are treated as primary evidence for current/source-dependent factual claims; non-conflicting model background knowledge can still be used for explanation/context.
- If query sanitization yields empty query in `on` mode, orchestrator falls back to the raw prompt.
- Prompt injection includes citation requirements, partial-source fallback guidance, and a UTC retrieval timestamp.
- When provider timestamps are missing, Tavily source timestamps fall back to server UTC ISO timestamps (never `Timestamp: N/A`).
- Tavily runtime diagnostics emit `research.network.diagnostics` with DNS + TCP egress health (host/port configurable via `TAVILY_NETWORK_DIAGNOSTICS_*` envs) for EC2 troubleshooting.
- Tavily failures emit normalized `error_kind` fields (for example `dns_resolution_failed`, `timeout`, `auth_forbidden`, `rate_limited`) without logging raw query text.

## Session Continuity

- Ask and Compare now share the same conversation session when the same `session_id` is reused.
- Switching between Ask and Compare does not require creating a separate thread.
- Compare turns still persist their per-target rows under a shared `request_group_id`, but the user-visible chat session can remain the same across both modes.

## Chat Context Guardrails

- Conversation history sent to the API is trimmed to the last `10` messages.
- Total conversation-history payload is capped at `20000` characters per request.
- If the last `10` messages exceed that limit, the request is rejected until the sent context is smaller or a new session is started.

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

Notes:
- Chat responses now include `session_id`.
- Chat `response_done` payloads include `web_source_items` for rendered source chips.
- Chat `start` and `done` stream events include the active `session_id`.
- Server logs include `chat.stream.*` body lifecycle events so mid-stream
  disconnects can be distinguished from normal HTTP request completion.

`/v1/compare/stream` events:
- `start`
- `response_start`
- `line`
- `response_done`
- `done` (contains aggregate compare payload with `request_group_id`)
- `error`

Notes:
- Compare responses now include `session_id`.
- Per-model compare `response_done` payloads include `web_source_items`.
- Compare `start` and `done` stream events include the active `session_id`.
- The final compare `done` payload includes both `request_group_id` and `session_id`.
- Server logs include `compare.stream.*` body lifecycle events with per-target
  provider-call progress and terminal stream reason.

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

Provider-model failures that originate from upstream APIs are normalized before
they reach API/stream/frontend surfaces. `error.details.kind` carries the stable
failure class when available, such as `transient_capacity`, `rate_limited`,
`quota_exceeded`, `timeout`, `auth`, `bad_request`, or `provider_5xx`.

## Output Guardrails (Current)

- Route-level `max_tokens` is clamped to `2048` (`server/utils.py`).
- OpenAI client defaults to `max_tokens=2048` when caller omits output cap.
- If a provider returns an apparent success with empty text, routes normalize it to `provider_error` before DTO/stream output.
- Content-filtered empty responses are marked non-retryable; other empty-success responses are retryable provider errors.
- This prevents blank-success payloads from surfacing as empty assistant messages in UI/API responses.
- Raw provider availability payloads (for example 503/high-demand/overloaded errors) are converted to client-safe messages before chat, compare, stream, and history rendering. Smart Ask still uses its existing fallback loop; manual Ask and Compare preserve explicit model choices and show `This model is temporarily busy. Try again shortly or switch to another model.` when the selected model is unavailable.

## Minimal Python SDK Snippet

```python
import requests

class CortexClient:
    def __init__(self, base_url: str, bearer_token: str):
        self.base_url = base_url.rstrip("/")
        self.headers = {"Authorization": f"Bearer {bearer_token}"}

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
- Transient provider capacity failures are tagged with `error.details.kind="transient_capacity"` so routing telemetry, circuit-breaker behavior, and the amber `.model-soft-error` UI treatment stay consistent across providers.

## Privacy and Retention

- default (unset): `STORAGE_POLICY=full` behavior.
- `STORAGE_POLICY=metadata`: no raw prompt/response text persistence.
- `STORAGE_POLICY=full`: content persistence enabled.
- `REDACT_PII=true`: regex redaction for emails, phones, and card-like numbers before DB storage.

## Build Artifacts

Frontend artifact (static files + manifest + zip):
```bash
python scripts/build_frontend_artifact.py
```

API runtime image:
```bash
docker build -f Dockerfile.api -t cortexai-api:dev .
```

These artifacts are intentionally separate so frontend-only or API-only changes can be built independently.

## DB Migration Runbook

- See `docs/runbooks/db-migrations.md` for migration authoring, apply order, rollback strategy, and verification checks.

## Release Gate

Use this before launch/deploy:
```bash
python scripts/release_gate.py
```

It runs:
- `python -m py_compile ...`
- `pytest -q`
- DB mode smoke test (`/v1/chat` + DB row assertions for `llm_requests` and `usage_daily`)

## CI and Workflows

- `.github/workflows/ci.yml`:
  - path-aware frontend/backend quality checks
  - changed-file Python Ruff/MyPy gates with pinned dev tool versions
  - Black format check is advisory until the repository has a formatting baseline
  - frontend artifact build
  - API image build metadata export
  - pinned Gitleaks CLI directory scan of the checked-out tree
- `.github/workflows/incident-regression-38.yml`:
  - targeted backend regression pack for routing/guardrail mismatches (38 tests)
  - no live provider keys required
- `.github/workflows/live-e2e.yml`:
  - live Playwright browser suite with real providers
  - uses GitHub Environment `live-e2e`
  - runs on `windows-latest` and provisions local PostgreSQL in-workflow
  - initializes schema from `db/schema_public_snapshot.sql` + `db/migrations/*.sql`
  - publishes Playwright JUnit results directly into GitHub Checks + run summary (no artifact download needed for first-pass triage)

Required secrets for `live-e2e` environment:
- `E2E_API_KEY` (gateway auth key used by E2E suite; not a provider billing key)
- `OPENAI_API_KEY`
- `GOOGLE_GEMINI_API_KEY`
- `ANTHROPIC_API_KEY`
- `GROK_API_KEY`
- `DEEPSEEK_API_KEY`
- optional web/search keys used by test prompts: `BRAVE_API_KEY`, `SERPAPI_API_KEY`

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

Run full suite with an HTML report artifact:
```bash
python scripts/test_report_runner.py
```

This generates:
- timestamped report folder under `reports/test-results/<YYYYMMDD-HHMMSS>/`
- HTML dashboard report at `reports/test-results/latest-report.html`
- JUnit XML at `reports/test-results/latest-junit.xml`

Run B2B launch tests only:
```bash
python -m pytest tests/test_b2b_launch_features.py -q
```

Run full B2B API checklist against a live server:
```bash
python scripts/e2e_b2b_checklist.py --base-url http://127.0.0.1:8000 --api-key dev-key-1
```

Run browser E2E suite (Playwright):
```bash
npm run --prefix e2e test
```

Run high-impact UI business scenarios only:
```bash
npm run --prefix e2e test -- specs/50.high-impact-business-ui.spec.mjs
```

Run incident regression pack locally (same target set as workflow):
```bash
python -m pytest -q \
  tests/test_routing_regression.py \
  tests/test_fallback_manager.py \
  tests/test_smart_router_metadata.py \
  tests/test_server_utils.py \
  tests/test_unified_response_contract.py \
  tests/test_fastapi_contract_and_guardrails.py \
  tests/test_api_persistence_guardrails.py
```

Postman collection:
- `docs/postman/CortexAI_B2B.postman_collection.json`

## Project Structure

```text
OpenAIProject/
  .dockerignore
  Dockerfile.api
  main.py
  run_server.py
  list-models.cmd
  quick_test_optimizer.py
  README.md
  requirements.txt
  requirements-dev.txt
  pyproject.toml
  pytest.ini

  .github/
    workflows/
      ci.yml
      incident-regression-38.yml
      live-e2e.yml

  api/
    base_client.py
    claude_client.py
    client_registry.py
    deepseek_client.py
    google_gemini_client.py
    grok_client.py
    openai_client.py
    provider_adapter.py

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
    schema_public_snapshot.sql
    migrations/
      20260218_add_request_group_id_to_llm_requests.sql
      20260218_llm_requests_api_key_owner_guard.sql
      20260222_b2b_launch_tables.sql
      20260222_go_live_hardening.sql
    repository.py
    session.py
    tables.py

  docs/
    README.md
    CHANGELOG.md
    COMPARE_MODE_GUIDE.md
    DATABASE_INTEGRATION_COMPLETE.md
    FASTAPI_README.md
    LOGGING.md
    PROJECT_MAP.md
    REFACTORING_SUMMARY.md
    SMART_ROUTING_DIAGRAM.md
    TAVILY_INTEGRATION.md
    UNIFIED_RESPONSE_CONTRACT.md
    USER_FLOW_DIAGRAM_SOURCE.md
    adr/
      0001-architecture-baseline-and-deploy-boundaries.md
      0002-provider-validation-and-safety-rails.md
      0003-component-deployment-readiness-boundaries.md
    runbooks/
      db-migrations.md
    postman/
      CortexAI_B2B.postman_collection.json

  frontend/
    index.html
    app.js
    runtime-config.example.js
    style.css
    smart-routing-state.js
    layout-smoke.test.mjs
    provider-discovery.e2e.test.mjs
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
    build_frontend_artifact.py
    db_mode_smoke.py
    e2e_b2b_checklist.py
    generate_proof_pack.py
    onboard_tenant.py
    release_gate.py
    run_playwright_mcp.py
    serve_frontend.py
    test_report_runner.py

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
    runtime_checks.py
    savings.py
    usage_reporting.py
    utils.py
    routes/
      __init__.py
      admin.py
      byok.py
      catalog.py
      chat.py
      compare.py
      files.py
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

  tests/
    __init__.py
    conftest.py
    README.md
    test_api.py
    test_api_key_hashing.py
    test_api_persistence_guardrails.py
    test_b2b_launch_features.py
    test_component_boundaries.py
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
    test_research_pack.py
    test_routing_regression.py
    test_server_utils.py
    test_smart_router_metadata.py
    test_tavily_client.py
    test_tier_decider.py
    test_unified_response_contract.py
    test_dynamic_provider_discovery_e2e.py
    ... (additional unit/integration suites)

  e2e/
    README.md
    package.json
    playwright.config.mjs
    global-setup.mjs
    global-teardown.mjs
    fixtures/
      live-e2e.mjs
    helpers/
      api.mjs
      cleanup.mjs
      config.mjs
      db.mjs
      ids.mjs
      network.mjs
      prompts.mjs
      runtime-state.mjs
      ui.mjs
    server/
      run_e2e_server.py
      fault_injection.py
      stream_tuning.py
    specs/
      00.app-readiness.spec.mjs
      10.ask-and-routing.spec.mjs
      20.session-and-history.spec.mjs
      30.persistence-and-fallback.spec.mjs
      40.compare-three-models.spec.mjs
      50.high-impact-business-ui.spec.mjs
      _helpers.mjs
    test-data/
      routing-outcomes.mjs
```

## What to Edit for Common Changes

- Add a new API endpoint: `server/routes/*.py` + wire router in `server/app.py` + request/response models in `server/schemas/`.
- Add business logic/service code: `server/*.py` (keep route handlers thin; move logic into services).
- Add or change provider behavior: `api/*.py`, `api/client_registry.py`, orchestration flow in `orchestrator/core.py`, and provider metadata in `config/providers.yaml`.
- Change smart routing rules: `orchestrator/prompt_analyzer.py`, `orchestrator/tier_decider.py`, `orchestrator/model_selector.py`, `orchestrator/smart_router.py`.
- Change web research behavior: `orchestrator/core.py` + `tools/web/intent.py` + `tools/web/tavily_service.py` + `tools/web/research_pack.py`.
- Add DB tables/columns/indexes: create SQL migration in `db/migrations/`, then update reflected usage in `db/tables.py` and queries in `db/repository.py`.
- Change persistence/audit behavior for FastAPI: `server/persistence.py` (shared write path for chat/compare/stream).
- Change usage/savings/BYOK behavior: `server/usage_reporting.py`, `server/savings.py`, `server/byok_service.py`, and related routes under `server/routes/`.
- Add/adjust guardrails: `server/rate_limit.py`, `server/circuit_breaker.py`, privacy policy in `server/privacy.py`.
- Update CI/workflow behavior: `.github/workflows/ci.yml`, `.github/workflows/live-e2e.yml`, `.github/workflows/incident-regression-38.yml`.
- Add tenant/dev tooling scripts: `scripts/` (runtime checks/reporting) and `tools/` (operator/dev helpers).
- Add tests: put new tests in `tests/` (mirror by feature area) and run `python -m pytest -q` + `python scripts/release_gate.py`.
- Update API docs and examples after behavior changes: `README.md` and `docs/postman/CortexAI_B2B.postman_collection.json`.

Last updated: 2026-04-13
