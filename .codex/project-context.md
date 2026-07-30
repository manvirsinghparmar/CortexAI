# OpenAIProject Context Pack

## Project Snapshot

- Product: CortexAI B2B LLM gateway (API + React frontend + CLI tooling).
- Backend stack: FastAPI + SQLAlchemy/repository pattern + PostgreSQL.
- Orchestration: provider abstraction with smart routing/fallback across OpenAI, Gemini, DeepSeek, Grok, and Claude.
- Frontend stack: React/Vite app in `frontend-react/`.
- E2E stack: Playwright tests in `e2e/`.

## Runtime Commands

```bash
python run_app.py
python run_server.py --reload
npm ci --prefix frontend-react
npm run --prefix frontend-react build
```

## Core Invariants

- `DATABASE_URL` is required for startup and should point to PostgreSQL.
- Most `/v1/*` endpoints accept API key, Cognito bearer, or session cookie auth.
- Session-scoped routes (`/v1/chat*`, `/v1/compare*`, including Cortex Analysis, `/v1/files/*`, `/v1/providers`, `/v1/models`, `/v1/optimize`, `/v1/history*`) reject API-key-only auth.
- Local dev can mint session cookies via `POST /v1/auth/dev-login` only when `ENABLE_DEV_SESSION_LOGIN=true` (blocked in production-like envs).
- Reverse-proxy handling defaults to `ENABLE_PROXY_HEADERS=true` with `TRUSTED_PROXY_IPS=*`. Narrow the trusted proxy list when the API is directly reachable, or disable proxy-header handling when no trusted upstream proxy is present.
- Production Cognito deployments should set `COGNITO_REDIRECT_URI` to the exact registered HTTPS callback. Automatic callback and frontend API-base derivation depend on the effective request scheme supplied through trusted proxy headers.
- Session cookies default to a seven-day lifetime (`SESSION_MAX_AGE_SECONDS=604800`); `0` restores browser-session behavior. `SESSION_COOKIE_SECURE` is an explicit override, otherwise the `Secure` attribute follows the effective HTTPS request scheme.
- Cognito JWKS and token requests verify TLS certificates by default (`COGNITO_SSL_VERIFY=true`). Disabling verification is limited to controlled local troubleshooting or trusted TLS-inspection environments.
- Frontend startup waits for Cognito/local dev-session bootstrap before session-scoped startup fetches. Signed-out Cognito users see a `Sign in to use CortexAI` workspace gate and React does not call `/v1/providers`, `/v1/models`, or `/v1/history` until a session exists; authenticated and local dev-session users hydrate Ask/Compare model selectors and the history sidebar, then restore the browser-persisted active `session_id` transcript when the page reloads/remounts.
- React account actions live in the top-right account icon menu as a secondary sign-in path. Keep the persisted light/dark theme switch available there, and keep `Log off` available as a session-clear fallback even when the icon is labelled `Guest account`; it clears the API session cookie, resets active React chat/history state, and redirects to the Cognito Hosted UI logout URL when `/v1/auth/cognito-config` provides one.
- In monolith mode (`SERVE_FRONTEND=true`), `GET /runtime-config.js` is generated at runtime and sent with no-cache headers.
- Browser lifecycle diagnostics post non-sensitive metadata to unauthenticated `POST /v1/client-diagnostics`; backend logs them as `frontend.diagnostic` for reload/discard/bfcache/long-task/error triage.
- `run_app.py` is the local full-app runner: it starts FastAPI with `SERVE_FRONTEND=false`, launches the React/Vite dev server, and passes `CORTEX_API_PROXY_TARGET` / `FRONTEND_RUNTIME_API_BASE` so Vite and runtime config point to the selected API host/port. Its loopback-only `--subscription-plan free|plus|pro|unrestricted` option provides IntelliJ-friendly local entitlement profiles; `unrestricted` removes subscription allowances only and preserves authentication, provider, file-safety, and production guards.
- The full-app runner preflights both ports before starting children and must terminate full process trees on Windows so failed startup cannot orphan Vite.
- `FRONTEND_DIR` explicitly selects the compiled static frontend directory. When unset, FastAPI uses `frontend-react/dist`.
- React dependencies belong in `frontend-react/package.json` and `frontend-react/package-lock.json`, never in Python `requirements.txt`.
- Ask and Compare support shared session continuity via `session_id`.
- History persistence remains row-oriented: React groups sidebar threads by `session_id` and reconstructs multi-model Compare turns by `request_group_id` when restoring a session. Compare regeneration appends an immutable response revision under the original logical response root; history presents only its latest revision. Thread labels use an explicit renamed `session_title` when available, but must ignore the system-generated `API Chat` / `API Compare` placeholders and fall back to the first persisted prompt.
- React desktop and mobile history rows show each thread's latest activity timestamp using Today/Yesterday/calendar-date formatting.
- Desktop history rows expose a hover/focus context menu containing only Rename and Delete; Rename persists `sessions.title` through `PATCH /v1/history/session/{session_id}`, while Delete uses the short in-row confirmation and removes each persisted request row in the selected thread. Mobile keeps its existing inline delete affordance. `DELETE /v1/history?session_id=<id>` clears only that session, while omitting `session_id` clears all history for the authenticated identity.
- Expanded desktop sidebar history is the `Recent` list: Today/Yesterday/month-day groups with single-line 36px rows containing a compact 11.5px ellipsized title and narrowed `MODE · time` caption that swaps to the context-menu trigger on hover/focus. Do not add a leading mode glyph; preserve at least 140px for title text at the 280px expanded width. Keep model names, turn counts, and token counts hidden, preserve the full title in the row tooltip, and support arrow navigation plus Enter/R/D/Escape. Leave the collapsed 76px desktop rail and separate mobile History layout unchanged. Ask, Compare, Usage, and Models live in the desktop rail; the bottom-left session tile is status-only for active sessions and must not trigger logout; the mobile bottom navigation remains Ask/Compare/History only while Usage and Models are reached from the account menu.
- Explicit browser fresh sign-in starts a new chat session instead of restoring the previously active thread; page refresh, Chrome tab resume/reload, same-browser reauth, and explicit History thread selection still preserve continuity for the selected session. React uses `cortex_active_session_id` for active-thread persistence and consumes `cortex_fresh_login_pending` plus `fresh_login=1` only for intentional fresh-login resets.
- Conversation-history guardrails are active, but oversized history is soft-trimmed instead of rejected.
- Compare targets are explicit; smart routing flags are ignored in compare mode by design.
- Consumer plans are server-owned in `config/subscription_plans.yaml` and must validate at API startup. The only monthly usage meter is `ai_credits`: Free/Plus/Pro receive 100,000/1,000,000/3,000,000 credits. Model access categories (`economical`, `standard`, `advanced`, `premium`) are distinct from smart-routing tiers (`T0`-`T3`), and every registry model must explicitly declare its category, input/output credit multipliers, usage label, and pricing version. `server/billing/subscription_service.py` is the only effective-plan lifecycle authority and falls back conservatively to Free; `server/billing/entitlement_service.py` owns feature/model/file decisions and exact reservation quantities; `server/billing/metering_service.py` owns atomic reserve/settle/release/expiry transitions; `server/billing/enforcement_service.py` composes those services for DB-mode Ask/Compare/Optimize/Cortex Analysis. Routes reserve a conservative estimate before provider work, settle actual successful input/output credits, add the fixed 15,000-credit research charge only when retrieval ran, release unused estimates/failures, and partially settle Compare. Upload/storage is free; file context is accounted through the consuming model call. Smart routing reserves the worst allowed candidate and settles the selected model without changing its independent tier. `credit_transactions` is the immutable itemized reconciliation ledger exposed by `GET /v1/credits/transactions`. `BILLING_ENABLED=false` still resolves every account to Free, and verified Stripe webhooks remain authoritative for paid state.
- Stripe hosted billing sessions keep credentials, paid-plan Price IDs, redirects, provider payloads, signature verification, and response validation in `server/billing/stripe_gateway.py`. `server/billing/session_service.py` separates hosted-session provider calls from short DB transactions, atomically claims Customer identity, and sends provider-live accounts to Portal instead of duplicate Checkout. `server/billing/webhook_service.py` persists verified provider events before row-locked processing, handles required Checkout/subscription/invoice lifecycle events, reverse-maps server-owned Prices, rejects stale snapshots, preserves same-period usage counters, applies grace/cancellation through `subscription_service.py`, and provides internal reconciliation. Strict request schemas reject client Price/amount/currency/Customer/redirect fields. `BILLING_ENABLED=false` returns `billing_not_configured`; hosted-session creation never grants paid access, and verified Stripe webhook state is authoritative. Do not expose reconciliation over HTTP until administrator authorization exists.
- React subscription state is in-memory and auth-aware: `frontend-react/src/api/billing.ts` and `api/entitlements.ts` own transport, `subscription/subscriptionErrors.ts` owns typed safe errors, and `hooks/useSubscription.ts` loads authenticated state only after auth bootstrap. Checkout-return query state is a polling hint, never paid authority; only webhook-synchronized `/v1/entitlements` may confirm a paid plan. Signed-out users may fetch the public display-safe plan catalogue but must not call current-subscription or entitlement endpoints. React follows only validated backend-returned HTTPS hosted URLs and never calls Stripe directly or stores billing authority in browser storage.
- React plan management lives at `/pricing` and `/account/billing`, using the shared responsive subscription shell and summary-only account-menu plan context. `GET /v1/billing/plans.billing_enabled` is the only public hosted-billing availability signal; it is boolean and display-safe. Pricing and Billing must render lifecycle and allowance state from `useSubscription`, keep paid plan switching in Portal, and never promote a Checkout return to paid access before webhook-synchronized entitlements confirm it.
- React subscription locks are explanatory UX, never billing authority. Model access joins static display IDs to live `/v1/models.billing_class`; missing metadata fails conservatively. Compare target count, Web, Improve, attachment count/size, uploaded bytes, and monthly counters come from live plan/entitlement contracts. Structured subscription denials open the shared accessible dialog, preserve the current composer draft and attachments until a stream is accepted, and never hide restored premium history after downgrade.
- Cortex Analysis is user-triggered only after two or three successful Compare responses. It defaults to `gpt-5.4-mini`, anonymizes and shuffles response identity before generation, restores every user-visible `Response A/B/C` reference to its provider display name after generation, validates strict structured output, and appends each successful run to `cortex_analysis_runs`. Every run must survive reload and History reopening; regenerating a source response keeps older analyses readable but stale. During an analysis re-run, show only the processing state and temporarily hide the saved result; restore the saved result if the re-run fails. Both analysis endpoints must preflight the migration schema and return `503 cortex_analysis_schema_unavailable` before provider work when it is absent or incomplete. Do not add subscription, tier, credit, trial, upgrade, auto-run, or Cortex-only mobile-tab behavior without an explicit product decision.
- Compare web research is prepared once per compare turn and shared across selected targets; underspecified follow-up search queries should anchor to the previous user topic before retrieval.
- Frontend Compare selectors keep at least two active models, prefer `openai:gpt-5.1` and `claude:claude-sonnet-4-5`, prefer `deepseek:deepseek-chat` for Add Model, preserve valid manual selections, and fall back to distinct enabled catalog models when a preference is unavailable. With three active models, removing any slot compacts the remaining two instead of allowing the default resolver to refill the removed slot.
- React manual Ask and Compare controls share `ModelPicker`, an accessible listbox with provider logo, readable family label, exact model ID, and selected-state styling. Compare supplies duplicate-option disabling and removal behavior. Keep the synchronized hidden native selects because the E2E harness uses `#singleModel` and `#compareModel1..3` for option enumeration, `inputValue`, and `selectOption`.
- The styled model picker keeps the custom accessible listbox on desktop and mobile. Its fixed-position menu renders through a body portal so narrow Compare overflow containers cannot clip touch selection; synchronized hidden native selects remain available only for automation compatibility.
- React frontend assistant responses use `frontend-react/src/components/results/` with progressive Ask/Compare stream rendering, visible copy-success confirmation, inline publisher-name citation pills from `web_source_items`, code-block copy controls, GFM table rendering, sanitized provider errors, and no active auto-follow or floating down-arrow jump control during streaming. Response tables use contained horizontal scrolling on desktop and header-labelled stacked rows on mobile.
- Chat and Compare streaming may emit `heartbeat` NDJSON events while provider work is pending. React ignores these visually; they exist to keep intermediaries from treating long provider calls as idle response bodies and are logged through stream lifecycle telemetry.
- React response headers resolve labels and provider logos through `config/modelPresentation.ts` and the shared `components/shared/ProviderLogo` renderer used by `ModelPicker`; do not add response-only provider mappings.
- The React Usage & insights route uses backend-driven values on desktop and mobile. Phone layouts shorten the visible title and KPI labels, keep the accessible heading as `Usage & insights`, show the Smart-pick leaderboard strip and session-mode bar, and retain the Ask/Compare/History footer navigation with mobile account-menu entry.
- Empty streaming responses use a per-card `ResponseLoadingState`. Each card removes its own loading block on first text/error, so faster Compare targets do not wait for slower targets; shimmer and pulse animations must remain disabled under `prefers-reduced-motion`.
- Smart Ask pending response headers remain model-neutral because the stream `start` provider/model is only a pre-runtime preview. Show `Smart routing` while pending and use the authoritative provider/model from `response_done`.
- Appending a new Ask or Compare turn always performs one smooth reveal of the submitted question, including when the user was viewing an older turn. Response-card regeneration refills the clicked response card in place, preserving the original turn's source-enabled flag so source-backed regenerations issue a fresh backend research/search request. Regeneration targets only the clicked response model, including for cards that came from a Compare turn, and streams through the chat endpoint without adding a new UI card. Subsequent response growth does not continue moving the viewport.
- React response sources render inline as citation pills. On desktop, hovering a pill opens a popover listing each grouped source link and leaving the hover area closes it. On phone-sized mobile, tapping a pill still opens the bottom sheet. The pill's external-link icon opens the first cited source directly.
- React Compare keeps every selected response visible in a responsive grid without horizontal response scrolling on desktop and tablet widths: three columns on wide desktop, two at tablet widths, and stacked tall cards at the app's tablet/mobile shell breakpoint. Phone-sized mobile uses a segmented model switcher, shows one selected response card at a time in natural page flow, and elevates the stuck switcher into a frosted provider-tinted bar.
- Compare transcripts reserve bottom breathing room above the persistent composer so the input area does not compress the reading workspace. Desktop/tablet Compare cards keep fixed headers/footers and independently scrolling response bodies; phone-sized mobile uses normal page scrolling for the active response card. Ask turns remain content-sized.
- React Ask and Compare share the same right-aligned user-message bubble, including attachment and optimization states. Optimization status renders as a right-aligned pill below the bubble so the prompt body keeps normal case and full wrapping. Compare keeps aggregate totals in a separate compact row, shows friendly model labels beside exact API model IDs, and uses compact icon actions.
- Mobile and desktop response cards show completed per-model duration, token, and cost metadata directly in the header without a run-details chevron; fastest/cheapest labels are desktop-only while the success tint remains visible on mobile. Pending and failed response cards keep their muted elapsed/status line visible on mobile and desktop. Response-card duration uses the same UI-observed elapsed timing when live timestamps are available, falls back to API `latency_ms` for restored rows, and keeps unavailable token counts hidden instead of rendering zero-token placeholders.
- Latest completed Ask response cards may show deterministic suggested follow-up chips extracted from clear assistant-offered options, one concrete follow-up offer, or a quoted follow-up query. The row is owned by `ResponseCard`, appears below markdown and above response actions, submits chip text through the normal chat stream path, skips Improve optimization, and is not shared with Compare cards or composer feature chips.
- React Ask and Compare share one rounded composer shell: model options sit above a borderless textarea that starts at one line and auto-grows to a bounded height, attachment chips grow upward inside the shell, and compact feature controls plus the fixed-size send action share the bottom row. Compare model chips are separated by decorative opposing-arrows connectors; desktop uses a subtle bordered medallion while mobile uses a narrow borderless glyph. Mode selection stays in the main navigation, while mobile compare chips scroll horizontally when needed and the answer-screen follow-up composer rests as a docked context pill above the fixed bottom navigation until tapped open. Mobile answer transcripts reserve bottom scroll clearance so response copy, regenerate, and feedback actions stay reachable above the dock. The shared model picker renders its fixed-position listbox through a body portal so horizontally scrollable mobile Compare rows cannot clip it.
- Keep the React composer shell visually borderless: use a transparent structural border to avoid layout shift, soft idle/focus elevation, and no textarea browser outline on desktop or mobile.
- Mobile starts new sessions through one persistent square-pen action in the header. It cancels active generation, clears the current thread, returns from History to chat, and preserves Ask/Compare mode; do not duplicate New chat inside mobile History.
- Shared React feature chips keep Smart, Web/With sources, and Improve guidance in accessible `role="tooltip"` elements. Ask starts with Web enabled and Compare starts with With sources enabled for new page sessions, while preserving manual off choices. Reveal tooltips on hover and keyboard focus; on touch input, one tap toggles the chip and shows its tooltip for two seconds. Keep tooltip bounds inside narrow mobile viewports.
- React attachment upload uses raw-byte `POST /v1/files/upload`, polls `GET /v1/files/{file_id}` while files process, and sends attachment IDs on Ask/Compare requests.
- Tavily research uses a deterministic local search-options resolver before provider calls. The resolver fixes retrieval params, may add topic/time/country/domain options when enabled, never rewrites the query, and can be reduced to fixed params with `TAVILY_ENHANCED_SEARCH_ENABLED=false`.
- Frontend follows the Alabaster Minimal shell: a quiet 272px desktop navigation rail that can collapse to a narrow icon rail, subtle mode and current-session states, top Ask/Compare tabs, prompt starter landing, horizontal compare canvas, unified composer with active model chips, visually aligned mobile Ask/Compare/History navigation, and token-backed light/dark themes switched from the account menu.
- The React Ask empty state uses product-focused workspace copy and four responsive task examples for debugging, document summaries, writing refinement, and file analysis. Selecting an example only fills the prompt; it must not auto-submit.
- The React Compare empty state uses the same hero system with Compare-specific workflow copy and three responsive examples for system design, debugging, and multi-model review. Selecting an example only fills the prompt and must preserve the current Compare mode and model selections.
- Frontend-only development falls back to a bundled display model catalog when `/v1/models` is unavailable; bootstrap history failures should not set the primary chat error banner.
- The React Models route (`/models`) keeps its task-first static display catalog in `frontend-react/src/config/models.data.json` and `modelsCatalog.ts`, but joins each ID to live `/v1/models` billing metadata for access presentation. It does not replace API model discovery or grant model access; if production display ownership moves to the gateway, preserve the same JSON shape and replace the static import with an API loader.
- Prompt optimization for the UI goes through explicit `POST /v1/optimize`; chat/compare auto-optimization is off by default and requires `ENABLE_ORCHESTRATOR_PROMPT_OPTIMIZATION=true`.
- Explicit UI prompt optimization is latency-bounded (`PROMPT_OPTIMIZER_TIMEOUT_MS`, default 5000 ms), defaults to two route-level attempts, retries unchanged output once for locally classified weak prompts, rejects answer-like or unresolved-placeholder optimizer output, and sends compact mixed user/assistant context whenever the active thread has prior messages. Attachment file contents are not copied into optimize requests. React caps optimize context to the last ten mixed messages and a 4,000-character `context_hint`; the backend prefers structured `context.conversation_history` over the flat hint when building the optimizer prompt. The Improve pending state uses one stable live status pill below the user bubble, respects reduced motion, and reveals optimized or kept-original status without replacing the prompt body with status text.

## High-Value Paths

- API routes: `server/routes/`
- API schemas: `server/schemas/`
- Effective subscription endpoint: `server/routes/entitlements.py`; display-safe plan/current-subscription routes: `server/routes/billing.py`; lifecycle/decision services: `server/billing/`
- Orchestration: `orchestrator/`
- Provider clients: `api/`
- Persistence and reporting: `server/persistence.py`, `server/usage_reporting.py`, `server/savings.py`, `db/`
- Config single sources:
  - `config/providers.yaml`
  - `config/model_registry.yaml`
  - `config/subscription_plans.yaml`
  - `config/pricing.py`

## Change-Impact Map

- New endpoint: route + schema + router wiring + tests + README API section.
- Provider/catalog changes: `api/`, `api/client_registry.py`, `config/providers.yaml`, provider discovery tests.
- Subscription-plan, lifecycle, entitlement, or billing-class changes: `config/subscription_plans.yaml`, `server/billing/`, `server/routes/entitlements.py`, `server/routes/whoami.py`, `config/model_registry.yaml`, `orchestrator/model_registry.py`, matching schemas/docs/Postman, and billing/model contract tests.
- Routing behavior changes: `orchestrator/prompt_analyzer.py`, `tier_decider.py`, `model_selector.py`, `smart_router.py`.
- DB changes: add SQL migration under `db/migrations/`, then reflect in tables/repository usage.
- Billing repository and metering-service functions do not commit. Their callers own transaction boundaries. Reservation creation locks the billing account to serialize account-scoped idempotency keys, then locks counters in deterministic meter-key order; settlement, release, and stale expiry lock the reservation before its counters. Never hold these transactions open across provider calls.
- Ask/Compare billing reservation IDs include a server-generated suffix even when the client supplies `X-Request-ID`, preventing a replayed correlation ID from reusing a terminal reservation for a new provider call.
- `/v1/entitlements` and DB-mode `/v1/whoami` use committing units of work because effective resolution may lazily create a billing account and current usage period. `plan_tier` is compatibility-only; new consumers use the entitlement snapshot and `billing.plan_code`.
- Frontend behavior changes: `frontend-react/` plus React tests/build and `e2e/` contract checks as needed.
- React subscription-data changes: keep server contract calls in `frontend-react/src/api/billing.ts` and `api/entitlements.ts`, auth-aware state/polling in `hooks/useSubscription.ts`, typed errors in `subscription/subscriptionErrors.ts`, and matching tests/docs. Never introduce a browser-side plan authority.

## Validation Matrix

- Unit/regression baseline:
  - `python -m pytest -q`
- Release gate:
  - `python scripts/release_gate.py`
- Pricing/registry consistency:
  - `python -m pytest tests/test_registry_pricing_alignment.py -q`
- CI changed-file quality gates:
  - Ruff/MyPy run on added or modified Python files; deleted paths are excluded before tooling runs. Black is advisory until a formatting baseline lands.
  - Gitleaks scans the checked-out tree with the pinned CLI rather than repository history.
- Frontend local checks (when UI touched):
  - `npm run --prefix frontend-react build` when React UI is touched
  - `npm run --prefix frontend-react test` when React component logic/tests are touched
- Full browser E2E:
  - `npm run --prefix e2e test`
- Frontend-only responsive browser suites:
  - `npm run --prefix e2e test:mobile`
  - `npm run --prefix e2e test:desktop-ipad`
  - These suites start isolated Vite servers and mock frontend API contracts; they do not require PostgreSQL or live provider credentials.

## Delivery Defaults

- Keep handlers thin and move logic into service modules.
- Preserve backward compatibility for public API contracts unless migration is explicitly requested.
- Update docs for behavior changes:
  - `README.md`
  - `docs/postman/CortexAI_B2B.postman_collection.json`
  - runbooks/ADRs when architecture decisions change.
