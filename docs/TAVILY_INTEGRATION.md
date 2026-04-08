# Tavily Integration Guide

## Purpose

Tavily is used as the web-research provider for research-enabled Ask/Compare turns.

Primary integration path:

- `tools/web/tavily_client.py`
- `tools/web/tavily_service.py`
- `tools/web/factory.py`
- `tools/web/intent.py`
- `tools/web/research_pack.py`

## Runtime Modes

At route level, API contract uses `routing.research_mode` as a boolean:

- `false` -> no web research for this turn
- `true` -> research-enabled flow

Inside orchestration, research state tracks behavior as:

- `off`
- `auto`
- `on`

Current behavior highlights:

- `on` performs a fresh search for the current turn.
- In `on`, local research cache reuse is bypassed.
- If sanitized query is empty in `on`, system falls back to raw prompt.
- Source metadata is normalized into `web_source_items` on responses.
- Missing provider timestamp values are normalized to server UTC ISO timestamps.

## Configuration

Set API key in environment:

```ini
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxxxxxxxx
```

Install dependency:

```bash
pip install tavily-python
```

## Validation

Recommended checks:

- `tests/test_tavily_client.py`
- `tests/test_research_pack.py`
- `tests/test_routing_regression.py`

## Notes

- This integration is API-first; do not rely on legacy CLI-only flows when validating web research behavior.
- For end-to-end behavior, use the browser E2E suite (`npm run --prefix e2e test`) and inspect response source chips + persisted metadata.

---

Last updated: 2026-03-19
