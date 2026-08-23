# Playbook Index

Use these as repeatable templates for long-running tasks.

## Trigger Map

- "add feature X end-to-end" -> [playbook-feature-end-to-end.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbook-feature-end-to-end.md)
- "migrate API Y" -> [playbook-migrate-api.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbook-migrate-api.md)
- "refactor module Z with tests" -> [playbook-refactor-module-with-tests.md](/C:/Users/14169/PycharmProjects/PythonProject/OpenAIProject/.codex/playbook-refactor-module-with-tests.md)

## How To Use

1. Confirm scope and non-goals.
2. Select the closest playbook.
3. Execute in phases (design -> implementation -> validation -> docs).
4. Report what changed, what was validated, and what remains.
5. If the user requested a commit, verify the blocking local hooks from
   [ci-commit-gate.md](./ci-commit-gate.md) are installed; do not bypass the
   automatic pre-commit or pre-push gates.

## Cross-Repo Variant

If the task spans multiple repositories, relaunch Codex with repeated `--add-dir` paths so planning and edits happen in one session.
