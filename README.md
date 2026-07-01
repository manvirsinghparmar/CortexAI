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
- Reporting/export: `/v1/usage`, `/v1/usage/summary`, `/v1/savings`, CSV export endpoints
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
`requirements.txt` includes `tavily-python`, so Research Mode works once `TAVILY_API_KEY` is set. The FastAPI dependency is constrained away from `0.136.3` because that release is currently flagged by `pip-audit` advisory `MAL-2026-4750`.
`requirements.txt` includes `tavily-python`, so Research Mode works once `TAVILY_API_KEY` is set.
React frontend dependencies are managed by npm, not `requirements.txt`. If you want to run or build the React UI from `frontend-react/`, also install its locked Node dependencies:
```bash
npm ci --prefix frontend-react
```
Use Node.js 20.x for the React/Vite toolchain.

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
PROMPT_OPTIMIZER_TIMEOUT_MS=5000    # explicit /v1/optimize hard deadline
PROMPT_OPTIMIZER_ROUTE_MAX_RETRIES=2 # explicit /v1/optimize attempt count
PROMPT_OPTIMIZER_MAX_OUTPUT_TOKENS=450 # compact optimizer output cap
PROMPT_OPTIMIZER_TEMPERATURE=0.2    # low-drift optimizer generation setting

# Tavily research retrieval
TAVILY_API_KEY=                     # required when research_mode=true
TAVILY_ENHANCED_SEARCH_ENABLED=true # false => fixed Tavily params only
TAVILY_CHUNKS_PER_SOURCE=3          # 1..3; invalid values fall back to 3
TAVILY_ENHANCED_SEARCH_DOMAIN_RULES=true
TAVILY_NETWORK_DIAGNOSTICS_HOST=api.tavily.com
TAVILY_NETWORK_DIAGNOSTICS_PORT=443
TAVILY_NETWORK_DIAGNOSTICS_INTERVAL_SECONDS=300
TAVILY_NETWORK_DIAGNOSTICS_TIMEOUT_SECONDS=2

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
FRONTEND_DIR=frontend    # optional override when SERVE_FRONTEND=true; set to frontend-react/dist for React
REACT_FRONTEND=false     # optional convenience switch; when true and FRONTEND_DIR is unset, serves frontend-react/dist
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

Run the full local app (FastAPI API + React/Vite frontend):
```bash
python run_app.py
```

Useful URLs:
- React frontend: `http://127.0.0.1:5173/`
- API health: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`

For local browser session bootstrap, keep `ENABLE_DEV_SESSION_LOGIN=true` in `.env` or pass:
```bash
python run_app.py --enable-dev-login
```

`run_app.py` starts FastAPI with `SERVE_FRONTEND=false`, runs `npm run --prefix frontend-react dev`, and points both Vite's `/v1`, `/auth`, and `/runtime-config.js` proxy plus `FRONTEND_RUNTIME_API_BASE` at the selected API host/port.
Before launching either process, the runner verifies that both requested ports are available and reports a clear error when another process owns one. On Windows, shutdown terminates the complete FastAPI/Vite process trees so failed startup or `Ctrl+C` does not leave an orphaned Vite listener.

Run the API server by itself:
```bash
python run_server.py --reload
```

Useful URLs:
- Health: `http://127.0.0.1:8000/health`
- Swagger: `http://127.0.0.1:8000/docs`
- Legacy/static frontend when FastAPI serves one: `http://127.0.0.1:8000/`

### Run the React Frontend Through FastAPI

Build the React/Vite app first, then point the FastAPI static mount at the generated `dist` folder:

```powershell
npm ci --prefix frontend-react
npm run --prefix frontend-react build
$env:FRONTEND_DIR=(Resolve-Path .\frontend-react\dist).Path
python run_server.py --reload
```

`FRONTEND_DIR` is the most explicit option and takes precedence over `REACT_FRONTEND`. For a shorter local setup, you can set `REACT_FRONTEND=true` instead, as long as `frontend-react/dist` already exists:

```powershell
$env:REACT_FRONTEND="true"
python run_server.py --reload
```

Do not add React packages to `requirements.txt`; keep React dependencies in `frontend-react/package.json` and `frontend-react/package-lock.json`.

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

React development server (hot reload, with `/v1`, `/auth`, and `/runtime-config.js` proxied to the API on port 8000):
```bash
npm run --prefix frontend-react dev
```

When launched by `run_app.py`, Vite reads `CORTEX_API_PROXY_TARGET` from the runner so custom `--api-host` / `--api-port` values stay aligned with the frontend proxy.

For this split local workflow, run the API separately with `SERVE_FRONTEND=false`:
```powershell
$env:SERVE_FRONTEND="false"
python run_server.py --reload
```

Frontend runtime config (`/runtime-config.js`):
- In monolith mode (`SERVE_FRONTEND=true`), FastAPI serves `/runtime-config.js` dynamically with `Cache-Control: no-store`.
- `apiBase` defaults to current request origin. Override with `FRONTEND_RUNTIME_API_BASE` when API is on another origin.
- Browser dev-session bootstrap flag:
  - defaults from `ENABLE_DEV_SESSION_LOGIN`
  - optional explicit frontend override: `FRONTEND_RUNTIME_ENABLE_DEV_SESSION_LOGIN`
  - forced off in production-like runtimes (`APP_ENV/ENVIRONMENT/ENV = prod|production`)
- The frontend completes Cognito/local dev-session bootstrap before fetching session-scoped startup data (`/v1/providers`, `/v1/models`, and `/v1/history`), so local development history appears on load instead of waiting for the first chat request.
- Optional browser token for local bootstrap: `FRONTEND_RUNTIME_DEV_SESSION_LOGIN_TOKEN`
- For static-only hosting (`scripts/serve_frontend.py`, CDN, etc.): copy `frontend/runtime-config.example.js` to `frontend/runtime-config.js` and set `window.CORTEX_RUNTIME_CONFIG.apiBase`.
- For standalone React production hosting, make `/runtime-config.js` available at the same origin as the React app and route `/v1/*` plus `/auth` to the API origin. The current React client uses same-origin relative API paths, so a CDN/load-balancer/nginx rule should proxy those paths to the FastAPI service.
- Composer keyboard behavior: `Enter` sends the prompt, `Shift+Enter` inserts a new line.
- React startup waits for Cognito/local dev-session bootstrap before fetching `/v1/models` and `/v1/history`; background history failures do not surface as the primary chat error banner. It persists the active `session_id` in browser storage and restores that transcript after reloads, Chrome tab refreshes, mobile/desktop browser resume, and same-browser reauth.
- The React sidebar uses a compact navigation rail with subtle Ask/Compare/Usage and current-session states. On desktop, an icon-only control at the top right collapses the sidebar to a narrow action rail and expands it back to the full history view; the bottom-left session tile is status-only once a session is active, while explicit logout stays in the account menu. Mobile continues to use the separate top and bottom navigation, with `Usage & insights` reached from the account menu. The mobile Usage route uses the compact 2x2 KPI grid, Smart-pick leaderboard strip, session-mode bar, and Ask/Compare/History footer navigation. Desktop History renders each `session_id` as a two-line borderless row: a single-line title plus mode and the latest activity date. Model names, turn counts, and token counts stay hidden; long titles truncate visually while remaining available through the row tooltip and search still covers every persisted turn. Desktop and mobile History rows reveal an inline delete control on hover/focus, require a short in-row confirmation, and remove every persisted row in that thread; deleting the active thread starts a clean chat.
- Selecting a history thread reloads its complete persisted transcript. Ask rows become chronological turns, while Compare target rows sharing a `request_group_id` are reconstructed as one multi-model turn.
- An explicit fresh sign-in starts an empty new chat session instead of appending the first prompt to the previously active thread. Browser refreshes, tab resume/reload, same-browser reauth, and explicit History selections continue the selected thread.
- React Ask and Compare turns send `context.session_id`, bounded `conversation_history`, and `new_session` so follow-ups continue the selected thread and New Chat starts a new backend session.
- React Ask starts with the `Web` source toggle enabled for new page sessions, and React Compare starts with `With sources` enabled; users can turn either off for the current page session. Compare mode streams `/v1/compare/stream` events into each model response column.
- React Compare keeps every selected response visible in a responsive grid without a horizontal response rail on desktop and tablet widths: three columns on wide desktop, two columns at tablet widths, and stacked tall cards at the app's tablet/mobile shell breakpoint. Phone-sized mobile restores the segmented model switcher, shows one selected response card at a time in natural page flow, and elevates the switcher into a frosted sticky bar with provider-tinted active cues while keeping every model pill horizontally stable during scroll transitions.
- Compare card headers and action footers remain fixed inside each desktop/tablet panel while only the answer body scrolls. The transcript retains bottom breathing room above the persistent composer so the input area does not compress the reading workspace.
- React Compare renders submitted prompts with the same right-aligned user bubble used by Ask mode. Aggregate result totals remain in a separate compact row, while model cards keep friendly names, exact API model IDs, and compact icon actions.
- React Ask and Compare use one rounded composer shell with a borderless textarea that starts at one line and auto-grows to a bounded height. Attachments stay above the compact routing controls and fixed-size send action; mode changes remain in the app navigation rather than a redundant composer switch. Compare model selectors use a subtle opposing-arrows connector between active models: a bordered medallion on desktop and a compact borderless glyph on mobile. The selector row scrolls horizontally rather than compressing model names when a third model exceeds the mobile width. Its shared dropdown is rendered in a viewport-positioned body portal so mobile overflow containers cannot clip model options.
- The React composer shell uses a transparent structural border and soft elevation instead of a visible rectangular outline. Textarea focus removes the browser outline and strengthens the shell shadow without changing layout on desktop or mobile.
- React Smart, Web/With sources, and Improve chips expose the same concise guidance as the legacy UI through accessible tooltips. Enabled chips use a theme-aware high-contrast fill, label, and accent ring so their state remains clear in light and dark themes. Compare's With sources and Improve controls use the same background, border, label, and shadow treatment whenever they share the same toggle state. Tooltips open on pointer hover or keyboard focus and stay within narrow viewports. On touch screens, the same tap toggles the chip and shows its tooltip for two seconds.
- On mobile answer screens, the follow-up composer rests as a docked pill above the fixed Ask/Compare/History navigation. The pill shows the current routing context and opens the bottom sheet on tap; that same tap focuses the textarea and places the cursor at the end of any draft so typing can begin immediately. The expanded sheet keeps attachment chips, routing controls, and the fixed-size send action clear of the tab bar. Answer transcripts reserve enough bottom scroll clearance for response copy, regenerate, and feedback actions to remain reachable above the dock.
- Mobile exposes one persistent square-pen action in the header for starting a new session from Ask, Compare, or History. It cancels active generation, clears the current thread, returns to chat, and preserves the selected mode; History does not duplicate this action.
- React file upload uses the current raw-byte `POST /v1/files/upload` contract, polls `GET /v1/files/{file_id}` while uploads are processing, and sends attachment IDs on Ask/Compare requests.
- Compare response cards use compact footers while the compare summary bar carries aggregate tokens, usage, and success counts. Completed duration, token, and cost metrics render as a packed mono strip with abbreviated values (`s`, `tok`, dollars); fastest/cheapest winners get the success tint, with the text label shown only where desktop space allows.
- Mobile and desktop response cards show completed duration, token, and cost metadata directly in the header without a run-details chevron. Pending and failed cards keep their muted elapsed/status line visible on mobile and desktop. Response-card duration uses the same UI-observed elapsed timing when live timestamps are available, falls back to API `latency_ms` for restored rows, and unavailable token counts stay hidden instead of rendering zero-token placeholders.
- Ask and Compare response headers use the same shared provider-logo and model-presentation resolver as the model picker. Failed or unavailable logo assets retain a provider-initial fallback instead of leaving a blank header.
- Empty streaming cards render an independent request-aware loading state with a subtle sparkle and skeleton lines. Ask, Compare, source-enabled, and prompt-improved turns use contextual copy, and the loading block disappears when that card receives its first token or error.
- Smart Ask pending cards remain model-neutral because the chat stream `start` event contains only a pre-runtime routing preview. They show `Smart routing` while waiting and adopt the authoritative provider/model from `response_done`.
- Response card controls render as a minimal icon row for copy, regenerate, and feedback actions. Copy shows a brief visible success confirmation in the toolbar. Regenerate refills the clicked response card in place through the existing chat streaming path for that response model, including when the clicked card came from Compare mode. It preserves the original turn's source-enabled flag, so source-backed regenerations run a new backend research/search pass.
- Response sources render inline as publisher-name citation pills derived from `web_source_items`; grouped markers such as `[1][2][3]` collapse into one pill with a preview card listing each linked source. On desktop, hovering the pill opens a viewport-contained preview directly beside the pill and leaving the hover area closes it; on mobile, tapping still opens the bottom sheet. The external-link icon opens the first cited source directly.
- Response Markdown rendering preserves explicit ordered-list numbering even when numbered items are separated by explanatory text.
- React response Markdown includes inline citation pills with tap/click source previews, direct external source-icon links, blockquote callout styling, styled code blocks with copy controls, GFM tables, and sanitized provider error states. Tables stay inside a horizontal response-card scroller on desktop and become labelled stacked rows on mobile.
- Streaming Ask and Compare cards progressively render buffered Markdown instead of raw text.
- Whenever a new Ask or Compare turn is submitted, React performs one smooth reveal of that new turn so the submitted question becomes visible even when the user was viewing an older turn.
- Streaming responses do not auto-follow generated text as it grows, and the transcript no longer renders a floating down-arrow jump control.
- React frontend uses the Alabaster Minimal workspace shell: a quiet 272px desktop navigation rail that can collapse to a narrow icon rail, top Ask/Compare tabs with theme-aware high-contrast active and inactive text, prompt starter landing, horizontal compare canvas, unified bottom composer, visually aligned mobile Ask/Compare/History navigation, and light/dark theme tokens switched from the account menu.
- The empty Ask workspace introduces CortexAI as a place for answers, file analysis, content work, and model comparison, then offers four actionable prompts covering debugging, document summaries, writing refinement, and file analysis. Example selection fills the composer without submitting automatically.
- The empty Compare workspace explains the ask-once, multi-model workflow and highlights accuracy, depth, speed, tone, and usefulness as comparison dimensions. Three responsive examples cover system design, debugging, and model review; selection fills the Compare composer without changing selected models or submitting.
- Frontend model selectors fall back to a bundled display catalog when `/v1/models` is unavailable, so local UI controls remain usable while backend/session setup is incomplete.
- Compare response cards render as tall equal-height model panels with fixed model headers/actions and independently scrolling readable Markdown bodies.
- The composer keeps active compare models as removable chips and exposes Add Model from the same options row without separating the prompt, attachments, feature controls, or send action into independent boxes.

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
- `DELETE /v1/history?session_id=<optional>`
- `GET /v1/whoami`
- `GET /v1/usage/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`
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
- `POST /v1/auth/logout` (clears the session cookie)

### Cognito (Gmail) sign-in

To enable "Sign in with Google" via Amazon Cognito:

1. **AWS Cognito**: Create a User Pool, add an App client, configure the Cognito domain, and add Google as an identity provider (see [AWS docs](https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-social-idp.html)).
2. **Environment** (see `.env.example`):
   - `COGNITO_USER_POOL_ID` – User pool ID (e.g. `us-east-1_xxxxxxxxx`)
   - `COGNITO_CLIENT_ID` – App client ID
   - `COGNITO_REGION` – AWS region
   - `COGNITO_DOMAIN` – Hosted UI base URL (e.g. `https://your-prefix.auth.us-east-1.amazoncognito.com`)
   - `COGNITO_REDIRECT_URI` – (optional) Callback URL; React falls back to same-origin `/auth`
3. **Frontend**: Load the app; the React top-right account icon opens an account menu. Cognito guests can `Sign in`, the theme switch toggles the React `data-theme` between light and dark and persists the browser preference, and `Log off` remains available as a session-clear fallback even when the icon is labelled `Guest account`. Log off posts to `/v1/auth/logout`, clears the active React session/history state, then redirects to the Cognito `logoutUrl` when the backend provides one. After sign-in, sessions/history are tied to the authenticated user identity.

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
- `/v1/optimize` has an optimize-specific hard deadline from `PROMPT_OPTIMIZER_TIMEOUT_MS` (default `5000`) and explicit-route retry count from `PROMPT_OPTIMIZER_ROUTE_MAX_RETRIES` (default `2`)
- weak or vague prompts are classified locally and get one extra retry if the optimizer returns the original prompt unchanged; strong prompts can keep the original without retry
- optimizer calls use compact generation defaults from `PROMPT_OPTIMIZER_MAX_OUTPUT_TOKENS` (default `450`) and `PROMPT_OPTIMIZER_TEMPERATURE` (default `0.2`), with JSON-object mode for OpenAI chat models
- optimizer route logs include status, fallback reason, prompt-quality class, attempt count, and retry reasons without logging raw prompt text
- request payloads may include optional `context_hint` and compact `context`; the frontend sends recent mixed user/assistant context whenever a thread has prior messages. Attachment file contents are not copied into optimize requests. React caps optimize context to the last ten compact messages and a 4,000-character `context_hint` so follow-up rewrites can resolve ordinal, pronoun, and formatting references like "the second one", "their cadres", or "write it as a table".
- optimizer model output must be valid optimizer JSON and is rejected if it appears to answer the prompt, or if it introduces unresolved placeholders such as `[specific topic]`, instead of rewriting it
- responses include `optimization_status` (`optimized`, `kept_original`, `disabled`, `timeout`, `failed`, `rejected`) plus `fallback_reason`
- if optimization is disabled, times out, fails, is rejected, or keeps the original, the API returns the original prompt with `was_optimized=false`
- when the frontend Improve toggle is enabled, the user bubble always shows the prompt being sent in normal case. Optimization state renders as a right-aligned pill below the bubble: pending shows `Improving your prompt`, optimized shows `Prompt optimized` with `View original`, and kept-original shows `Already clear — sent as-is`. Ask response cards and Compare response tabs, cards, and summary remain hidden while optimization is pending, then appear when optimization resolves and model generation begins; cancelling during optimization leaves the placeholder response UI hidden

For Compare (`/v1/compare`, `/v1/compare/stream`) requests:
- auth must be session-based (`cortex_session` cookie or `Authorization: Bearer`)
- Targets are always explicit (`targets[]`).
- `routing.smart_mode` is ignored by design in compare mode.
- `routing.research_mode=true` is still honored and runs once per compare turn for all selected targets.
- In the browser UI, Ask starts with `Web` enabled by default and Compare starts with `With sources` enabled by default; each keeps a manual off choice for that page session.
- Frontend Compare selectors support per-model removal with compact circular controls attached to each selector. Remove controls show only when three models are active; removing any slot compacts the remaining two models, preserving the API's two-target minimum. Request payloads include only active selected models.
- Frontend Compare response cards hide per-card action label text in side-by-side layouts and keep compact copy/feedback icons; inline citation pills carry source previews, while aggregate tokens, usage, and success counts remain in the summary bar.
- Frontend Compare selectors appear as removable model chips in the unified composer. React prefers `openai:gpt-5.1` and `claude:claude-sonnet-4-5` for the initial two targets, and Add Model prefers `deepseek:deepseek-chat`; unavailable preferences fall back to distinct enabled catalog models. Request payloads include only active selected models.
- React manual Ask and Compare model controls share one accessible picker component with provider logo, readable model-family label, exact API model ID, and active highlighting. Compare adds duplicate-option disabling and removal rules through the shared component API. Hidden native selects remain synchronized for browser automation compatibility.
- Frontend Compare response cards use side-by-side model columns with a packed per-card metric strip for completed duration, tokens, and cost on desktop; mobile exposes the same abbreviated metrics directly in the compact header and phone-sized Compare switches between model responses with the frosted sticky model switcher. Loading cards show live elapsed time plus `Queued`, `Refining prompt`, `Connecting to model`, `Generating response`, or `Finalizing`; completed cards keep that same UI-observed elapsed basis when live timestamps are available, and failed cards show elapsed failure time.

## Web Research Behavior (Current)

- API contract: `routing.research_mode` accepts `true|false` (mapped to `on|off`).
- Internal orchestrator modes:
- `research_mode=off`: hard stop for this turn (no research injection, no reuse).
- `research_mode=auto`: reuse prior research only when intent/topic heuristics match; otherwise search.
- `research_mode=on`: always perform fresh search for the current turn and bypass local research cache.
- When sources are injected, they are treated as primary evidence for current/source-dependent factual claims; non-conflicting model background knowledge can still be used for explanation/context.
- Query sanitization anchors underspecified follow-up searches to the previous user topic when the current prompt omits that topic, so a Compare follow-up like a 1990s film list stays scoped to the active conversation subject.
- If query sanitization yields empty query in `on` mode, orchestrator falls back to the raw prompt.
- Prompt injection includes citation requirements, partial-source fallback guidance, and a UTC retrieval timestamp.
- Tavily search options are resolved by a deterministic local resolver before the API call. It always sends `max_results=5`, `search_depth=advanced`, `chunks_per_source` from `TAVILY_CHUNKS_PER_SOURCE` (default `3`), `include_raw_content=false`, `include_answer=false`, and `auto_parameters=false`.
- When `TAVILY_ENHANCED_SEARCH_ENABLED=true`, the resolver may add Tavily `topic` (`finance` or `news` only), `time_range`, country targeting for non-topic searches, and curated finance domain allowlists. It does not rewrite the query; prompt optimization and existing query sanitization remain separate.
- Tavily country targeting is omitted whenever `topic` is sent because Tavily country filtering applies only to general searches. Finance regional targeting uses curated domains instead, for example `bankofcanada.ca`/`statcan.gc.ca`, `bls.gov`/`bea.gov`/`federalreserve.gov`, `sec.gov`, or `ons.gov.uk`/`bankofengland.co.uk`.
- `TAVILY_ENHANCED_SEARCH_ENABLED=false` is the kill switch for enhanced Tavily options; the call still uses the fixed retrieval params above.
- When provider timestamps are missing, Tavily source timestamps fall back to server UTC ISO timestamps (never `Timestamp: N/A`).
- Tavily runtime diagnostics emit `research.network.diagnostics` with DNS + TCP egress health (host/port configurable via `TAVILY_NETWORK_DIAGNOSTICS_*` envs) for EC2 troubleshooting.
- Tavily failures emit normalized `error_kind` fields (for example `dns_resolution_failed`, `timeout`, `auth_forbidden`, `rate_limited`) without logging raw query text.

## Session Continuity

- Ask and Compare now share the same conversation session when the same `session_id` is reused.
- Switching between Ask and Compare does not require creating a separate thread.
- Compare turns still persist their per-target rows under a shared `request_group_id`, but the user-visible chat session can remain the same across both modes.
- `GET /v1/history` intentionally returns persisted request rows rather than pre-grouped UI threads. Each row includes optional `session_id` and `request_group_id`; clients group sidebar threads by `session_id` and Compare responses by `request_group_id`.
- `DELETE /v1/history?session_id=<id>` clears only that user-visible conversation thread. Omitting `session_id` clears all history for the authenticated identity. React per-thread delete calls `DELETE /v1/history/{entry_id}` for every persisted row in the selected thread.
- The browser UI persists the active thread id as `cortex_active_session_id` and restores that transcript after reload/resume. It does not auto-continue the last active thread after an explicit fresh login: that path marks `cortex_fresh_login_pending`, consumes the `fresh_login=1` callback marker, clears the active thread id, and sends `new_session=true` for the first turn. Users can still reopen older threads from History.

## Chat Context Guardrails

- Conversation history sent to the API is trimmed to the last `10` messages.
- Oversized conversation-history payloads are soft-trimmed server-side instead of rejected.
- The server keeps the newest context first and trims older or oversized message content within the internal context budget before calling providers.

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
- Chat `response_done` payloads include `web_source_items` for rendered citation pills.
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

Usage summary for the Usage & insights screen:
```bash
curl -H "X-API-Key: dev-key-1" \
  "http://127.0.0.1:8000/v1/usage/summary?from=2026-02-01&to=2026-02-22"
```

`GET /v1/usage/summary` defaults to the last 30 inclusive calendar days when no range is provided. It returns the screen contract: period label, total tokens/requests/sessions, average/p95/min latency, average cost/request, total spend, token delta versus the previous equal-length period, Smart-routed totals, per-provider/model reply rows, Ask/Compare/Mixed session counts, and a zero-padded 14-day token activity series ending at `period.to`.
The React Usage & insights screen uses the same period-scoped summary query; its period selector refetches the full dashboard and its Export button downloads day-grouped CSV rows from `/v1/usage/export` for the loaded period. On phone layouts it preserves the same backend-driven values in shortened labels and a compact model/session presentation.

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

    def usage_summary(self, from_date: str, to_date: str):
        r = requests.get(
            f"{self.base_url}/v1/usage/summary",
            params={"from": from_date, "to": to_date},
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

Legacy static frontend artifact (static files + manifest + zip):
```bash
python scripts/build_frontend_artifact.py
```

React static frontend build:
```bash
npm ci --prefix frontend-react
npm run --prefix frontend-react build
```

Optional React artifact zip/manifest after building:
```bash
python scripts/build_frontend_artifact.py --source-dir frontend-react/dist --output-dir dist/frontend-react
```

API runtime image:
```bash
docker build -f Dockerfile.api -t cortexai-api:dev .
```

Standalone React/nginx image:
```bash
docker build -f Dockerfile.frontend -t cortexai-frontend:dev .
```

Production deployment notes:
- `Dockerfile.api` is API-only and does not copy `frontend-react/dist`; if the API image should serve React directly, include the built `frontend-react/dist` directory in that runtime image and set `FRONTEND_DIR` to its absolute path.
- `Dockerfile.frontend` builds and serves React static assets with nginx. Put it behind a reverse proxy or update nginx/CDN routing so `/v1/*`, `/auth`, and `/runtime-config.js` reach the FastAPI service.
- Keep `APP_ENV`, `ENVIRONMENT`, or `ENV` set to `prod`/`production` in production-like deployments so browser dev-session login is forced off.

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

Run the frontend-only responsive suites independently:
```bash
npm run --prefix e2e test:mobile
npm run --prefix e2e test:desktop-ipad
```
These responsive suites start their own Vite server and use mocked frontend API contracts, so they do not require PostgreSQL, provider keys, or the live E2E environment. Mobile coverage exercises 320px and 390px phone behavior; the desktop/iPad suite covers desktop plus iPad portrait and landscape layouts.

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
  Dockerfile.frontend
  nginx.conf
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
    llm-response.css
    llm-response.js
    runtime-config.example.js
    style.css
    smart-routing-state.js
    layout-smoke.test.mjs
    provider-discovery.e2e.test.mjs
    smart-routing-state.test.mjs

  frontend-react/
    index.html
    package.json
    package-lock.json
    vite.config.ts
    src/
      main.tsx
      App.tsx
      components/
      hooks/
      api/
      store/

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
      tavily_resolver.py
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
    test_tavily_resolver.py
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

Last updated: 2026-05-23
