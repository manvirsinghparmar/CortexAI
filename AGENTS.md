# AGENTS.md

## Objective

Keep Codex sessions consistent for this repository by front-loading project context, enforcing shared engineering conventions, and using repeatable playbooks for long-running work.

## Session Bootstrap (Always)

1. Read [README.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/README.md) for current runtime behavior and endpoint contracts.
2. Read [project-context.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/project-context.md) for architecture, guardrails, and test matrix.
3. If the request matches a standard task shape, load the matching playbook from [playbooks-index.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbooks-index.md) before planning.

## Workspace Strategy For Monorepos/Polyrepos

- Prefer expanding scope with repeated `--add-dir` flags instead of broader sandbox modes.
- Recommended launch pattern:

```powershell
codex --cd C:\path\to\primary\repo `
  --add-dir C:\path\to\repo-a `
  --add-dir C:\path\to\repo-b `
  "Implement <task> end-to-end across repos"
```

- `--add-dir` is the default move whenever a task touches shared SDKs, sibling services, infra repos, or separate frontend/backend repositories.

## Stack And Runtime Facts

- Python `3.12` backend with FastAPI entrypoint in [run_server.py](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/run_server.py).
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
  - follow [db-migrations.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/docs/runbooks/db-migrations.md)

## Documentation Sync Requirement (Mandatory)

- Documentation sync is a required completion gate for every task that changes behavior, contracts, configuration, tests, or operations.
- A task is not complete until all impacted docs are updated in the same change set.
- Always review and update impacted documentation, including at minimum:
  - `README.md`
  - `docs/FASTAPI_README.md`
  - `docs/postman/CortexAI_B2B.postman_collection.json`
  - `docs/PROJECT_MAP.md` (when code-path ownership/change map shifts)
  - `docs/runbooks/*.md` (when operational workflow changes)
  - `.codex/project-context.md` (when core invariants/guardrails change)
- For endpoint or schema changes, update route lists, request/response examples, error semantics, and Postman entries in the same task.
- For runtime/config changes, update environment variable docs and startup/runtime assumptions.
- For routing/research/compare/front-end behavior changes, update the corresponding guide docs/diagrams in `docs/`.
- Before handoff, explicitly verify there is no known documentation drift. If no doc files changed, state why docs were unaffected.
- Do not defer documentation updates to a follow-up task.

## Validation Gates

- Default test command: `python -m pytest -q`
- Full release gate: `python scripts/release_gate.py`
- E2E suite: `npm run --prefix e2e test`
- React frontend build: `npm run --prefix frontend-react build`
- Pricing/registry alignment: `python -m pytest tests/test_registry_pricing_alignment.py -q`

Choose the smallest relevant subset during iteration, then run broader gates before handoff.

## Triggerable Playbooks

- "add feature X end-to-end" -> [playbook-feature-end-to-end.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbook-feature-end-to-end.md)
- "migrate API Y" -> [playbook-migrate-api.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbook-migrate-api.md)
- "refactor module Z with tests" -> [playbook-refactor-module-with-tests.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbook-refactor-module-with-tests.md)

Use these playbooks as execution templates: scope, touch-map, verification commands, and done criteria.
