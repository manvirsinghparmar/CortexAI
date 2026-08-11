# DB Migration Runbook

## Scope

This runbook covers how to author, validate, apply, and rollback SQL migrations in `db/migrations/`.

## Prerequisites

- PostgreSQL owner/admin connection for the target environment. Do not assume
  the normal application `DATABASE_URL` role can run DDL.
- DB credentials that own existing altered tables and have `CREATE` permission
  on the target schema.
- Backup/restore access for production.

## Naming Convention

Create migration files in `db/migrations/` using:

`YYYYMMDD_short_description.sql`

Example:

`20260301_add_provider_config_table.sql`

## Authoring Checklist

1. Keep migrations additive and forward-only when possible.
2. Prefer explicit `IF EXISTS` / `IF NOT EXISTS` for safer re-runs.
3. Add indexes only when needed for query plans.
4. Avoid mixing unrelated changes in one migration.
5. Update related repository/table code in the same PR.

## Local Validation

1. Run syntax + app test checks:

```bash
python -m pytest tests/test_component_boundaries.py tests/test_fastapi_contract_and_guardrails.py -q
```

2. Apply migration on a local/staging-like DB:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/<migration_file>.sql
```

If the runtime role is intentionally restricted, use a separate owner/admin
connection for the migration:

```powershell
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/<migration_file>.sql
```

After a migration that changes reflected tables, restart the API process so its
SQLAlchemy table cache sees the new columns.

3. Run read/write smoke checks after apply:

```bash
python scripts/db_mode_smoke.py
```

## Deployment Order

1. Apply migrations to staging.
2. Run staging API smoke tests.
3. Apply the same migration to production.
4. Deploy API code that depends on new schema.

For the current subscription/Cortex release, apply these additive scripts in
this exact order before starting the new API:

```powershell
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260718_add_b2c_billing_foundation.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260727_add_cortex_analysis_runs.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260729_add_unified_ai_credits.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260730_add_usage_reservation_activity.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260731_add_model_pricing_audit.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260802_add_cortex_analysis_attribution.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260804_add_generation_budget_audit.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260807_add_cache_aware_credit_accounting.sql
```

The `20260727` script alters `llm_requests`, so the migration connection must
own that table. The later unified-credit and activity scripts depend on the
`20260718` billing foundation. PostgreSQL startup validates the complete table
and column contract, including generation-budget audit fields, and exits before serving provider traffic if any script is
missing.

### Cache-aware accounting and reuse migration

`20260807_add_cache_aware_credit_accounting.sql` is additive and idempotent. It
backfills historical credit rows as uncached without changing their totals, adds
non-negative cache token/credit columns, extends Cortex Analysis audit evidence,
creates reusable optimizer/research/context-summary storage, and adds the
`cache_reuse_events` audit table used for period-scoped reuse rates. Apply it with the
schema-owner connection after `20260804`, restart all API processes to refresh
SQLAlchemy reflection, and leave cache-aware settlement disabled until shadow
totals have been reconciled against provider invoices.

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'credit_transactions'
  AND column_name IN (
    'normal_input_tokens', 'cached_input_tokens', 'cache_write_tokens',
    'reasoning_tokens', 'normal_input_credits', 'cached_input_credits',
    'cache_write_credits', 'uncached_equivalent_credits', 'cache_savings_credits'
  )
ORDER BY column_name;

SELECT input_tokens, normal_input_tokens, cached_input_tokens,
       cache_write_tokens, total_credits, uncached_equivalent_credits
FROM public.credit_transactions
ORDER BY created_at DESC
LIMIT 20;

SELECT to_regclass('public.prompt_optimization_cache'),
       to_regclass('public.research_reuse_cache'),
       to_regclass('public.cache_reuse_events');
```

### Generation budget audit migration

`20260804_add_generation_budget_audit.sql` is additive and idempotent. It adds
the resolved profile, requested/effective output ceilings, reasoning mode/effort,
and policy version to `llm_requests`; it adds normalized `completion_status` and
`stop_cause` to `llm_responses` and backfills existing rows. Apply it before the
API version that requires provider-aware generation budgets, then restart every
API process so reflected metadata is refreshed.

```sql
SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'llm_requests'
  AND column_name IN (
    'generation_profile',
    'requested_max_output_tokens',
    'effective_max_output_tokens',
    'generation_policy_version'
  )
ORDER BY column_name;

SELECT column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = 'llm_responses'
  AND column_name IN ('completion_status', 'stop_cause')
ORDER BY column_name;
```

For breaking/large migrations:

1. Expand schema first (backward compatible).
2. Deploy code using new schema.
3. Contract/drop old columns in a later release window.

## Rollback Strategy

Because SQL migrations here are forward scripts, rollback is operational:

1. Stop rollout / shift traffic away from new API version.
2. Restore from DB backup or run a prepared compensating SQL script.
3. Redeploy previous API image.

Always prepare a compensating script before production apply when dropping/changing columns.

## Production Safety Rules

1. Always run with `-v ON_ERROR_STOP=1`.
2. Take a fresh backup/snapshot before migration.
3. Announce migration window and owner in release notes.
4. Verify key tables and API health immediately after migration.

## Verification Queries

```sql
-- check applied schema objects
\dt

-- spot-check recent API writes
SELECT id, created_at
FROM llm_requests
ORDER BY created_at DESC
LIMIT 20;

-- Cortex Analysis schema added by 20260727_add_cortex_analysis_runs.sql
SELECT response_revision_root_id, response_revision
FROM llm_requests
WHERE response_revision_root_id IS NOT NULL
ORDER BY created_at DESC
LIMIT 20;

SELECT id, request_group_id, source_fingerprint, created_at
FROM cortex_analysis_runs
ORDER BY created_at DESC
LIMIT 20;

SELECT id, disagreements, disagreement_note
FROM cortex_analysis_runs
ORDER BY created_at DESC
LIMIT 20;

SELECT id, request_id, state, last_activity_at
FROM usage_reservations
ORDER BY last_activity_at DESC
LIMIT 20;

SELECT request_id, operation_type, item_type, total_credits, metadata, created_at
FROM credit_transactions
ORDER BY created_at DESC
LIMIT 20;
```

## Cortex Analysis Migration

Migration:

`db/migrations/20260727_add_cortex_analysis_runs.sql` and
`db/migrations/20260802_add_cortex_analysis_attribution.sql`

Apply it with an owner/admin connection before deploying the Cortex Analysis
routes:

```powershell
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260727_add_cortex_analysis_runs.sql
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260802_add_cortex_analysis_attribution.sql
```

The first migration adds append-only response revision metadata to `llm_requests`
and creates `cortex_analysis_runs`. The attribution migration adds nullable
`disagreement_note`; the existing JSONB `disagreements` column stores the new
`{who,text}` objects without a destructive rewrite, so legacy string rows remain
available for compatibility reads. The migration role must own `llm_requests` and
have `CREATE` permission on the target schema. Restart the API after applying
it so reflected SQLAlchemy metadata sees the new columns and table. Until then,
both analysis endpoints return `503 cortex_analysis_schema_unavailable` before
provider work.

Rollback should normally redeploy the previous application version and retain
the additive columns/table. Before any destructive schema rollback, stop
writers, take a verified snapshot, and confirm `cortex_analysis_runs` contains
no production evidence that must be retained.

## B2C Billing Foundation

Migration:

`db/migrations/20260718_add_b2c_billing_foundation.sql`

Apply it before deploying code that calls `db/billing_repository.py`:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260718_add_b2c_billing_foundation.sql
```

The migration is additive. It creates six new tables and their constraints/indexes; it does not alter `users`, sessions, messages, `llm_requests`, or `llm_responses`. Verify the schema after apply:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name IN (
    'billing_accounts',
    'subscriptions',
    'usage_periods',
    'usage_counters',
    'usage_reservations',
    'billing_webhook_events'
  )
ORDER BY table_name;

SELECT indexname
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN (
    'billing_accounts',
    'subscriptions',
    'usage_periods',
    'usage_counters',
    'usage_reservations',
    'billing_webhook_events'
  )
ORDER BY tablename, indexname;
```

Run the repository tests and, when a disposable PostgreSQL database is available, the real reflection/locking tests:

```bash
python -m pytest tests/test_billing_repository.py tests/test_billing_metering.py -q
BILLING_TEST_DATABASE_URL="postgresql+psycopg://..." python -m pytest tests/test_billing_postgres_integration.py -q
```

### Unified AI credits and reconciliation ledger

Migration:

`db/migrations/20260729_add_unified_ai_credits.sql`

Apply it after the B2C billing foundation and before deploying the unified-credit API:

```bash
psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260729_add_unified_ai_credits.sql
```

The migration adds the immutable `credit_transactions` reconciliation table. Existing legacy counter rows remain available for audit, but the new runtime creates and mutates only `usage_counters.meter_key = 'ai_credits'`. The table rejects negative token, credit, and provider-cost values and prevents duplicate item settlement for the same reservation.

Verify the schema and newest reconciliation records:

```sql
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name = 'credit_transactions';

SELECT request_id, operation_type, item_type, total_credits,
       usage_estimated, pricing_version, created_at
FROM public.credit_transactions
ORDER BY created_at DESC
LIMIT 20;
```

Run the credit and billing suites after apply:

```bash
python -m pytest tests/test_credit_calculator.py tests/test_billing_repository.py tests/test_billing_metering.py tests/test_billing_entitlements.py -q
BILLING_TEST_DATABASE_URL="postgresql+psycopg://..." python -m pytest tests/test_billing_postgres_integration.py -q
```

### Atomic metering and automatic cleanup

Migration:

`db/migrations/20260730_add_usage_reservation_activity.sql`

Apply it after the unified-credit migration. It adds non-null
`usage_reservations.last_activity_at` plus the state/activity index used by the
cleanup worker. `server/billing/metering_service.py` reserves, supplements,
settles, releases, and expires usage inside caller-owned transactions. Keep
these transactions short and commit the reservation before starting a provider
call.

The API runs one cleanup cycle at startup and subsequent cycles every 300
seconds by default. Active in-process reservations are persisted every 60
seconds; cleanup considers a reservation stale after 1,800 seconds. Configure
with `ENABLE_BILLING_RESERVATION_CLEANUP_WORKER`,
`BILLING_RESERVATION_CLEANUP_INTERVAL_SECONDS`,
`BILLING_RESERVATION_STALE_AFTER_SECONDS`, and
`BILLING_RESERVATION_HEARTBEAT_INTERVAL_SECONDS`. Cleanup uses
`SELECT ... FOR UPDATE SKIP LOCKED`, so concurrent application instances cannot
release the same row twice. Inspect candidates without mutating them:

```sql
SELECT id, billing_account_id, request_id, operation_type, last_activity_at
FROM public.usage_reservations
WHERE state = 'reserved'
  AND last_activity_at < NOW() - INTERVAL '30 minutes'
ORDER BY last_activity_at;
```

Do not repair `reserved_quantity` with ad hoc SQL. Investigate worker logs
(`billing.reservation_cleanup.*`) and restore the worker before considering a
reviewed manual call to the same cleanup service.

### Model identity and pricing audit

Migration:

`db/migrations/20260731_add_model_pricing_audit.sql`

Apply it with a role that owns `llm_requests` and `llm_responses` before
deploying the canonical catalogue/pricing runtime:

```powershell
psql "$env:MIGRATION_DATABASE_URL" -v ON_ERROR_STOP=1 -f db/migrations/20260731_add_model_pricing_audit.sql
```

The additive migration records the originally requested model on requests and
the provider-served/pricing identities, lifecycle/alias resolution, detailed
cache/reasoning token usage, price-rule/version, unknown-price flag, and JSONB
price snapshot on responses. Existing response rows are retained and are
explicitly marked `pricing_unknown=true`; the migration does not invent
historical evidence that was not stored previously.

The new identity columns remain nullable at the database layer so the migration
can be applied safely before a rolling application deployment. The upgraded
write path always supplies them; rows written by an older instance during the
rollout remain distinguishable as incomplete audit evidence.

Verify the columns and inspect recent audit rows:

```sql
SELECT table_name, column_name
FROM information_schema.columns
WHERE table_schema = 'public'
  AND (
    (table_name = 'llm_requests' AND column_name = 'requested_model')
    OR
    (table_name = 'llm_responses' AND column_name IN (
      'served_model', 'pricing_model', 'model_lifecycle_status',
      'replacement_model', 'model_migration_reason',
      'pricing_rule_applied', 'pricing_version', 'pricing_unknown',
      'pricing_snapshot'
    ))
  )
ORDER BY table_name, column_name;

SELECT r.requested_model, s.served_model, s.pricing_model,
       s.pricing_rule_id, s.pricing_version, s.pricing_unknown
FROM public.llm_requests AS r
JOIN public.llm_responses AS s ON s.request_id = r.id
ORDER BY s.created_at DESC
LIMIT 20;
```

Restart the API after apply so reflected SQLAlchemy metadata includes the new
columns. A missing required audit column fails PostgreSQL startup before
provider traffic. Roll back the application by redeploying the prior version
and retain these additive audit columns; do not delete billing evidence.

### Ask and Compare enforcement deployment

Apply and verify all five release migrations listed above before deploying the
API. Database-mode Ask, Compare, Improve Prompt, and Cortex Analysis create
unified-credit reservations even while `BILLING_ENABLED=false`. A missing
billing table or required column fails PostgreSQL startup before any provider
call.

Work Package 8 also requires no new migration. Its verified Stripe webhook lifecycle uses the existing `billing_webhook_events`, `subscriptions`, `usage_periods`, and `usage_counters` columns from `20260718_add_b2c_billing_foundation.sql`. Apply and verify that migration before registering the Stripe webhook endpoint; otherwise verified events return a non-2xx response and remain retryable at Stripe.

Reservation, provider execution, and settlement are deliberately separate transactions. During a rolling deployment, do not drop or rewrite the additive billing tables. If the new API must be rolled back, redeploy the prior application version and retain the billing rows for audit/reconciliation; stale `reserved` rows can be handled by the reviewed cleanup flow above.

### Billing rollback

The preferred application rollback is to redeploy the previous API version and leave the additive, unused tables in place. This preserves any billing evidence and requires no database mutation.

If the tables must be removed before any production billing data exists:

1. Stop billing writers and deploy the previous API version.
2. Take and verify a database snapshot.
3. Confirm all seven billing tables contain zero rows.
4. Drop only the billing tables in dependency order inside one transaction:

```sql
BEGIN;
DROP TABLE IF EXISTS public.credit_transactions;
DROP TABLE IF EXISTS public.billing_webhook_events;
DROP TABLE IF EXISTS public.usage_reservations;
DROP TABLE IF EXISTS public.usage_counters;
DROP TABLE IF EXISTS public.usage_periods;
DROP TABLE IF EXISTS public.subscriptions;
DROP TABLE IF EXISTS public.billing_accounts;
COMMIT;
```

Once billing rows exist, do not use the table-drop rollback. Keep the additive schema or restore/repair from the verified snapshot with a reviewed compensating migration. Neither rollback path deletes or modifies historical LLM request/response or chat-history data.
