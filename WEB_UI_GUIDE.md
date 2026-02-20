# CortexAI Web UI Guide

This guide documents the current UI flow in `ui/` with FastAPI backend integration.

## What Changed

- UI now calls FastAPI directly (`/v1/chat`, `/v1/compare`).
- Single mode is default and uses smart routing by default.
- Compare mode is fixed to 2 models in UI.
- Prompt Optimization and Research Mode are user toggles.
- Smart routing toggle is not shown in compare mode.
- Response cards show backend `request_id`.
- UI context sends conversation history only (no `session_id`) to avoid DB FK persistence issues.

## Run End to End

1. Start FastAPI server:

```bash
python run_server.py --reload
```

2. Serve the UI (any static server):

```bash
cd ui
python -m http.server 8080
```

3. Open:

`http://127.0.0.1:8080`

Default backend target is `http://127.0.0.1:8000/v1`.

## API Base URL Resolution

The UI resolves API base like this:

1. `localStorage["cortex_api_base_url"]` (if set)
2. If page is served from port `8000`: `<current-origin>/v1`
3. Fallback: `http://127.0.0.1:8000/v1`

Set custom API base in browser console:

```js
localStorage.setItem("cortex_api_base_url", "http://127.0.0.1:8000/v1");
```

## UI Mode Behavior

### Single Chat Mode (default)

- Endpoint: `POST /v1/chat`
- Default behavior: smart routing ON
  - payload includes `routing_mode: "smart"`
  - no explicit provider/model
- If smart routing is toggled OFF:
  - payload includes `provider` and `model` from selected model dropdown
- Prompt Optimization toggle maps to `prompt_optimization_enabled`
- Research Mode toggle maps to `research_mode` (`on`/`off`)

### Compare Mode

- Endpoint: `POST /v1/compare`
- UI always sends exactly 2 targets.
- Smart routing toggle is hidden.
- Prompt Optimization toggle maps to `prompt_optimization_enabled`
- Research Mode toggle maps to `research_mode` (`on`/`off`)
- `timeout_s` is sent as `60`.

## Payload Mapping

### Single mode payload (smart ON)

```json
{
  "prompt": "user text",
  "research_mode": "off",
  "prompt_optimization_enabled": false,
  "routing_mode": "smart",
  "context": {
    "conversation_history": [
      {"role": "user", "content": "..." }
    ]
  }
}
```

### Single mode payload (smart OFF)

```json
{
  "prompt": "user text",
  "research_mode": "on",
  "prompt_optimization_enabled": true,
  "routing_mode": "smart",
  "provider": "openai",
  "model": "gpt-4o-mini",
  "context": {
    "conversation_history": []
  }
}
```

### Compare mode payload

```json
{
  "prompt": "user text",
  "research_mode": "off",
  "prompt_optimization_enabled": false,
  "timeout_s": 60,
  "targets": [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"}
  ],
  "context": {
    "conversation_history": []
  }
}
```

## Conversation Context Handling

- UI keeps local `conversationHistory`.
- On each request, only the last 10 messages are sent.
- UI intentionally does not send `context.session_id`.
  - Reason: avoid FK violations when DB persistence validates `llm_requests.session_id`.

## Request IDs and DB Checks

- UI response cards display backend `request_id`.
- Use that value to query DB:

```sql
SELECT r.*, resp.*
FROM public.llm_requests r
LEFT JOIN public.llm_responses resp ON resp.llm_request_id = r.id
WHERE r.request_id = 'your-request-id';
```

Failure reason query:

```sql
SELECT
  r.request_id,
  r.provider,
  r.model,
  resp.finish_reason,
  resp.error_type,
  resp.error_message
FROM public.llm_requests r
JOIN public.llm_responses resp ON resp.llm_request_id = r.id
WHERE r.request_id = 'your-request-id';
```

## Known Legacy Path

- `web_server.py` is legacy Flask (`/api/chat`) and not the default UI backend for this flow.
- Current UI path is FastAPI `/v1/chat` and `/v1/compare`.

---

Last updated: 2026-02-19
