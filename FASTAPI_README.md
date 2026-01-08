# FastAPI Integration

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure API Keys
Add to `.env`:
```bash
API_KEYS=your-api-key-1,your-api-key-2
```

### 3. Start Server
```bash
# Development (with auto-reload)
python run_server.py --reload

# Production
python run_server.py --host 0.0.0.0 --port 8000
```

## API Endpoints

### Health Check
```bash
curl http://localhost:8000/health
```

### Single Chat
```bash
curl -X POST http://localhost:8000/v1/chat \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "What is Python?",
    "provider": "openai",
    "model": "gpt-4o-mini"
  }'
```

### Multi-Model Compare
```bash
curl -X POST http://localhost:8000/v1/compare \
  -H "X-API-Key: dev-key-1" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain async/await",
    "targets": [
      {"provider": "openai", "model": "gpt-4o-mini"},
      {"provider": "gemini"}
    ]
  }'
```

## Request Schemas

### Chat Request
```json
{
  "prompt": "string (required)",
  "provider": "openai|gemini|deepseek|grok (required)",
  "model": "string (optional)",
  "context": {
    "session_id": "string (optional)",
    "conversation_history": [
      {"role": "user|assistant|system", "content": "string"}
    ]
  },
  "temperature": 0.7,
  "max_tokens": 1000
}
```

### Compare Request
```json
{
  "prompt": "string (required)",
  "targets": [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "gemini"}
  ],
  "timeout_s": 30,
  "temperature": 0.7,
  "max_tokens": 1000
}
```

**Note:** Max 4 targets allowed.

## Testing

```bash
# Run test script (requires server running)
python test_api.py
```

## Architecture

- **server/app.py** - FastAPI app factory
- **server/routes/** - Endpoint handlers
- **server/schemas/** - Pydantic request/response models
- **server/middleware.py** - Request ID middleware
- **server/dependencies.py** - Auth & orchestrator dependencies

## CLI Still Works

The existing CLI is unchanged:
```bash
python main.py
```
