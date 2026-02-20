# CortexAI UI

Frontend for FastAPI chat and compare flows.

## Scope

- Uses `POST /v1/chat` for single mode.
- Uses `POST /v1/compare` for compare mode.
- Default mode is single chat with smart routing ON.
- Compare mode is fixed to 2 models in UI.
- Prompt Optimization and Research Mode toggles are exposed.

## Run

1. Start backend:

```bash
python run_server.py --reload
```

2. Serve this folder:

```bash
cd ui
python -m http.server 8080
```

3. Open:

`http://127.0.0.1:8080`

## API Base Resolution

The UI resolves base URL in this order:

1. `localStorage["cortex_api_base_url"]`
2. If current page is on port `8000`, use `<origin>/v1`
3. Fallback `http://127.0.0.1:8000/v1`

Override example:

```js
localStorage.setItem("cortex_api_base_url", "http://127.0.0.1:8000/v1");
```

## Controls to Payload

- Smart Routing toggle (single mode only):
  - ON: no explicit provider/model
  - OFF: send explicit `provider` and `model`
- Prompt Optimization toggle:
  - maps to `prompt_optimization_enabled`
- Research Mode toggle:
  - maps to `research_mode` (`on` or `off`)

All requests include:
- `prompt`
- `context.conversation_history` (last 10 messages)

UI intentionally does not send `context.session_id` to avoid session FK persistence issues.

## Compare Mode Rules

- Smart routing control is hidden.
- Exactly 2 targets are sent.
- `timeout_s` is set to `60`.

## Request IDs

- Response cards show `request_id` from backend.
- Use this ID in DB checks:

```sql
SELECT r.*, resp.*
FROM public.llm_requests r
LEFT JOIN public.llm_responses resp ON resp.llm_request_id = r.id
WHERE r.request_id = 'your-request-id';
```

---

Last updated: 2026-02-19
