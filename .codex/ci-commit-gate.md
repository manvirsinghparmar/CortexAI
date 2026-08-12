# Per-Commit CI Parity Gate

`.github/workflows/ci.yml` is the source of truth for this gate. Update this
document in the same change whenever that workflow's blocking jobs or commands
change.

## When the gate is required

- When the user requests a commit, run this gate exactly once against the final
  commit SHA after the commit is created and before pushing or handing it off.
- Run from a clean checkout of that exact SHA so generated files, ignored logs,
  and local `.env` secrets cannot change the Gitleaks result.
- If the commit is amended or another change is added, the prior result is stale;
  run the gate once again against the new SHA.
- Do not create a commit only to run this gate when the user did not authorize a
  commit. Continue to use proportionate validation for uncommitted work.
- Record the validated SHA and the result of every applicable blocking job in the
  handoff. Fix failures before push; if an environment prerequisite is
  unavailable, report that check as unverified rather than claiming CI parity.

## Select the applicable jobs

Compare the final commit/PR branch with its target branch (normally
`origin/develop`). Match the path filters in `.github/workflows/ci.yml`:

- Always run the security secrets scan.
- Run backend quality and the API image build for backend, database, or shared
  changes.
- Run React responsive quality and the frontend artifact build for React or
  shared changes.
- A shared change runs both backend and React paths.

## Backend quality

Use Python 3.12 with `requirements.txt` and `requirements-dev.txt` installed.
Build the changed-file list from added or modified Python files only:

```powershell
$pythonChangedFiles = @(
  git diff --name-only --diff-filter=AM origin/develop...HEAD -- '*.py'
)

if ($pythonChangedFiles.Count -gt 0) {
  python -m ruff check $pythonChangedFiles
  python -m black --check $pythonChangedFiles  # advisory in CI
  python -m mypy --explicit-package-bases --follow-imports=skip $pythonChangedFiles
}
```

Run the blocking backend suites and dependency audit:

```powershell
python -m pytest tests/test_baseline_safety_rails.py tests/test_provider_catalog.py tests/test_client_registry_and_schema_dynamic.py tests/test_fastapi_contract_and_guardrails.py tests/test_dynamic_provider_discovery_e2e.py tests/test_component_boundaries.py -q
pip-audit -r requirements.txt -r requirements-dev.txt
docker build -f Dockerfile.api -t cortexai-api:ci .
```

Black is advisory in CI; run and report it, but it does not determine CI success.

## React responsive quality and artifact

Use Node.js 20. In a clean checkout, run:

```powershell
npm ci --prefix frontend-react
npm ci --prefix e2e
Push-Location e2e
npx playwright install chromium
Pop-Location
npm run --prefix frontend-react test
npm run --prefix frontend-react lint
npm run --prefix frontend-react build
npm run --prefix e2e test:mobile
npm run --prefix e2e test:desktop-ipad
python scripts/build_frontend_artifact.py
```

## Security secrets scan

Use Gitleaks `8.30.1`, matching CI, and run the exact blocking scan from the clean
checkout root:

```powershell
gitleaks version
gitleaks dir . --no-banner --redact --exit-code 1
```

Do not add allowlist entries merely to make the scan pass. Remove real secrets;
for a verified false positive, prefer wording or fixture changes that retain the
intended meaning without resembling a credential assignment.
