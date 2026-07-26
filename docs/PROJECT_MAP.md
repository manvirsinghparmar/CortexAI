# CortexAI Project Map

This map is the quick "where do I change X?" reference for the current API-first CortexAI codebase.

## Runtime Entrypoints

- Full local app runner and guarded Free/Plus/Pro/unrestricted IntelliJ profiles: `run_app.py`; effective local profile construction: `server/billing/subscription_service.py`
- API server: `run_server.py`
- Main FastAPI app wiring: `server/app.py`
- Frontend runtime config renderer: `server/frontend_runtime_config.py` (`GET /runtime-config.js`)
- Browser lifecycle diagnostics ingestion: `server/routes/client_diagnostics.py` (`POST /v1/client-diagnostics`)
- Browser E2E harness bootstrap: `e2e/server/run_e2e_server.py`

## API Contracts

- Routes: `server/routes/`
- Request/response DTOs: `server/schemas/`
- Error mapping and route guardrails: `server/utils.py`

## Orchestration and Routing

- Core orchestration path: `orchestrator/core.py`
- Smart routing planner: `orchestrator/smart_router.py`
- Tier selection: `orchestrator/tier_decider.py`
- Candidate ranking: `orchestrator/model_selector.py`
- Fallback decisions: `orchestrator/fallback_manager.py`
- Web research intent/query sanitization and Tavily search options: `tools/web/`

## Provider Clients

- Client registry: `api/client_registry.py`
- Base contract: `api/base_client.py`
- Providers:
  - `api/openai_client.py`
  - `api/google_gemini_client.py`
  - `api/deepseek_client.py`
  - `api/grok_client.py`
  - `api/claude_client.py`

## Config Sources of Truth

- Provider catalog and defaults: `config/providers.yaml`
- Smart-router model tiers and metadata: `config/model_registry.yaml`
- Consumer subscription plans: `config/subscription_plans.yaml`
- Immutable plan types, validation, and cache: `server/billing/models.py`, `server/billing/plan_catalog.py`
- Effective account/subscription lifecycle and entitlement decisions: `server/billing/account_service.py`, `server/billing/subscription_service.py`, `server/billing/entitlement_service.py`, `server/billing/errors.py`
- Ask/Compare/Optimize/upload authorization, conservative Smart premium-envelope reservation, and actual-success finalization: `server/billing/enforcement_service.py`; committing route adapters: `server/persistence.py`; request integration: `server/routes/chat.py`, `server/routes/compare.py`, `server/routes/optimize.py`, `server/routes/files.py`
- Atomic allowance reservation lifecycle: `server/billing/metering_service.py`; transaction-neutral locks and counter mutations: `db/billing_repository.py`
- Public effective-plan snapshot: `server/routes/entitlements.py` (`GET /v1/entitlements`); compatibility fields: `server/routes/whoami.py`
- Server-owned Stripe config and API adapter: `server/billing/stripe_gateway.py`; Customer/Checkout/Portal orchestration: `server/billing/session_service.py`; verified event lifecycle/reconciliation: `server/billing/webhook_service.py`; public plans, effective subscription, hosted-session, and webhook endpoints: `server/routes/billing.py`
- React subscription transport, access presentation, and in-memory authority boundary: `frontend-react/src/api/billing.ts`, `frontend-react/src/api/entitlements.ts`, `frontend-react/src/hooks/useSubscription.ts`, `frontend-react/src/subscription/subscriptionErrors.ts`, `frontend-react/src/subscription/subscriptionAccess.ts`; contract/denial tests: `frontend-react/src/__tests__/subscriptionDataLayer.test.tsx`, `subscriptionDenialDraft.test.tsx`
- React consumer plan management: route wiring in `frontend-react/src/App.tsx`; public catalogue in `frontend-react/src/pages/PricingPage.tsx`; authenticated lifecycle/allowance view in `frontend-react/src/pages/BillingPage.tsx`; shared responsive account shell in `frontend-react/src/components/subscription/SubscriptionPageShell.tsx`; backend-plan-to-menu mapping in `frontend-react/src/subscription/accountMenuPresentation.ts`; summary navigation in `frontend-react/src/components/layout/AccountMenu.tsx` across Chat, Models, Usage, Pricing, and Billing; state/route tests in `frontend-react/src/__tests__/subscriptionPages.test.tsx`, `accountMenuPresentation.test.ts`, and `subscriptionRoutes.test.tsx`
- React entitlement UX: reusable dialog/badge/allowance/banner components in `frontend-react/src/components/subscription/`; model/Compare/Web/Improve/file controls in `frontend-react/src/components/composer/`; draft-safe backend denial handling in `frontend-react/src/hooks/useChat.ts` and `store/chatStore.ts`; static-to-live model-class join in `frontend-react/src/pages/ModelsPage.tsx`; Usage allowance panel in `frontend-react/src/pages/UsageInsightsPage.tsx`; behavior/accessibility/mobile coverage in `frontend-react/src/__tests__/subscriptionGating.test.tsx`
- Cost tables: `config/pricing.py`

## Persistence and Reporting

- SQLAlchemy table reflection and repository access: `db/`
- B2C billing persistence and transaction-neutral repository operations: `db/migrations/20260718_add_b2c_billing_foundation.sql`, `db/billing_repository.py`, `db/tables.py`
- Billing constraint/lifecycle/entitlement/metering/Stripe-session/webhook/route coverage and opt-in PostgreSQL concurrency coverage: `tests/test_billing_repository.py`, `tests/test_billing_entitlements.py`, `tests/test_billing_metering.py`, `tests/test_stripe_billing.py`, `tests/test_stripe_webhooks.py`, `tests/test_baseline_safety_rails.py`, `tests/test_fastapi_contract_and_guardrails.py`, `tests/test_files_routes.py`, `tests/test_billing_postgres_integration.py`
- Persistence service: `server/persistence.py`
- Usage reporting: `server/usage_reporting.py`
- Savings reporting: `server/savings.py`
- DB migrations: `db/migrations/`

## Frontend and Browser Tests

- Static frontend shell and behavior: `frontend/index.html`, `frontend/app.js`, `frontend/style.css`
- Response rendering enhancement assets: `frontend/llm-response.js`, `frontend/llm-response.css`
- Static-only hosting config example: `frontend/runtime-config.example.js`
- Legacy static frontend: `frontend/` (`runtime-config.example.js` for static-only hosting)
- React/Vite frontend: `frontend-react/`
  - Runtime deps: `frontend-react/package.json` + `frontend-react/package-lock.json`
  - App entry: `frontend-react/src/main.tsx`, `frontend-react/src/App.tsx`
  - Browser boot/reload diagnostics: `frontend-react/src/diagnostics/bootDiagnostics.ts`
  - API hooks/client: `frontend-react/src/api/`, `frontend-react/src/hooks/`
  - Shared visual primitives: `frontend-react/src/components/common/`
  - Task-first Models destination, static display catalogue, and live billing-class access join: `frontend-react/src/pages/ModelsPage.tsx`, `frontend-react/src/pages/ModelsPage.module.css`, `frontend-react/src/config/models.data.json`, `frontend-react/src/config/modelsCatalog.ts`, `frontend-react/src/hooks/useModels.ts`
  - React prompt optimization request shaping and UI fallback state: `frontend-react/src/optimization/promptOptimization.ts`
  - Compare model preference resolution: `frontend-react/src/config/compareDefaults.ts`
  - Shared manual Ask/Compare model picker: `frontend-react/src/components/composer/ModelPicker.tsx`
  - Model display labels and provider logo metadata: `frontend-react/src/config/modelPresentation.ts`
  - History thread grouping, persisted session rename, per-thread delete, and Compare-turn reconstruction: `server/routes/history.py`, `db/repository.py`, `frontend-react/src/api/history.ts`, `frontend-react/src/history/historyThreads.ts`, `frontend-react/src/hooks/useHistory.ts`, `frontend-react/src/components/layout/Sidebar.tsx`, `frontend-react/src/pages/ChatPage.tsx`
  - Usage & insights route, states, KPI row, mobile compact dashboard, model leaderboard/provider-logo tiles, session modes panel, activity chart, period selector/export, and data layer: `frontend-react/src/pages/UsageInsightsPage.tsx`, `frontend-react/src/pages/UsageInsightsPage.module.css`, `frontend-react/src/api/usage.ts`, `frontend-react/src/hooks/useUsageSummary.ts`
  - Active thread browser persistence and fresh-login reset markers: `frontend-react/src/session/activeSession.ts`
  - Transcript/session state: `frontend-react/src/store/chatStore.ts`
  - Main shell and responsive navigation: `frontend-react/src/pages/ChatPage.tsx`
  - Top-right Cognito account menu and summary plan/billing action: `frontend-react/src/components/layout/AccountMenu.tsx`
  - Desktop sidebar navigation, Models/Usage route entries, history list, and collapse rail: `frontend-react/src/components/layout/Sidebar.tsx`
  - Ask/Compare result rendering: `frontend-react/src/components/results/`
  - Deterministic assistant-offered follow-up extraction and response-level chip row: `frontend-react/src/followups/suggestedFollowups.ts`, `frontend-react/src/components/results/SuggestedFollowUps.tsx`, `frontend-react/src/components/results/ResponseCard.tsx`
  - Composer, attachments, model selection, and routing toggles: `frontend-react/src/components/composer/`
  - Local full-app dev: `run_app.py` starts FastAPI plus Vite, sets `CORTEX_API_PROXY_TARGET` / `FRONTEND_RUNTIME_API_BASE`, and can select guarded loopback-only subscription profiles with `--subscription-plan`.
  - Production build output: `frontend-react/dist` after `npm run --prefix frontend-react build`
- Frontend selection in FastAPI: `server/app.py`
  - `FRONTEND_DIR` explicitly selects the static directory to mount.
  - `REACT_FRONTEND=true` serves `frontend-react/dist` when `FRONTEND_DIR` is unset.
- Frontend container boundary: `Dockerfile.frontend` + `nginx.conf`
- Playwright E2E suite: `e2e/specs/`
  - Live full-stack browser scenarios: `e2e/specs/`
  - Frontend-only phone coverage: `e2e/responsive/mobile/`
  - Frontend-only desktop and iPad coverage: `e2e/responsive/desktop-ipad/`
  - Independent configs: `e2e/playwright.mobile.config.mjs`, `e2e/playwright.desktop-ipad.config.mjs`
- Playwright config: `e2e/playwright.config.mjs`

## CI and Workflows

- Main CI: `.github/workflows/ci.yml`
  - Detects frontend/backend/shared path changes.
  - Runs blocking Ruff/MyPy checks against changed Python files with pinned dev tools.
  - Runs Black as an advisory changed-file format check until a repo-wide baseline is applied.
  - Runs Gitleaks as a pinned CLI directory scan of the checked-out tree.
- Targeted backend regression pack: `.github/workflows/incident-regression-38.yml`
- Live browser E2E: `.github/workflows/live-e2e.yml`

## Common Change Paths

- Add/modify an API endpoint:
  1. Update `server/routes/`
  2. Update `server/schemas/`
  3. Add/adjust tests

- Change React history behavior:
  1. Keep `/v1/history` row-level persistence and session-title rename semantics in `server/routes/history.py` and `db/repository.py`.
  2. Update session/thread normalization in `frontend-react/src/history/historyThreads.ts`.
  3. Update active-thread browser persistence in `frontend-react/src/session/activeSession.ts` when reload/fresh-login behavior changes.
  4. Update hydration in `frontend-react/src/store/chatStore.ts` and presentation in the desktop/mobile history surfaces.
  5. Cover Ask session grouping and Compare `request_group_id` grouping in React and API tests.
  6. Update `README.md` and related docs

- Change routing behavior:
  1. Update files in `orchestrator/`
  2. Validate with routing/fallback tests
  3. Update routing docs (`README.md`, `docs/SMART_ROUTING_DIAGRAM.md`)

- Change web research or Tavily retrieval behavior:
  1. Update `tools/web/intent.py`, `tools/web/tavily_service.py`, `tools/web/tavily_client.py`, or `tools/web/tavily_resolver.py`
  2. Validate with Tavily/research tests
  3. Update `README.md`, `docs/TAVILY_INTEGRATION.md`, and logging/runbook docs when option or telemetry behavior changes

- Change token/cost behavior:
  1. Update provider clients and/or `server/utils.py`
  2. Keep `config/pricing.py` and `config/model_registry.yaml` aligned
  3. Update contract docs and tests

- Change subscription plan definitions or model billing classes:
  1. Update `config/subscription_plans.yaml` and/or model `billing_class` values in `config/model_registry.yaml`
  2. Keep billing classes separate from smart-routing `T0`-`T3` tiers
  3. Validate with `tests/test_subscription_plan_catalog.py`, `tests/test_model_registry_capabilities.py`, and the `/v1/models` contract tests

- Change DB schema:
  1. Add SQL migration under `db/migrations/`
  2. Update repository/table usage under `db/` + `server/`
  3. Follow `docs/runbooks/db-migrations.md`

- Change B2C billing persistence:
  1. Keep schema constraints/indexes in `db/migrations/20260718_add_b2c_billing_foundation.sql` aligned with `db/billing_repository.py`
  2. Register new tables for lazy reflection in `db/tables.py` and export public repository functions through `db/__init__.py`
  3. Keep repository functions transaction-neutral; callers own commit/rollback boundaries
  4. Validate portable repository behavior in `tests/test_billing_repository.py` and PostgreSQL row locking with `BILLING_TEST_DATABASE_URL`
  5. Keep effective paid access and lifecycle/grace policy in `server/billing/subscription_service.py`; routes must not infer access directly from a stored row

- Change effective subscription or entitlement behavior:
  1. Keep account validation/lazy creation in `server/billing/account_service.py`
  2. Keep lifecycle state, Free fallback, development override guards, and period selection in `server/billing/subscription_service.py`
  3. Keep feature/model/file checks and required allowance quantities in `server/billing/entitlement_service.py`; atomic reserve/settle/release/expiry mutations belong in `server/billing/metering_service.py`
  4. Update `server/schemas/responses.py`, `/v1/entitlements`, `/v1/whoami`, Postman, and `tests/test_billing_entitlements.py` together
  5. Preserve the separation between smart-routing tiers and subscription billing classes, and fail unknown plan/class/status data conservatively

- Change Stripe Checkout or Customer Portal behavior:
  1. Keep credentials, paid-plan Price mapping, and all redirect URLs in `server/billing/stripe_gateway.py`; never accept those values from request bodies
  2. Keep short DB units of work and provider calls separated in `server/billing/session_service.py`; Customer claiming must remain compare-and-set and Customer/Checkout creation idempotent
  3. Keep routes session-scoped and provider-safe in `server/routes/billing.py`; existing provider-live subscriptions must route to Portal instead of creating Checkout
  4. Update strict request/response schemas, `.env.example`, `docs/runbooks/stripe-billing.md`, README/FastAPI docs, Postman, and `tests/test_stripe_billing.py` together
  5. Hosted-session creation never grants paid access; only the verified webhook lifecycle may update paid subscription state

- Change the React subscription data layer:
  1. Keep public plan, current subscription, entitlement, Checkout, and Portal transport in `frontend-react/src/api/billing.ts` and `frontend-react/src/api/entitlements.ts`
  2. Keep structured billing error parsing in `frontend-react/src/subscription/subscriptionErrors.ts`; do not parse provider payloads or expose secrets in React
  3. Keep auth-aware, memory-only subscription state and bounded Checkout-return polling in `frontend-react/src/hooks/useSubscription.ts`; signed-out users must not call authenticated billing endpoints
  4. Treat return query parameters as refresh hints only; paid access remains the `/v1/entitlements` result synchronized by verified webhooks
  5. Validate API calls, typed errors, redirects, polling, and browser-storage non-authority in `frontend-react/src/__tests__/subscriptionDataLayer.test.tsx`

- Change React subscription gating UX:
  1. Derive model classes, feature flags, file limits, counters, and recommended plans only from `/v1/models`, `/v1/entitlements`, and `/v1/billing/plans`; never duplicate plan YAML values in React
  2. Keep locked premium models and restored history visible; unknown live billing metadata must fail conservatively without deleting or filtering prior content
  3. Keep backend enforcement authoritative and route structured access/allowance/payment denials through `subscriptionErrors.ts`, `subscriptionAccess.ts`, and `UpgradeDialog.tsx`
  4. Preserve prompt text and attachments until the backend accepts the stream; provider/file compatibility errors remain separate from subscription denials
  5. Validate composer, model catalogue, Usage allowances, keyboard dialog behavior, and narrow layouts with `subscriptionGating.test.tsx`, `subscriptionDenialDraft.test.tsx`, and affected page/component tests

- Change Stripe webhook or reconciliation behavior:
  1. Keep raw-body signature verification and Stripe API access in `server/billing/stripe_gateway.py`; never deserialize or mutate the request before verification
  2. Keep event dispatch, provider ownership checks, Price-to-plan mapping, stale-event policy, and reconciliation in `server/billing/webhook_service.py`
  3. Keep event/Subscription/period row locks and mutations transaction-neutral in `db/billing_repository.py`; callers own commit/rollback
  4. Keep effective paid/grace/cancellation access in `server/billing/subscription_service.py`; webhook handlers synchronize snapshots but do not invent a second entitlement policy
  5. Update `.env.example`, billing runbooks, README/FastAPI docs, Postman, and `tests/test_stripe_webhooks.py` together; do not expose cross-account reconciliation until administrator authorization exists

- Change atomic subscription metering:
  1. Keep transaction orchestration and transition rules in `server/billing/metering_service.py`; keep SQL row locks and counter mutations in `db/billing_repository.py`
  2. Preserve caller-owned commit/rollback boundaries, deterministic counter lock ordering, account-scoped request idempotency, nonnegative counters, and conservative configuration failures
  3. Validate portable transitions in `tests/test_billing_metering.py` and real concurrent overuse prevention with `BILLING_TEST_DATABASE_URL` in `tests/test_billing_postgres_integration.py`
  4. Ask/Compare/Optimize/upload routes integrate through `server/billing/enforcement_service.py`; preserve pre-execution reservation, output-aware settlement, and failure release without folding provider, optimizer, or object-storage execution into billing transactions
  5. Attachment analysis is one turn per Ask/Compare action, not per file or Compare target; upload consumes only the server-observed `uploaded_bytes`

- Investigate production logging incidents on AWS EC2:
  1. Follow `docs/runbooks/aws-ec2-logging.md`
  2. Correlate CloudFront/WAF logs with `request_id`/`X-Amz-Cf-Id`
  3. Use upload (`upload.*`) and research (`research.*`) event families for root cause

- Change React frontend behavior:
  1. Update `frontend-react/src/`
  2. Keep npm dependencies in `frontend-react/package.json` and `frontend-react/package-lock.json`
  3. Validate with `npm run --prefix frontend-react build`
  4. For FastAPI-hosted React, build first and set `FRONTEND_DIR` to `frontend-react/dist`
  5. Update `README.md` / `docs/FASTAPI_README.md` if setup, runtime config, or deployment assumptions change

---

Last updated: 2026-07-18
