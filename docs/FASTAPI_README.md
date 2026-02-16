# FastAPI Integration

## Quick Start

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure API auth keys in `.env`:
```ini
API_KEYS=dev-key-1,dev-key-2
```

3. Start server:
```bash
python run_server.py --reload
```

4. Open docs:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Endpoints

- `GET /health`
- `POST /v1/chat`
- `POST /v1/compare`

## Authentication

All protected endpoints require:
- Header: `X-API-Key: <key-from-API_KEYS>`

If key is missing/invalid, response is `401`.

## Chat API

### Request Shape

```json
{
  "prompt": "string (required)",
  "provider": "openai|gemini|deepseek|grok (optional in smart mode)",
  "model": "string (optional)",
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ]
  },
  "temperature": 0.7,
  "max_tokens": 1000,
  "research_mode": "off|auto|on",
  "routing_mode": "smart|cheap|strong",
  "routing_constraints": {
    "max_cost_usd": 0.01,
    "max_total_latency_ms": 8000,
    "preferred_provider": "openai",
    "allowed_providers": ["openai", "gemini"],
    "min_context_limit": 128000,
    "json_only": true,
    "strict_format": true
  }
}
```

### Notes

- `provider` can be omitted when using smart routing (`routing_mode=smart|cheap|strong`).
- If both `provider` and `model` are provided, explicit model selection is used and validated against `config/model_registry.yaml`.
- Unknown/disabled explicit model returns `bad_request`.

### Example: Auto Routing

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Fix this stack trace and propose a patch",
    "routing_mode": "smart"
  }'
```

### Example: Explicit Model

```bash
curl -X POST http://127.0.0.1:8000/v1/chat \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain decorators in Python",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }'
```

## Compare API

### Request Shape

```json
{
  "prompt": "string (required)",
  "targets": [
    {"provider": "openai", "model": "gpt-4.1-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"}
  ],
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ]
  },
  "timeout_s": 30,
  "temperature": 0.7,
  "max_tokens": 1000,
  "research_mode": "off|auto|on"
}
```

### Rules

- Min 2 targets, max 4 targets.
- Context is rejected when targets > 2.

### Example

```bash
curl -X POST http://127.0.0.1:8000/v1/compare \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Summarize tradeoffs of sync vs async IO",
    "targets": [
      {"provider": "openai", "model": "gpt-4.1-mini"},
      {"provider": "deepseek", "model": "deepseek-chat"}
    ]
  }'
```

## Guardrails

Applied in `server/utils.py`:
- Conversation history trimmed to last 10 messages.
- Total context chars capped at 8000.
- `max_tokens` clamped to 1024.

## What API Does Not Enforce (Current)

- Daily token/cost caps (`DAILY_TOKEN_CAP`, `DAILY_COST_CAP`) are enforced in CLI (with DB path), not in API routes.

## Testing

Run contract/guardrail tests:
```bash
pytest tests/test_fastapi_contract_and_guardrails.py -v
```

Run integration tests (server must be running):
```bash
pytest tests/test_api.py -v
```

## Relevant Files

- `server/app.py`
- `server/routes/chat.py`
- `server/routes/compare.py`
- `server/routes/health.py`
- `server/schemas/requests.py`
- `server/schemas/responses.py`
- `server/dependencies.py`
- `server/utils.py`
- `orchestrator/core.py`

---

Last updated: 2026-02-16
