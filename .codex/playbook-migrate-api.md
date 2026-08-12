# Playbook: Migrate API

## Use When

- You are changing an existing endpoint contract, replacing route behavior, or migrating clients from old to new API shape.

## Inputs To Confirm

- Current contract and proposed contract diff.
- Compatibility strategy:
  - additive change
  - versioned route
  - deprecation window
- Client impact scope (internal frontend, external users, scripts, Postman).

## Execution Phases

1. Baseline current behavior:
   - capture existing request/response shapes in tests.
2. Design migration path:
   - prefer additive compatibility first.
   - if breaking, define a clear version/deprecation sequence.
3. Implement schema and route changes:
   - update `server/schemas/requests.py` and `server/schemas/responses.py`
   - update route handlers under `server/routes/`
4. Update dependent layers:
   - persistence/reporting services
   - frontend API calls
   - helper scripts/tooling that call impacted endpoints
5. Adjust tests:
   - keep old-contract tests when deprecation window exists
   - add tests for new contract path
6. Update docs and migration notes:
   - `README.md` endpoint sections/examples
   - `docs/postman/CortexAI_B2B.postman_collection.json`
   - changelog/runbook note for client migration steps

## DB-Linked Changes

If API migration requires schema updates, follow `docs/runbooks/db-migrations.md` and include expand/migrate/contract sequencing.

## Validation Checklist

- Route contract tests pass.
- Backward-compatibility tests pass (if applicable).
- `python -m pytest -q`
- `python scripts/release_gate.py`
- `npm run --prefix e2e test` if frontend/external UX depends on migrated contract.
- When the user requests a commit, run [ci-commit-gate.md](./ci-commit-gate.md)
  exactly once against the clean final commit SHA before push or handoff.

## Done Criteria

- New contract is fully implemented and documented.
- Compatibility/deprecation behavior is intentional and tested.
- Operational migration notes are explicit for downstream consumers.
