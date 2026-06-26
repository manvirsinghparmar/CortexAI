# CLAUDE.md

## Objective

Keep Claude Code sessions consistent for this repository by front-loading project context, enforcing shared engineering conventions, and using repeatable playbooks for long-running work.

## Session Bootstrap (Always)

1. Read `README.md` for current runtime behavior and endpoint contracts.
2. Read `.claude/project-context.md` for architecture, guardrails, and test matrix.
3. If the request matches a standard task shape, load the matching playbook from `.claude/playbooks-index.md` before planning.

## Source of Truth

- Primary branch: `develop`
- All feature/fix branches are created from `develop`
- All PRs target `develop` (not `master`)

## Stack And Runtime Facts

- Python `3.12` backend with FastAPI entrypoint in `run_server.py`.
- Multi-provider orchestration (`openai`, `gemini`, `deepseek`, `grok`, `claude`) under `api/` + `orchestrator/`.
- PostgreSQL-backed runtime is the standard mode (`DATABASE_URL` required; postgres URL expected).
- Legacy static frontend under `frontend/` and React/Vite frontend under `frontend-react/`.
- FastAPI serves static frontend assets unless `SERVE_FRONTEND=false`; set `FRONTEND_DIR=frontend-react/dist` after `npm run --prefix frontend-react build` to serve React.
- React dependencies stay in `frontend-react/package.json` / `frontend-react/package-lock.json`, not `requirements.txt`.
- Browser E2E harness under `e2e/` (Playwright).

## Engineering Conventions

- Keep route handlers thin; put business logic in service/orchestration modules.
- Update schemas/contracts with route behavior changes (`server/schemas/`, `README.md`, and Postman collection as needed).
- Keep pricing and registry aligned when model economics change:
  - `config/pricing.py`
  - `config/model_registry.yaml`
- For DB schema changes:
  - add forward migration in `db/migrations/`
  - update reflected table/query usage in `db/tables.py` and `db/repository.py`
  - follow `docs/runbooks/db-migrations.md`

## Documentation Sync Requirement (Mandatory)

Documentation sync is a required completion gate for every task that changes behavior, contracts, configuration, tests, or operations. A task is not complete until all impacted docs are updated in the same change set.

Always review and update impacted documentation, including at minimum:
- `README.md`
- `docs/FASTAPI_README.md`
- `docs/postman/CortexAI_B2B.postman_collection.json`
- `docs/PROJECT_MAP.md` (when code-path ownership/change map shifts)
- `docs/runbooks/*.md` (when operational workflow changes)
- `.claude/project-context.md` (when core invariants/guardrails change)

For endpoint or schema changes, update route lists, request/response examples, error semantics, and Postman entries in the same task. For runtime/config changes, update environment variable docs and startup/runtime assumptions. Before handoff, explicitly verify there is no known documentation drift. Do not defer documentation updates to a follow-up task.

## Validation Gates

- Default test command: `python -m pytest -q`
- Full release gate: `python scripts/release_gate.py`
- E2E suite: `npm run --prefix e2e test`
- React frontend build: `npm run --prefix frontend-react build`
- Pricing/registry alignment: `python -m pytest tests/test_registry_pricing_alignment.py -q`

Choose the smallest relevant subset during iteration, then run broader gates before handoff.

## Triggerable Playbooks

- "add feature X end-to-end" → `.claude/playbook-feature-end-to-end.md`
- "migrate API Y" → `.claude/playbook-migrate-api.md`
- "refactor module Z with tests" → `.claude/playbook-refactor-module-with-tests.md`

See `.claude/playbooks-index.md` for the full index and usage instructions.
