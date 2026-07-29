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
```
