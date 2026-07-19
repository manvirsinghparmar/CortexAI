# DB Migration Runbook

## Scope

This runbook covers how to author, validate, apply, and rollback SQL migrations in `db/migrations/`.

## Prerequisites

- PostgreSQL `DATABASE_URL` for the target environment.
- DB credentials with schema change permissions.
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

3. Run read/write smoke checks after apply:

```bash
python scripts/db_mode_smoke.py
```

## Deployment Order

1. Apply migrations to staging.
2. Run staging API smoke tests.
3. Apply the same migration to production.
4. Deploy API code that depends on new schema.

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
```

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

### Atomic metering operations

Work Package 4 uses the existing `usage_counters` and `usage_reservations` tables; it does not require another migration. `server/billing/metering_service.py` reserves, settles, releases, and expires usage inside the caller-owned transaction. Keep these transactions short and commit the reservation before starting a provider call.

Stale cleanup defaults to reservations older than 30 minutes and uses `SELECT ... FOR UPDATE SKIP LOCKED` before releasing counter quantities. No background scheduler is installed in this package; a future worker or operational task must call `expire_stale_reservations`. Inspect candidates without mutating them:

```sql
SELECT id, billing_account_id, request_id, operation_type, created_at
FROM public.usage_reservations
WHERE state = 'reserved'
  AND created_at < NOW() - INTERVAL '30 minutes'
ORDER BY created_at;
```

Do not repair `reserved_quantity` with ad hoc SQL. Run the metering cleanup in a reviewed caller-owned unit of work so each reservation and every related counter transition remain atomic and auditable.

### Ask and Compare enforcement deployment

Work Package 5 also uses the existing billing tables and requires no new migration. Apply and verify `20260718_add_b2c_billing_foundation.sql` before deploying the WP5 API: database-mode `/v1/chat*` and `/v1/compare*` now create Free-plan reservations even while `BILLING_ENABLED=false`. A missing billing table therefore fails the request conservatively before any provider call.

Reservation, provider execution, and settlement are deliberately separate transactions. During a rolling deployment, do not drop or rewrite the additive billing tables. If the new API must be rolled back, redeploy the prior application version and retain the billing rows for audit/reconciliation; stale `reserved` rows can be handled by the reviewed cleanup flow above.

### Billing rollback

The preferred application rollback is to redeploy the previous API version and leave the additive, unused tables in place. This preserves any billing evidence and requires no database mutation.

If the tables must be removed before any production billing data exists:

1. Stop billing writers and deploy the previous API version.
2. Take and verify a database snapshot.
3. Confirm all six billing tables contain zero rows.
4. Drop only the billing tables in dependency order inside one transaction:

```sql
BEGIN;
DROP TABLE IF EXISTS public.billing_webhook_events;
DROP TABLE IF EXISTS public.usage_reservations;
DROP TABLE IF EXISTS public.usage_counters;
DROP TABLE IF EXISTS public.usage_periods;
DROP TABLE IF EXISTS public.subscriptions;
DROP TABLE IF EXISTS public.billing_accounts;
COMMIT;
```

Once billing rows exist, do not use the table-drop rollback. Keep the additive schema or restore/repair from the verified snapshot with a reviewed compensating migration. Neither rollback path deletes or modifies historical LLM request/response or chat-history data.
