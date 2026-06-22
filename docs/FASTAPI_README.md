# FastAPI Integration

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```
`requirements.txt` already includes `tavily-python` for research-enabled Ask/Compare flows. FastAPI excludes `0.136.3` because `pip-audit` currently flags that release with advisory `MAL-2026-4750`.

React UI dependencies live in `frontend-react/package.json` and `frontend-react/package-lock.json`; they are not Python requirements:
```bash
npm ci --prefix frontend-react
```
Use Node.js 20.x for the React/Vite toolchain.

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
REACT_FRONTEND=false
# Optional frontend runtime-config override for clients that honor apiBase
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
# PROMPT_OPTIMIZER_TIMEOUT_MS=5000
# PROMPT_OPTIMIZER_ROUTE_MAX_RETRIES=2
# PROMPT_OPTIMIZER_MAX_OUTPUT_TOKENS=450
# PROMPT_OPTIMIZER_TEMPERATURE=0.2
# Optional Tavily search-option resolver
# TAVILY_ENHANCED_SEARCH_ENABLED=true
# TAVILY_CHUNKS_PER_SOURCE=3
# TAVILY_ENHANCED_SEARCH_DOMAIN_RULES=true
```

5. Start the full local app:
```bash
python run_app.py
```

This starts FastAPI on `http://127.0.0.1:8000` and the React/Vite frontend on `http://127.0.0.1:5173`. The runner starts the API with `SERVE_FRONTEND=false`, launches `npm run --prefix frontend-react dev`, and sets Vite's proxy target plus `FRONTEND_RUNTIME_API_BASE` from the selected API host/port.

For local browser session bootstrap, keep `ENABLE_DEV_SESSION_LOGIN=true` in `.env` or run:
```bash
python run_app.py --enable-dev-login
```

Start only the FastAPI server:
```bash
python run_server.py --reload
```

To serve the React/Vite frontend through FastAPI, build it and point `FRONTEND_DIR` to the built output:
```powershell
npm ci --prefix frontend-react
npm run --prefix frontend-react build
$env:FRONTEND_DIR=(Resolve-Path .\frontend-react\dist).Path
python run_server.py --reload
```

`FRONTEND_DIR` is explicit and takes precedence. If `FRONTEND_DIR` is unset, `REACT_FRONTEND=true` makes `server/app.py` serve `frontend-react/dist` instead of the legacy `frontend/` directory.

6. Open docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Frontend composer keyboard UX: `Enter` sends prompt, `Shift+Enter` inserts newline.
- React startup waits for Cognito/local dev-session bootstrap before fetching session-scoped model and history data.
- React Ask/Compare turns send `context.session_id`, bounded `conversation_history`, and `new_session` to preserve selected-thread continuity while allowing explicit New Chat resets.
- The React sidebar uses a compact navigation rail with subtle mode/current-session states. Desktop has an icon-only top-right control that collapses the sidebar to a narrow action rail and expands it back to the full history view; mobile remains on the separate top and bottom navigation. Desktop History shows one two-line borderless row per session: a single-line title plus mode and the latest activity date. Model names, turn counts, and token counts stay hidden; long titles truncate visually while remaining available through the row tooltip and thread-wide search is unchanged.
- Selecting a React history row reloads the complete session transcript. Ask rows are restored chronologically and Compare target rows are grouped into one turn by `request_group_id`.
- Frontend fresh sign-in starts an empty new chat session; browser refreshes within the same signed-in session and explicit History selections still continue the selected thread.
- React attachment UX uses raw-byte `POST /v1/files/upload`, polls `GET /v1/files/{file_id}` for processing uploads, and sends uploaded file IDs on Ask/Compare requests.
- React Ask defaults `Web` on for new page sessions, React Compare defaults `With sources` on, and users can turn either off for the current page session. Compare streams `/v1/compare/stream` events into per-model response columns.
- React Compare keeps every selected response visible in a responsive grid without horizontal response scrolling on desktop and tablet widths: three columns on wide desktop, two at tablet widths, and stacked tall cards at the app's tablet/mobile shell breakpoint. Phone-sized mobile uses a segmented model switcher and shows one selected response card at a time in natural page flow.
- Model headers and action footers remain fixed inside each desktop/tablet Compare card while only the answer body scrolls. The transcript reserves bottom breathing room above the persistent composer so the input area does not compress the reading workspace.
- React Compare uses the same right-aligned user-message bubble as Ask mode and keeps aggregate totals in a separate compact row. Model cards show a friendly model name with the exact API model ID, use compact icon actions, and reserve most of the column height for response content.
- React Ask and Compare use one rounded composer shell with a borderless textarea that starts at one line and auto-grows to a bounded height, attachment chips above a compact action row, routing controls, and a fixed-size send action. Mode changes use the app navigation; the composer does not duplicate the Ask/Compare switch. Compare model selectors remain in a compact options row above the textarea and scroll horizontally on narrow screens when needed.
- The React composer shell keeps a transparent structural border to prevent layout movement and uses soft elevation rather than a visible rectangular outline. Textarea focus suppresses the browser outline and increases the shell shadow on desktop and mobile.
- The empty React Ask workspace explains the product value across answers, file analysis, content generation, and model comparison. Its four responsive example actions populate the composer for debugging, summarization, writing refinement, and file-analysis tasks without triggering a request.
- The empty React Compare workspace explains that one prompt can be reviewed across multiple selected models and frames accuracy, depth, speed, tone, and usefulness as practical comparison dimensions. Its three responsive examples populate the composer without changing model selections or triggering a request.
- On mobile, attachment chips grow the composer upward without narrowing the textarea or displacing the send action, and the composer remains above the fixed Ask/Compare/History navigation.
- Mobile uses a persistent square-pen header action to start a new session from Ask, Compare, or History. The action cancels active generation, clears the current thread, returns to chat, and preserves the selected mode; the History panel does not render a separate New chat button.
- Frontend Compare selectors keep at least two active models and send only active selected models in compare requests. React prefers `openai:gpt-5.1` plus `claude:claude-sonnet-4-5` initially, and Add Model prefers `deepseek:deepseek-chat`; disabled or missing preferences fall back to distinct enabled catalog models. Remove controls appear with three active models and compact whichever two remain after any slot is removed.
- React manual Ask and Compare controls render through the same accessible model picker with provider logos, readable model labels, exact model IDs, and active-state highlighting. The listbox uses a viewport-positioned body portal so mobile Compare's horizontally scrollable model row cannot clip it. Compare supplies duplicate-selection prevention and removal behavior; synchronized hidden native selects preserve existing Playwright selectors and `selectOption` flows.
- Frontend Compare response cards use restrained model headings, compact Markdown paragraph/list spacing, compact footers, and a packed mono metric strip for completed duration, tokens, and cost; aggregate tokens, usage, and success counts remain in the summary bar.
- React composer feature chips provide legacy-compatible explanatory tooltips for Smart, Web/With sources, and Improve in Ask and Compare. The descriptions are associated through `aria-describedby`, open on hover or keyboard focus, and remain viewport-contained on mobile. A touch tap toggles the chip and keeps its tooltip visible for two seconds.
- Mobile completed response-card duration, token, and cost metadata starts collapsed behind an icon-only chevron beside the capability badge. Expanding it reveals the same packed metric strip within the header; desktop completed metadata remains visible. Loading and failed cards keep a muted elapsed/status line visible on mobile and desktop. The frontend displays the same UI-observed elapsed duration with abbreviated units when live timestamps are available, falls back to API `latency_ms` for restored rows, and keeps unavailable token counts hidden instead of rendering zero-token placeholders.
- React response headers reuse the model picker's shared provider-logo and model-presentation resolver, including the provider-initial fallback when an image is unavailable.
- Pending Ask and Compare cards show independent contextual loading blocks with a subtle sparkle and skeleton lines. A card removes its loading state on its first streamed token or error without waiting for the other Compare targets.
- Smart Ask pending cards remain model-neutral because the `start` provider/model is a routing preview that can differ after research and runtime context are applied. They show `Smart routing` while waiting and adopt the authoritative provider/model from `response_done`.
- Frontend response card controls render as a minimal icon row for copy, regenerate, and feedback actions. Regenerate uses the existing `/v1/chat/stream` path, refills the clicked response card in place, and preserves the original source-enabled flag. Compare card regeneration is intentionally single-target so clicking one card does not rerun or replace the other comparison cards.
- Frontend response sources render inline as publisher-name citation pills derived from `web_source_items`; grouped markers such as `[1][2][3]` collapse into one pill with a preview card listing each linked source. Desktop opens and closes the preview from hover, while phone-sized mobile keeps the tap-to-open bottom sheet.
- Frontend response Markdown keeps explicit ordered-list numbering when numbered items are split by explanatory text.
- React response Markdown renders inline citation pills with tap/click source previews, blockquote callout styling, styled code blocks with copy controls, GFM tables, and sanitized provider error states. Desktop tables scroll within the response card, while mobile tables stack cells under their column labels.
- Frontend streaming responses render buffered Markdown progressively for Ask and Compare.
- Submitting a new Ask or Compare turn always performs one smooth reveal of the new turn, including when the user was viewing an older turn.
- Frontend streaming responses do not auto-follow generated text as it grows; when the newest content is below the current viewport, `Jump to latest` provides explicit navigation.

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
- `GET /v1/auth/cognito-config`
- `POST /v1/auth/dev-login`
- `POST /v1/auth/logout`

### History response contract

`GET /v1/history?limit=<n>&session_id=<optional>` returns persisted request rows, newest first. It does not pre-group records for presentation.

- `session_id` identifies the user-visible conversation thread.
- `request_group_id` is optional and is populated for Compare target rows.
- One Ask turn produces one row.
- One Compare turn produces one row per target model; all target rows from that turn share the same `request_group_id`.
- The React client groups sidebar items by `session_id`, then reconstructs Compare turns by `request_group_id` when a thread is selected.

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
- Frontend startup completes Cognito/local dev-session bootstrap before calling session-scoped startup endpoints (`/v1/providers`, `/v1/models`, `/v1/history`) so Ask/Compare selectors and the history sidebar hydrate immediately in local development.
- The React top-right account icon opens a menu with Cognito `Sign in` when available, a persisted light/dark theme switch, and `Log off` as a session-clear fallback, including when the icon is still labelled `Guest account`. Log off clears the local session cookie through `/v1/auth/logout`, resets the active React chat/history state, then follows the Cognito Hosted UI `logoutUrl` when available.
- Response is sent with no-cache headers so config changes apply immediately.

React/Vite frontend notes:
- Build output lives in `frontend-react/dist` after `npm run --prefix frontend-react build`.
- Local hot-reload development can use `python run_app.py` for the full app, or `npm run --prefix frontend-react dev` plus a separate API process. Vite proxies `/v1`, `/auth`, and `/runtime-config.js` to `http://localhost:8000` by default.
- `run_app.py` sets `CORTEX_API_PROXY_TARGET` for Vite and `FRONTEND_RUNTIME_API_BASE` for runtime config so custom API host/port flags stay aligned with the frontend proxy.
- `run_app.py` checks both requested ports before starting either child process. On Windows it terminates each full child process tree, preventing npm/Vite descendants from remaining bound after partial startup failure or `Ctrl+C`.
- Standalone production hosting must provide `/runtime-config.js` at the React origin and route `/v1/*` plus `/auth` to the FastAPI service. The current React client uses same-origin relative API paths, so split-origin deployments need a reverse proxy/CDN/nginx rule for those paths.
- `Dockerfile.frontend` builds the React app and serves static assets with nginx. `Dockerfile.api` is API-only; it does not include `frontend-react/dist` unless the deployment image is extended to copy those files.

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
- The browser UI avoids that fallback on fresh login by generating a new `session_id` and sending `new_session=true` for the first turn after sign-in.

Prompt optimization:
- `POST /v1/optimize` is gated by `ENABLE_PROMPT_OPTIMIZATION=true`.
- `/v1/optimize` is the UI optimization path; chat/compare do not auto-optimize by default.
- Set `ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=true` only when chat/compare should automatically rewrite prompts without the explicit optimize endpoint.
- `PROMPT_OPTIMIZER_MODEL` must match the configured `PROMPT_OPTIMIZER_PROVIDER`.
- `/v1/optimize` uses `PROMPT_OPTIMIZER_TIMEOUT_MS` (default `5000`) as its hard deadline and `PROMPT_OPTIMIZER_ROUTE_MAX_RETRIES` (default `2`) for explicit-route attempts.
- Weak or vague prompts are classified locally and get one extra retry if the optimizer returns the original prompt unchanged; strong prompts can keep the original without retry.
- Optimizer calls use compact generation defaults from `PROMPT_OPTIMIZER_MAX_OUTPUT_TOKENS` (default `450`) and `PROMPT_OPTIMIZER_TEMPERATURE` (default `0.2`), with JSON-object mode for OpenAI chat models.
- Optimizer route logs include status, fallback reason, prompt-quality class, attempt count, and retry reasons without logging raw prompt text.
- Request payloads may include optional `context_hint` and compact `context`; the frontend sends recent mixed user/assistant context whenever a thread has prior messages. Attachment file contents are not copied into optimize requests. React caps optimize context to ten compact messages and a 4,000-character `context_hint` so ordinal, pronoun, and formatting references like "the second one", "their cadres", or "write it as a table" can be resolved in longer chats.
- Optimizer output is parsed as schema-constrained JSON and rejected when it appears to answer the prompt, or when it introduces unresolved placeholders such as `[specific topic]`, instead of rewriting it.
- Responses include `optimization_status` (`optimized`, `kept_original`, `disabled`, `timeout`, `failed`, `rejected`) and `fallback_reason`.
- Rejected, timed out, failed, kept-original, or disabled optimization returns the original prompt with `was_optimized=false`.
- With the frontend Improve toggle enabled, the user bubble always shows the prompt being sent in normal case. Optimization state renders as a right-aligned pill below the bubble: pending shows `Improving your prompt`, optimized shows `Prompt optimized` with `View original`, and kept-original shows `Already clear — sent as-is`.

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
- `start` includes the routed preview `provider` and `model`, plus `session_id`, `research_mode`, and an initial `web_source_items` array. Smart-mode clients should not present the preview as the final selected model.
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
- Browser Ask sends `routing.research_mode=true` by default because the `Web` toggle starts on, and Browser Compare does the same because `With sources` starts on; users can turn either off for the current page session.

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
- Query sanitization anchors underspecified follow-up searches to the previous user topic when the current prompt omits that topic.
- Tavily search calls use a deterministic local resolver with fixed retrieval params: `max_results=5`, `search_depth=advanced`, `chunks_per_source=1..3` (default `3`), `include_raw_content=false`, `include_answer=false`, and `auto_parameters=false`.
- With `TAVILY_ENHANCED_SEARCH_ENABLED=true`, the resolver may add Tavily `topic` for `finance`/`news`, a bounded `time_range`, country targeting only when no topic is sent, and curated finance domain allowlists for Canada, US, US SEC filings, and UK economic queries.
- The resolver does not rewrite queries. Prompt optimization and query sanitization remain separate layers before the Tavily client receives its query string.
- Set `TAVILY_ENHANCED_SEARCH_ENABLED=false` to disable topic/time/country/domain enrichment while keeping the fixed retrieval params.

## Guardrails

Applied in `server/utils.py`:
- Conversation history trimmed to last 10 messages.
- Oversized conversation-history payloads are soft-trimmed server-side instead of rejected; the newest context is retained first and older or oversized message content is trimmed before provider calls.
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
- Tavily search-option resolver logs include category, topic/time/country decisions, domain-rule metadata, returned source-content lengths, and API credits used.
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

Run React frontend build validation:
```bash
npm ci --prefix frontend-react
npm run --prefix frontend-react build
```

Run persistence guardrail tests:
```bash
pytest tests/test_api_persistence_guardrails.py -v
```

Run compare orchestrator tests:
```bash
pytest tests/test_multi_compare_mode.py -v
```

Run React responsive browser tests without a backend or database:
```bash
npm run --prefix e2e test:mobile
npm run --prefix e2e test:desktop-ipad
```
The suites start isolated Vite servers and mock frontend API contracts. Mobile tests cover phone navigation, composer clearance and growth, attachments, Compare model controls, history restoration, and stacked response cards. Desktop/iPad tests cover the desktop shell, iPad breakpoint behavior, model selection, and independent Compare response scrolling.

---

Last updated: 2026-05-23
