# Playbook: Refactor Module With Tests

## Use When

- You need structural cleanup (readability, decomposition, reuse, typing, safety) while preserving behavior.

## Inputs To Confirm

- Refactor target module(s).
- Non-goals (what behavior must not change).
- Required invariants and edge cases.

## Execution Phases

1. Freeze behavior with tests first:
   - add/extend tests that capture current expected behavior.
2. Refactor in small commits/chunks:
   - extract pure helpers
   - reduce function/class complexity
   - tighten typing where low risk
3. Keep public interfaces stable unless migration is explicitly requested.
4. Run focused tests after each meaningful change.
5. Run broader suite before handoff.
6. Remove dead code only after replacement paths are green.

## Module-Specific Touch Map

- Routing logic refactor: `orchestrator/` + routing tests.
- API/service refactor: `server/` + contract tests.
- Provider refactor: `api/` + unified response contract tests.
- Persistence refactor: `db/` + DB-mode smoke and reporting tests.

## Validation Checklist

- Relevant targeted tests for refactored module(s).
- `python -m pytest -q`
- `python scripts/release_gate.py` for high-confidence refactors.

## Done Criteria

- Behavior parity is maintained (or intentionally changed and documented).
- Complexity reduced measurably (smaller units, clearer boundaries).
- Tests protect the new structure and prior failure modes.
