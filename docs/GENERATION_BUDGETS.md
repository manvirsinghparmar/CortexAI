# Generation Budgets

Ask and Compare use one provider-aware generation budget for request validation,
provider execution, credit authorization, response metadata, persistence, and retry UX.
The canonical profile values are in `config/generation_profiles.yaml`; no route or
billing module owns a second output-token default.

## Profiles

| Profile | Requested output ceiling | Default reasoning effort | Intended use |
| --- | ---: | --- | --- |
| `quick` | 1,024 | low | Short, low-credit answers and legacy omitted requests |
| `balanced` | 4,096 | medium | Browser default and normal detailed answers |
| `deep` | 12,288 | high | Long analysis and reasoning-heavy work |
| `extended` | 32,768 | max | Maximum room when the selected model supports it |

The effective ceiling is the minimum of the profile ceiling, the selected model's
`max_output_tokens`, the 32,768 operational ceiling, and remaining context after a
1,024-token safety margin. Profiles are transparently reduced to those safe bounds.
An explicit `generation.max_output_tokens` or legacy `max_tokens` above the safe
bound is rejected with `422 invalid_generation_budget`; it is never silently clipped.

## Request contract

Ask and Compare accept a shared `generation` object:

```json
{
  "generation": {
    "profile": "balanced",
    "reasoning": {"mode": "auto", "effort": "auto"}
  }
}
```

`profile` and `max_output_tokens` are mutually exclusive. `generation` and legacy
`max_tokens` are also mutually exclusive. Compare additionally permits a target-level
`generation` override; a target override wins over the shared Compare value.

Legacy clients that omit both fields use `quick` (1,024). The React app
explicitly defaults new Ask and Compare turns to `balanced` and exposes Quick,
Balanced, Deep, and Extended through the Answer depth selector.

## Reasoning mapping

`orchestrator/generation_policy.py` translates the provider-neutral mode and effort
into adapter parameters. The model registry declares supported modes, efforts,
disable support, whether reasoning counts against output, and native output limits.
DeepSeek receives thinking configuration, Claude receives adaptive thinking and output
effort, Gemini receives thinking configuration, and supported OpenAI models receive
reasoning effort. Unsupported combinations are rejected before credits are reserved.

Reasoning tokens are model work tokens, not hidden conversation history. When a
provider counts them inside its output allowance, a small output ceiling can be
exhausted before visible text is produced. Such a response remains billable provider
work and is returned as `incomplete`, not rewritten as a provider failure.

## Billing and estimates

The exact effective ceiling passed to a provider is also passed to
`server/billing/enforcement_service.py`. Compare authorizes each target with its own
resolved ceiling. The preflight is a maximum temporary AI-credit hold; settlement
uses actual successful usage and releases the unused amount.

`POST /v1/billing/estimate-generation` performs the same resolution and credit
calculation without reserving credits. It returns per-target ceilings, the maximum
temporary hold, remaining credits, and whether that hold can currently be authorized.

## Completion and retry contract

Every response exposes:

- `completion_status`: `complete`, `incomplete`, or `failed`
- `stop_cause`: normalized terminal cause such as `natural`, `token_limit`,
  `context_limit`, `content_filter`, or `error`
- `generation_budget`: requested/effective profile, ceiling, reasoning values, and
  policy version
- `retry_with_more_room`: whether a larger profile is available and its recommendation

Partial text is preserved. React displays an explicit incomplete banner and can retry
the same response slot with the recommended next profile. A retry is a new model call
and may use additional AI credits. If it fails, the original partial response remains.

## Persistence and operations

Apply `db/migrations/20260804_add_generation_budget_audit.sql` before deploying this
code. It adds request-level budget/reasoning audit fields plus response-level terminal
status and stop cause. PostgreSQL startup preflight requires these columns.

`GENERATION_BUDGET_POLICY_ENABLED=true` enables provider-aware budgets and is the
default. Setting it to `false` is the rollback switch: all new profile requests execute
with the historical Quick/2K ceiling while the public contract remains available.
Restart API processes after changing the setting or applying the migration.

See `docs/runbooks/generation-budget-rollout.md` for deployment and rollback checks.
