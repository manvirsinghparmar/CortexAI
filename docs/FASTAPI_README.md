# FastAPI Integration

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```
`requirements.txt` includes `tavily-python` for research-enabled Ask/Compare flows and a compatible Stripe 15.3 minor range for hosted billing sessions. FastAPI excludes `0.136.3` because `pip-audit` currently flags that release with advisory `MAL-2026-4750`.

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
# Optional stream keep-alive interval; set 0 to disable heartbeat events
# STREAM_HEARTBEAT_INTERVAL_SECONDS=15
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
- React startup waits for Cognito/local dev-session bootstrap before fetching session-scoped model and history data. Signed-out Cognito users see a workspace sign-in gate instead of the Ask/Compare composer, while authenticated and local dev-session users restore the persisted active `session_id` transcript when the page was reloaded, resumed, or silently reauthenticated in the same browser.
- React Ask/Compare turns send `context.session_id`, bounded `conversation_history`, and `new_session` to preserve selected-thread continuity while allowing explicit New Chat resets.
- The React sidebar uses a compact navigation rail with subtle mode/current-session states plus Usage and Models destinations. Desktop has an icon-only top-right control that collapses the sidebar to a narrow action rail and expands it back to the full history view; mobile remains on the separate Ask/Compare/History bottom navigation, with Usage and Models reached from the account menu. The expanded desktop `Recent` list groups chats by Today, Yesterday, and month/day, with one 36px row per session: compact 11.5px ellipsized title and a narrowed `MODE · time` caption, with no leading mode glyph, to preserve substantially more identifying title text. Hover/focus replaces the caption with a Rename/Delete menu; renamed titles persist in `sessions.title`, Delete retains the short in-row confirmation, and keyboard rows support arrows, Enter, R, D, and Escape. The collapsed desktop rail and the separate mobile History surface remain unchanged.
- Selecting a React history row reloads the complete session transcript. Ask rows are restored chronologically and Compare target rows are grouped into one turn by `request_group_id`.
- Explicit frontend fresh sign-in starts an empty new chat session; browser refreshes, Chrome tab reload/resume, same-browser reauth, and explicit History selections continue the selected thread.
- React posts non-sensitive lifecycle diagnostics to `/v1/client-diagnostics`; backend logs them as `frontend.diagnostic` events so production refresh reports can be separated into reload/navigation, tab discard, back/forward cache restore, long main-thread task, or frontend error cases.
- React attachment UX uses raw-byte `POST /v1/files/upload`, polls `GET /v1/files/{file_id}` for processing uploads, and sends uploaded file IDs on Ask/Compare requests. In DB mode, upload reserves the server-observed body size against the plan's `uploaded_bytes` allowance before storage, then settles successful uploads or releases validation/storage failures. Ask/Compare enforce plan file count and per-file size and settle one `file_analysis_turns` unit per billable attachment-backed action, not per file or Compare target.
- React Ask defaults `Web` on for new page sessions, React Compare defaults `With sources` on, and users can turn either off for the current page session. Compare streams `/v1/compare/stream` events into per-model response columns.
- React Compare keeps every selected response visible in a responsive grid without horizontal response scrolling on desktop and tablet widths: three columns on wide desktop, two at tablet widths, and stacked tall cards at the app's tablet/mobile shell breakpoint. Phone-sized mobile uses a segmented model switcher, shows one selected response card at a time in natural page flow, and elevates the stuck switcher into a frosted provider-tinted bar without changing model-pill horizontal positions.
- Model headers and action footers remain fixed inside each desktop/tablet Compare card while only the answer body scrolls. The transcript reserves bottom breathing room above the persistent composer so the input area does not compress the reading workspace.
- React Compare uses the same right-aligned user-message bubble as Ask mode and keeps aggregate totals in a separate compact row. Model cards show a friendly model name with the exact API model ID, use compact icon actions, and reserve most of the column height for response content.
- React Ask and Compare use one rounded composer shell with a borderless textarea that starts at one line and auto-grows to a bounded height, attachment chips above a compact action row, routing controls, and a fixed-size send action. Mode changes use the app navigation; the composer does not duplicate the Ask/Compare switch. Compare model selectors remain in a compact options row above the textarea and scroll horizontally on narrow screens when needed.
- The React composer shell keeps a transparent structural border to prevent layout movement and uses soft elevation rather than a visible rectangular outline. Textarea focus suppresses the browser outline and increases the shell shadow on desktop and mobile.
- The empty React Ask workspace explains the product value across answers, file analysis, content generation, and model comparison. Its four responsive example actions populate the composer for debugging, summarization, writing refinement, and file-analysis tasks without triggering a request.
- The empty React Compare workspace explains that one prompt can be reviewed across multiple selected models and frames accuracy, depth, speed, tone, and usefulness as practical comparison dimensions. Its three responsive examples populate the composer without changing model selections or triggering a request.
- On mobile answer screens, the follow-up composer rests as a docked pill above the fixed Ask/Compare/History navigation. Tapping the pill opens the bottom-sheet composer, focuses its textarea, and places the cursor at the end of any draft so typing can begin without a second tap. Attachment chips grow upward without narrowing the textarea or displacing the send action. Answer transcripts reserve enough bottom scroll clearance for response copy, regenerate, and feedback actions to remain reachable above the dock.
- Mobile uses a persistent square-pen header action to start a new session from Ask, Compare, or History. The action cancels active generation, clears the current thread, returns to chat, and preserves the selected mode; the History panel does not render a separate New chat button.
- Frontend Compare selectors keep at least two active models and send only active selected models in compare requests. React prefers `openai:gpt-5.1` plus `claude:claude-sonnet-4-5` initially, and Add Model prefers `deepseek:deepseek-chat`; disabled or missing preferences fall back to distinct enabled catalog models. Remove controls appear with three active models and compact whichever two remain after any slot is removed.
- React manual Ask and Compare controls render through the same accessible model picker with provider logos, readable model labels, exact model IDs, and active-state highlighting. The listbox uses a viewport-positioned body portal so mobile Compare's horizontally scrollable model row cannot clip it. Compare supplies duplicate-selection prevention and removal behavior; synchronized hidden native selects preserve existing Playwright selectors and `selectOption` flows.
- Frontend Compare response cards use restrained model headings, compact Markdown paragraph/list spacing, compact footers, and a packed mono metric strip for completed duration, tokens, and cost; aggregate tokens, usage, and success counts remain in the summary bar.
- React composer feature chips provide legacy-compatible explanatory tooltips for Smart, Web/With sources, and Improve in Ask and Compare. Enabled chips use a theme-aware high-contrast fill, label, and accent ring so their state remains clear in light and dark themes. Compare's With sources and Improve controls use the same background, border, label, and shadow treatment whenever they share the same toggle state. The descriptions are associated through `aria-describedby`, open on hover or keyboard focus, and remain viewport-contained on mobile. A touch tap toggles the chip and keeps its tooltip visible for two seconds.
- React desktop top mode navigation keeps the active and inactive Ask/Compare labels legible in both light and dark themes, with a theme-accent underline identifying the selected mode independently of the sidebar navigation.
- Mobile and desktop completed response-card duration, token, and cost metadata appears directly in the header without a run-details chevron. Loading and failed cards keep a muted elapsed/status line visible on mobile and desktop. The frontend displays the same UI-observed elapsed duration with abbreviated units when live timestamps are available, falls back to API `latency_ms` for restored rows, and keeps unavailable token counts hidden instead of rendering zero-token placeholders.
- React response headers reuse the model picker's shared provider-logo and model-presentation resolver, including the provider-initial fallback when an image is unavailable.
- React exposes `/models` for a task-first model selection guide. The screen is currently driven by `frontend-react/src/config/models.data.json`, not `/v1/models`: editing a provider's `models[]` changes the visible catalog, while `tier`, `speed`, and `rec` derive the Depth meter, Speed meter, and recommended row/callout. If this metadata becomes production-owned by the gateway, the frontend should keep the same JSON contract and swap the static import for an API-backed loader.
- `config/subscription_plans.yaml` is the server-owned Free/Plus/Pro plan catalogue. `server/billing/plan_catalog.py` validates and caches it during API startup, including ranks, prices, Stripe price environment-variable mappings, entitlements, allowances, limits, and allowed billing classes.
- `db/billing_repository.py` provides transaction-neutral access to billing accounts, provider subscription snapshots, usage periods/counters/reservations, and webhook idempotency records created by `db/migrations/20260718_add_b2c_billing_foundation.sql`.
- `server/billing/account_service.py` validates user ownership and lazily creates B2C accounts. `server/billing/subscription_service.py` applies the server-side lifecycle/grace policy and creates the effective usage period. `server/billing/entitlement_service.py` returns feature/model/file decisions and exact reservation quantities without mutating counters.
- `server/billing/metering_service.py` owns atomic allowance mutation. It locks the billing owner for idempotency-key creation, locks required counters in deterministic order, rejects over-limit reservations before mutation, settles only successful quantities, releases unused quantities, and expires clearly stale reservations after a default 30-minute threshold. Every function uses the caller-owned transaction and never commits.
- `server/billing/enforcement_service.py` composes effective-plan resolution, entitlement evaluation, atomic reservation, and output-aware settlement/release for DB-mode Ask, Compare, Optimize, upload, and attachment analysis. `server/persistence.py` owns the short committing units of work; no billing transaction remains open during a provider, optimizer, or object-storage call.
- `BILLING_ENABLED=false` resolves all users to Free, keeps Stripe lazy, and makes Checkout, Portal, and webhook routes return `503 billing_not_configured`. `DEV_SUBSCRIPTION_PLAN` works only when billing is disabled and the runtime is explicitly local/development.
- With billing enabled, startup validates the secret key, webhook signing secret, paid-plan Price IDs, server redirect URLs, and optional API version. The API rejects client-supplied Price IDs, amounts, currencies, Customer IDs, and redirects. `server/billing/webhook_service.py` makes verified Stripe Checkout/subscription/invoice state authoritative, locks provider-event retries, rejects stale snapshots, preserves usage counters across same-period changes, and delegates paid/grace/cancellation access to `subscription_service.py`.
- `/v1/chat`, `/v1/chat/stream`, `/v1/compare`, and `/v1/compare/stream` reserve model, research, and attachment-analysis quantities before provider execution. They settle only successful model responses by actual billing class, settle one file-analysis turn when an attachment-backed request produces billable output, release failed targets, and settle research once only when it ran. Compare performs aggregate partial settlement. `/v1/optimize` meters one actual explicit optimizer invocation without recounting the later Ask/Compare submission. `/v1/files/upload` enforces file access/size and uploaded-byte allowances before storage and releases failed uploads. Usage-export enforcement remains later work.
- Focused validation: `python -m pytest tests/test_billing_metering.py tests/test_billing_entitlements.py tests/test_stripe_billing.py tests/test_stripe_webhooks.py tests/test_baseline_safety_rails.py tests/test_fastapi_contract_and_guardrails.py -q`. Use `BILLING_TEST_DATABASE_URL` with `tests/test_billing_postgres_integration.py` for real row-lock concurrency coverage.
- `/v1/models` exposes `billing_class` as `standard`, `advanced`, or `ultra`. This value is independent from the existing smart-routing `tier`; missing legacy classifications use the conservative `advanced` fallback and emit a warning.
- Pending Ask and Compare cards show independent contextual loading blocks with a subtle sparkle and skeleton lines. A card removes its loading state on its first streamed token or error without waiting for the other Compare targets.
- Smart Ask pending cards remain model-neutral because the `start` provider/model is a routing preview that can differ after research and runtime context are applied. They show `Smart routing` while waiting and adopt the authoritative provider/model from `response_done`.
- Frontend response card controls render as a minimal icon row for copy, regenerate, and feedback actions. Copy shows a brief visible success confirmation in the toolbar. Regenerate uses the existing `/v1/chat/stream` path, refills the clicked response card in place, and preserves the original source-enabled flag. Compare card regeneration is intentionally single-target so clicking one card does not rerun or replace the other comparison cards.
- Frontend response sources render inline as publisher-name citation pills derived from `web_source_items`; grouped markers such as `[1][2][3]` collapse into one pill with a preview card listing each linked source. Desktop keeps the hover preview viewport-contained and directly beside its pill, while phone-sized mobile keeps the tap-to-open bottom sheet.
- Frontend response Markdown keeps explicit ordered-list numbering when numbered items are split by explanatory text.
- React response Markdown renders inline citation pills with tap/click source previews, blockquote callout styling, styled code blocks with copy controls, GFM tables, and sanitized provider error states. Desktop tables scroll within the response card, while mobile tables stack cells under their column labels.
- Frontend streaming responses render buffered Markdown progressively for Ask and Compare.
- Submitting a new Ask or Compare turn always performs one smooth reveal of the new turn, including when the user was viewing an older turn.
- Frontend streaming responses do not auto-follow generated text as it grows, and the transcript no longer renders a floating down-arrow jump control.

## Endpoints

- `GET /health`
- `GET /health/runtime`
- `GET /runtime-config.js`
- `GET /v1/providers`
- `GET /v1/models?provider=<optional>&enabled_only=true|false`
- `POST /v1/files/upload`
- `GET /v1/files/{file_id}`
- `POST /v1/client-diagnostics`
- `POST /v1/chat`
- `POST /v1/chat/stream`
- `POST /v1/compare`
- `POST /v1/compare/stream`
- `POST /v1/optimize`
- `GET /v1/history`
- `PATCH /v1/history/session/{session_id}`
- `DELETE /v1/history/{entry_id}`
- `DELETE /v1/history?session_id=<optional>`
- `GET /v1/whoami`
- `GET /v1/entitlements`
- `POST /v1/billing/checkout-session`
- `POST /v1/billing/portal-session`
- `POST /v1/billing/webhook`
- `GET /v1/usage/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`
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
- `session_title` is optional; user-authored values replace the first prompt as the thread label. React ignores the system-generated `API Chat` and `API Compare` placeholders.
- `request_group_id` is optional and is populated for Compare target rows.
- One Ask turn produces one row.
- One Compare turn produces one row per target model; all target rows from that turn share the same `request_group_id`.
- The React client groups sidebar items by `session_id`, reconstructs Compare turns by `request_group_id` when a thread is selected, and persists the active thread id as `cortex_active_session_id` so startup can restore the same transcript after a browser refresh/remount.
- `PATCH /v1/history/session/{session_id}` accepts `{"title":"..."}` to rename one user-owned session. The title is trimmed, limited to 120 characters, and persisted without changing latest-activity ordering.
- `DELETE /v1/history?session_id=<id>` clears only that session's persisted request rows for the authenticated identity; omitting `session_id` clears all history. React per-thread delete uses `DELETE /v1/history/{entry_id}` for each row in the selected thread.

### Usage summary contract

`GET /v1/usage/summary?from=<YYYY-MM-DD>&to=<YYYY-MM-DD>` returns the aggregate contract for the Usage & insights screen. If both dates are omitted, the period defaults to the last 30 inclusive calendar days.

- Request, token, spend, latency, and model reply totals are aggregated from `llm_requests` joined to `llm_responses`.
- `smartRoutedTotal` and per-model `viaSmart` count routing rows whose `routing_mode` is `smart`, `cheap`, or `strong`; missing/explicit/legacy routing rows count as manual.
- `sessionModes` is classified from `llm_requests.route_mode` per `session_id` within the period: Ask only, Compare only, or Mixed. The `sessions.mode` creation value is not used.
- `tokensDeltaPct` compares the selected period with the immediately preceding equal-length period. It returns `0` when both periods have zero tokens and `100` when the current period has tokens but the previous period is zero.
- `activityDaily` always contains 14 entries ending at `period.to`, zero-filled for days without usage.

## Authentication

Protected `/v1/*` endpoints accept any one of:
- `cortex_session` cookie
- `Authorization: Bearer <gateway-bearer-token>`
- `X-API-Key: <key-from-API_KEYS>`

Invalid or missing credentials return `401`.

### Effective subscription and entitlements

`GET /v1/entitlements` uses API-key, Cognito bearer, or signed-session authentication. It commits lazy account/usage-period creation and returns all seven allowance counters with `used`, `reserved`, `limit`, and nonnegative `remaining` values. Free periods are UTC calendar months; paid periods use stored provider boundaries.

Effective lifecycle rules are server-side and conservative:

- `trialing` and `active`: paid plan for a valid current stored period
- `past_due`: paid plan only through `grace_until`; otherwise Free
- `canceled`: paid plan only when `cancel_at_period_end=true` and the stored period has not ended
- `unpaid`, `incomplete`, `incomplete_expired`, `paused`, expired cancellation, unknown status, or unknown plan: Free

The endpoint returns `plan`, `features`, `model_access`, `allowances`, and `period` sections and never exposes provider subscription IDs, Stripe price IDs, customer IDs, amounts, or secrets. `/v1/whoami.plan_tier` remains a compatibility display field populated from the effective plan in database mode; new integrations should use `/v1/entitlements` plus `/v1/whoami.billing.plan_code`.

### Stripe hosted billing sessions

The hosted Checkout and Portal routes require signed-session or Cognito bearer identity; API-key-only authentication returns `403 session_auth_required`. The webhook route uses Stripe signature verification instead of user authentication.

`GET /v1/billing/plans` is public and returns only display-safe catalogue fields: USD monthly price, Plus recommendation state, model billing classes, feature availability, core allowances, and boolean `billing_enabled`. The availability flag supports a truthful disabled Checkout state without exposing or probing configuration. Price IDs, configured environment-variable names, Customers, secrets, and provider objects are omitted.

`GET /v1/billing/subscription` requires signed-session or Cognito identity and database mode. It returns the effective plan code/status, provider label, current period, cancellation state, and `can_manage` without exposing a provider subscription ID. Its effective state comes from `subscription_service.py`, so disabled billing and unsafe lifecycle states still resolve conservatively.

`POST /v1/billing/checkout-session` accepts the strict body `{"plan_code":"plus","billing_period":"monthly"}`. The server validates that the plan exists and is paid, resolves its Price ID from `config/subscription_plans.yaml` plus environment, creates/reuses the account Customer, and returns:

```json
{"checkout_url":"https://checkout.stripe.com/...","destination":"checkout"}
```

An existing provider-live subscription is not duplicated. The same endpoint creates a Portal session and returns its hosted URL with `destination: "portal"`. The browser still follows only the returned short-lived URL and never selects the Customer or redirect target.

`POST /v1/billing/portal-session` accepts no body or `{}` and returns `{"portal_url":"https://billing.stripe.com/..."}` for the persisted Customer. Missing Customer state returns `409 stripe_customer_required`; normalized Stripe errors return `502 billing_provider_unavailable`. Hosted URLs are never persisted, and neither hosted-session endpoint grants paid access.

`POST /v1/billing/webhook` has no user-auth dependency. It reads the raw request bytes, verifies `Stripe-Signature` with `STRIPE_WEBHOOK_SECRET`, rejects invalid signatures with structured `400`, and caps the body at 1 MiB. Valid events are hashed and persisted by Stripe event ID before processing. Unknown valid event types are marked ignored; processed/ignored duplicates return `200`; failed events retain a safe failure code and are retried under a row lock. Required handlers cover `checkout.session.completed`, `customer.subscription.created|updated|deleted`, `invoice.paid`, and `invoice.payment_failed`. The response is always `{"received":true}` after successful or duplicate handling and never exposes Stripe objects or identifiers.

Checkout and invoice handlers retrieve the current Subscription; subscription handlers consume the signed snapshot and compare its event creation time with `last_provider_event_at`. Price IDs are reverse-mapped only through server configuration. Paid periods use the existing `(billing_account_id, starts_at)` identity, so duplicate renewal events cannot reset counters; same-period plan/end changes preserve the row and counters. Payment failure sets grace only when the retrieved Subscription remains `past_due`, and deletion resolves through the existing lifecycle policy to Free without deleting history. The internal `reconcile_billing_account()` helper refreshes an account from Stripe, but no HTTP reconciliation endpoint is exposed because the repository does not yet provide administrator authorization.

Subscription environment controls:

```ini
BILLING_ENABLED=false
SUBSCRIPTION_PAYMENT_GRACE_DAYS=3
STRIPE_SECRET_KEY=
STRIPE_WEBHOOK_SECRET=
STRIPE_PLUS_MONTHLY_PRICE_ID=
STRIPE_PRO_MONTHLY_PRICE_ID=
STRIPE_CHECKOUT_SUCCESS_URL=https://app.example.com/account/billing?checkout=success
STRIPE_CHECKOUT_CANCEL_URL=https://app.example.com/pricing?checkout=cancelled
STRIPE_PORTAL_RETURN_URL=https://app.example.com/account/billing
# STRIPE_API_VERSION=  # optional
# DEV_SUBSCRIPTION_PLAN=pro  # local/dev only; never production
```

See `docs/runbooks/stripe-billing.md` for the enablement checklist. Do not place Stripe secrets in frontend runtime configuration or commit them.

React consumes these contracts through `frontend-react/src/api/billing.ts`, `frontend-react/src/api/entitlements.ts`, and the auth-aware `useSubscription` hook. Signed-out hooks call only the public plans endpoint. Checkout-success polling remains bounded and considers payment confirmed only after `/v1/entitlements` reports a paid effective plan; browser storage and the return query string are never plan authority.

React exposes `/pricing` for the public Free/Plus/Pro catalogue and `/account/billing` for authenticated plan status, lifecycle notices, allowance progress, and Portal management. Billing-disabled, Free, active paid, past-due, cancel-at-period-end, fully cancelled, and delayed Checkout-confirmation states render from these server contracts. Account-menu plan context stays summary-only.

Session-scoped endpoints are session-scoped:
- `/v1/chat*`
- `/v1/compare*`
- `/v1/files/*`
- `/v1/providers`
- `/v1/models`
- `/v1/optimize`
- `/v1/history*`
- `/v1/billing/*`
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
- Frontend startup completes Cognito/local dev-session bootstrap before calling session-scoped startup endpoints (`/v1/providers`, `/v1/models`, `/v1/history`). If Cognito is enabled and no user session is present, React shows a sign-in gate instead of calling those endpoints; authenticated and local dev-session users still hydrate Ask/Compare selectors and the history sidebar immediately.
- The React workspace shows a `Sign in to use CortexAI` gate for signed-out Cognito users, and the top-right account icon remains a secondary menu with Cognito `Sign in` when available, a persisted light/dark theme switch, and `Log off` as a session-clear fallback, including when the icon is still labelled `Guest account`. Log off clears the local session cookie through `/v1/auth/logout`, resets the active React chat/history state, then follows the Cognito Hosted UI `logoutUrl` when available.
- Response is sent with no-cache headers so config changes apply immediately.

React/Vite frontend notes:
- Build output lives in `frontend-react/dist` after `npm run --prefix frontend-react build`.
- Local hot-reload development can use `python run_app.py` for the full app, or `npm run --prefix frontend-react dev` plus a separate API process. Vite proxies `/v1`, `/auth`, and `/runtime-config.js` to `http://localhost:8000` by default.
- The React router exposes `/usage` for Usage & insights and `/models` for the task-first model guide. Desktop reaches both from the sidebar; mobile reaches both from the account menu, and Models intentionally has no bottom-tab entry.
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
- The browser UI avoids that fallback on explicit fresh login by marking `cortex_fresh_login_pending`, consuming the backend `fresh_login=1` callback marker, clearing the stored active thread id, and sending `new_session=true` for the first turn after sign-in.

Prompt optimization:
- `POST /v1/optimize` is gated by `ENABLE_PROMPT_OPTIMIZATION=true`.
- `/v1/optimize` is the UI optimization path; chat/compare do not auto-optimize by default.
- In DB mode, the endpoint resolves the server-owned plan, checks prompt-improvement access, and reserves one `optimization_turns` before optimizer setup. Setup failure releases the reservation; any started invocation settles once, including timeout or kept-original/rejected fallback.
- Sending the returned prompt through Ask or Compare does not reserve another optimization turn.
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
- With the frontend Improve toggle enabled, the user bubble always shows the prompt being sent in normal case. Optimization state renders as a right-aligned pill below the bubble: pending shows `Improving your prompt`, optimized shows `Prompt optimized` with `View original`, and kept-original shows `Already clear — sent as-is`. Ask response cards and Compare response tabs, cards, and summary remain hidden while optimization is pending, then appear when optimization resolves and model generation begins; cancelling during optimization leaves the placeholder response UI hidden.

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
- `heartbeat`
- `line`
- `response_done`
- `done`
- `error`

Notes:
- `start` includes the routed preview `provider` and `model`, plus `session_id`, `research_mode`, and an initial `web_source_items` array. Smart-mode clients should not present the preview as the final selected model.
- `response_done` includes the full `ChatResponseDTO`, including `session_id` and `web_source_items`.
- `done` includes the resolved `session_id`.
- `heartbeat` carries elapsed timing while provider work is pending. It keeps
  the HTTP response body active, is ignored by the React UI, and does not call
  provider APIs or consume model tokens.
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
- 2 to 3 targets at the API boundary. Free and Plus allow 2; Pro allows 3.
- Compare always uses explicit targets.
- `routing.smart_mode` is ignored in compare mode by design.
- With `routing.research_mode=true`, research runs once per compare turn and is shared across all selected targets for fairness.
- Browser Ask sends `routing.research_mode=true` by default because the `Web` toggle starts on, and Browser Compare does the same because `With sources` starts on; users can turn either off for the current page session.

Subscription enforcement:
- The effective plan, model billing classes, feature access, and meter quantities are resolved server-side; client-supplied billing identifiers are ignored.
- Entitlement/model denials return structured `403` responses before provider execution. Monthly exhaustion returns `429`; unsafe billing configuration returns a provider-safe `500`.
- Smart Ask receives the plan's allowed billing classes as an independent routing constraint. It conservatively reserves the premium-meter envelope through the highest allowed Smart class, settles only the actual successful class, and releases unused premium reservations. This accommodates the existing reservation schema, which cannot transfer units between premium meter keys.
- Streaming reservations are created before the `StreamingResponse` is returned. Ask settles a successful model after its first meaningful output is emitted, releases model units on a pre-output disconnect, and still settles performed research once. Compare finalizes aggregate successful targets before `done`, or settles only partial targets whose output started on disconnect/error.

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
- `heartbeat`
- `response_start`
- `line`
- `response_done`
- `done`
- `error`

Notes:
- `start` includes `session_id`, `research_mode`, and target count.
- Each `response_done` includes one full `ChatResponseDTO`.
- Final `done` includes the aggregate compare payload with both `request_group_id` and `session_id`.
- `heartbeat` may appear while Compare targets are pending and has the same
  keep-alive semantics as chat streaming.
- Server logs emit `compare.stream.*` lifecycle events from inside the response body generator, including per-target provider-call progress and terminal stream reason.

## Schema Migrations

Apply these when enabling updated persistence flows:

```bash
psql "$DATABASE_URL" -f db/migrations/20260218_llm_requests_api_key_owner_guard.sql
psql "$DATABASE_URL" -f db/migrations/20260218_add_request_group_id_to_llm_requests.sql
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260718_add_b2c_billing_foundation.sql
```

No new DB migration is required for shared Ask/Compare session continuity; that behavior is currently implemented in persistence/session resolution logic.

The B2C billing migration is additive and leaves `users`, sessions, messages, `llm_requests`, and `llm_responses` unchanged. Apply it before deploying code that uses the billing repository. See `docs/runbooks/db-migrations.md` for verification and rollback guidance.

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
- Browser lifecycle diagnostics are accepted by unauthenticated `POST /v1/client-diagnostics` and logged as `frontend.diagnostic` with sanitized metadata only; prompts, responses, attachment contents, and auth secrets are not sent.
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

Run mocked Stripe billing tests (no Stripe network calls):
```bash
pytest tests/test_stripe_billing.py tests/test_billing_repository.py -q
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

Last updated: 2026-07-19
