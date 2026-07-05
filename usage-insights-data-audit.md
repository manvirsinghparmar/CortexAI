# Usage & insights data audit

Step 0 audit for `usage_insights_handoff/SPEC.md` section 7. This is backend discovery only; no UI implementation was started.

Implementation status: the audit's minimal backend fill has been implemented as `GET /v1/usage/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`, backed by `UsageSummaryDTO` and aggregate queries over existing audit tables. No schema migration was required.

## Existing backend inventory

### Endpoints

| Endpoint | Current shape | Contract usefulness |
|---|---|---|
| `GET /v1/usage/summary?from=YYYY-MM-DD&to=YYYY-MM-DD` | `UsageSummaryDTO` with the SPEC section 7 fields: concrete period, totals, latency metrics, spend, token delta, Smart counts, per-model rows, session modes, and 14-day activity. Defaults to the last 30 inclusive calendar days when both dates are omitted. | Dedicated backend contract for the Usage & insights screen. |
| `GET /v1/usage?from=YYYY-MM-DD&to=YYYY-MM-DD&group_by=day|provider|model` | `UsageReportDTO` with `from_date`, `to_date`, `group_by`, `totals { requests, tokens, cost }`, and `breakdown[] { bucket, requests, tokens, cost }`. Implemented by `server/routes/reporting.py` + `server/usage_reporting.py`. | Covers only coarse totals and day/provider/model buckets. It cannot populate the full UsageSummary screen without extra queries. |
| `GET /v1/usage/export?format=csv&from=...&to=...&group_by=...` | CSV columns: `bucket,requests,tokens,cost`. | Useful for current export behavior, but not enough for dashboard export if Step 7 needs the full UsageSummary rows. |
| `GET /v1/savings` / `GET /v1/savings/export` | Savings/baseline aggregates from `llm_savings`. | Not needed for SPEC section 7 except as a separate reporting surface. `totalSpend` should come from actual request cost, not savings baseline math. |
| `GET /v1/history?limit=&session_id=` | Row-level recent history with session, request group, mode, provider/model, latency, tokens, and cost. | Useful for UI history reconstruction, but not suitable for this dashboard because it is limit-bound and not an aggregate contract. |
| `GET /v1/models` / `GET /v1/providers` | Catalog data for enabled models and provider labels/UI metadata. | Can enrich provider/model display, but the UsageSummary contract expects `displayName` in the summary model rows. |

### Metering tables and write paths

| Source | Existing fields | Notes for UsageSummary |
|---|---|---|
| `llm_requests` | `user_id`, `session_id`, `request_id`, `route_mode`, `provider`, `model`, `created_at`, `api_key_id`, `request_group_id` | Best denominator for `totalRequests`, model reply counts, session mode classification, and period filtering. Compare writes one row per target response. |
| `llm_responses` | `llm_request_id`, `latency_ms`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost`, error fields, `created_at` | Best source for tokens, spend, average/min/p95 latency, and cost/request. |
| `routing_decisions` | `llm_request_id`, `routing_mode`, tiers, fallback flag, trace | Best source for `viaSmart` and `smartRoutedTotal`. Treat `routing_mode in ('smart', 'cheap', 'strong')` as Smart-routed; everything else, including missing routing rows, is manual/explicit. |
| `routing_attempts` | Per-attempt provider/model/status/latency/error | Not needed for the first UsageSummary contract. Useful only if future insights show fallback attempts. |
| `sessions` | `id`, `user_id`, `mode`, timestamps | Do not rely on `sessions.mode` for Ask/Compare/Mixed classification. The app now allows Ask and Compare in the same `session_id`, so classify from `llm_requests.route_mode` within the selected period. |
| `usage_daily` | `user_id`, `usage_date`, `total_requests`, `total_tokens`, `total_cost` | Useful for caps and legacy daily totals, but not the correct source for this screen. Compare persistence increments `total_requests` once per compare run, while the screen counts per-model replies/requests. |

The current persistence path already writes the raw data needed for most metrics:

- Chat: `persist_chat_interaction()` creates one `llm_requests` row, one `llm_responses` row, optional `routing_decisions`, updates the session timestamp, and upserts `usage_daily`.
- Compare: `persist_compare_interaction()` creates one `llm_requests` + `llm_responses` row per target response, stores a shared `request_group_id`, optional routing telemetry, updates the session timestamp, and upserts aggregate `usage_daily`.

## SPEC section 7 mapping

| UsageSummary field | Existing exposure | Backend source | Gap / minimal fill |
|---|---|---|---|
| `period.from`, `period.to` | Partial in `/v1/usage` as `from_date`, `to_date`; omitted defaults remain `null`. | Query params and `parse_date_range()`. | Add a dedicated summary period resolver with default last 30 days and concrete ISO dates. |
| `period.label` | Not exposed. | Derived from selected period. | Add label in the new summary DTO, e.g. `Last 30 days`. |
| `totalTokens` | Exposed by `/v1/usage.totals.tokens`. | `sum(llm_responses.total_tokens)`. | No migration; include in summary. Optional `tokensIn/tokensOut` can be derived from prompt/completion columns if added later. |
| `totalRequests` | Exposed by `/v1/usage.totals.requests`. | `count(llm_requests.id)` for period/user. | No migration. Use raw request rows, not `usage_daily.total_requests`, to keep Compare target rows counted as replies. |
| `totalSessions` | Not exposed. | `count(distinct llm_requests.session_id)` for non-null session IDs. | No migration. Decide whether to exclude legacy null-session rows; recommended: exclude from session counts and keep them in request/token totals. |
| `avgLatencyMs` | Not exposed in `/v1/usage`; present per row in `/v1/history`. | `avg(llm_responses.latency_ms)`. | Add aggregate query. Ignore null latency rows. |
| `p95LatencyMs` | Not exposed. | PostgreSQL percentile over `llm_responses.latency_ms`. | Add aggregate query using `percentile_cont(0.95) within group`. For SQLite-backed tests, compute percentile in Python or use a test helper branch. |
| `minLatencyMs` | Not exposed. | `min(llm_responses.latency_ms)`. | Add aggregate query. |
| `avgCostPerRequest` | Not exposed. | `sum(estimated_cost) / count(llm_requests.id)` or `avg(estimated_cost)`. | Add derived field. Use `0` when total requests is `0`. |
| `totalSpend` | Exposed by `/v1/usage.totals.cost`. | `sum(llm_responses.estimated_cost)`. | No migration; include as `totalSpend`. |
| `tokensDeltaPct` | Not exposed. | Compare current period token sum with the immediately preceding equal-length period. | Add previous-period query. Need a denominator convention when previous tokens are `0`; recommended: `0` when both periods are `0`, otherwise `100` for current > 0 and previous = 0 unless product wants `null`. |
| `smartRoutedTotal` | Not exposed. | Count joined rows where `routing_decisions.routing_mode in ('smart', 'cheap', 'strong')`. | Add join to `routing_decisions`. Missing routing rows count as manual/explicit. |
| `models[].provider` | Exposed by `/v1/usage?group_by=provider`, but not together with model rows. | `llm_requests.provider`. | Add model-level grouping by provider + model. Existing provider IDs are `openai`, `gemini`, `deepseek`, `grok`, `claude`; SPEC/logo copy uses `google` and `anthropic`. The UI resolver should accept both aliases or the endpoint should normalize display provider keys while preserving raw provider IDs if needed. |
| `models[].modelId` | Exposed by `/v1/usage?group_by=model`, but provider is lost in the bucket. | `llm_requests.model`. | Add model-level grouping by provider + model. |
| `models[].displayName` | Not exposed by backend reporting. | Can be derived from model catalog/presentation logic. | No DB migration. Add a small server-side display helper or let the frontend join model rows to `/v1/models`; to match SPEC exactly, return `displayName` from the summary endpoint. |
| `models[].replies` | Partially exposed by `/v1/usage?group_by=model` as `requests`. | `count(llm_requests.id)` grouped by provider/model. | Add provider+model grouped rows to avoid collisions between providers with similar model names. |
| `models[].viaSmart` | Not exposed. | `sum(case when routing_decisions.routing_mode in ('smart','cheap','strong') then 1 else 0 end)` grouped by provider/model. | Add routing join. No migration. |
| `sessionModes.askOnly` | Not exposed. | Per-session set of `llm_requests.route_mode` in period. | Add aggregation: sessions with only `ask` rows. |
| `sessionModes.compareOnly` | Not exposed. | Per-session set of `llm_requests.route_mode` in period. | Add aggregation: sessions with only `compare` rows. |
| `sessionModes.mixed` | Not exposed. | Per-session set containing both `ask` and `compare` in period. | Add aggregation. Do not use `sessions.mode`; it is creation metadata and can be stale for mixed sessions. |
| `switchedMidSession` | Not exposed. | Same population as `sessionModes.mixed`. | Return the mixed count unless product defines a stricter mid-conversation switch event. No migration. |
| `activityDaily[]` | Partially exposed by `/v1/usage?group_by=day`, but only for days with activity and for the requested range. | `date(llm_requests.created_at)`, `sum(llm_responses.total_tokens)`. | Add zero-padded 14-day activity array. Recommended semantics: last 14 calendar days ending at `period.to`, clipped only if product wants shorter custom periods. |

## Gaps and recommended minimal backend work

1. Add a dedicated aggregate endpoint instead of chaining existing endpoints.
   - Implemented route: `GET /v1/usage/summary?from=YYYY-MM-DD&to=YYYY-MM-DD`.
   - Default when omitted: last 30 days.
   - Response model: new `UsageSummaryDTO` matching SPEC section 7.
   - Route owner: `server/routes/reporting.py`; service owner: `server/usage_reporting.py`.

2. Add query-only aggregation helpers; no DB schema migration is required for the current contract.
   - Use `llm_requests` joined to `llm_responses` and left-joined to `routing_decisions`.
   - Current indexes already support the main filters/joins: user/time on `llm_requests`, `llm_responses.llm_request_id`, and `routing_decisions.llm_request_id`.
   - Avoid `usage_daily` for dashboard request/session/model counts because it is not reply-row granular.

3. Define two semantics before implementation:
   - `tokensDeltaPct` when the previous period has zero tokens.
   - `activityDaily` for custom periods shorter than 14 days.

4. Normalize provider display without changing metering storage.
   - Current backend provider IDs are `openai`, `gemini`, `deepseek`, `grok`, and `claude`.
   - SPEC provider logo copy uses OpenAI, Anthropic, DeepSeek, Google Gemini, Meta Llama, and Mistral.
   - No current `meta`/`mistral` provider exists in `config/providers.yaml` or `config/model_registry.yaml`; the screen should not fabricate those rows. If those providers are added later, the same grouping query will pick them up.
   - For this screen, either normalize `claude -> anthropic` and `gemini -> google` in a usage-specific presentation layer, or support both IDs in the logo/display resolver.

5. Add tests with the backend step.
   - Unit-test `build_usage_summary()` for totals, avg/min/p95 latency, Smart counts, model grouping, session modes, token delta, and 14-day padding.
   - Add a FastAPI contract test for `GET /v1/usage/summary` in the existing DB-mode reporting fixture.
   - Keep existing `/v1/usage` and `/v1/usage/export` behavior backward compatible.

## Step 0 conclusion

The backend already persists enough raw data to populate the Usage & insights screen without a schema migration. The blocker was API shape, not storage: the existing `/v1/usage` endpoint is too coarse and omits latency, Smart-route counts, session-mode classification, model display rows, period label/defaulting, token delta, and zero-padded 14-day activity. That gap is now filled by a dedicated summary DTO/service/route layered over existing audit tables, plus explicit conventions for zero-denominator token deltas and 14-day activity charts.
