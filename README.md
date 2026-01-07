READ# AI Chat Interface

A Python command-line application that provides an interactive chat interface with multiple AI providers, featuring **enterprise-ready structured JSON logging**, **unified response contract**, token usage tracking, and real-time cost estimation.

## Features

### Core Features
- **Multi-Provider Support**: OpenAI, Google Gemini, DeepSeek, and Grok (X.AI)
- **Unified Response Contract**: Provider-agnostic response format with immutable dataclasses
- **Interactive CLI**: User-friendly command-line interface with loading animations
- **Token Tracking**: Real-time monitoring of token usage (prompt, completion, and total)
- **Cost Calculation**: Automatic cost estimation based on current pricing for all models
- **Request Tracking**: Unique request IDs (UUID) for distributed tracing
- **Latency Metrics**: End-to-end request timing for performance monitoring

### Enterprise Features
- **Structured JSON Logging**: Production-ready logging system with rotating file handlers
- **Centralized Log Aggregation Ready**: JSON format compatible with ELK Stack, Grafana Loki, Datadog
- **Error Normalization**: Standardized error codes across all providers
- **No Exceptions Bubble Up**: All errors returned as structured responses
- **Session Statistics**: View cumulative token usage and costs during your session
- **Environment-Based Configuration**: Secure API key and logging management using `.env` files

## Prerequisites

- Python 3.8 or higher
- API key for your chosen provider:
  - OpenAI API key (for GPT models)
  - Google Gemini API key (for Gemini models)
  - DeepSeek API key (for DeepSeek models)
  - Grok API key (for Grok models from X.AI)

## Installation

1. **Clone the repository** (or create a new directory):
   ```bash
   cd OpenAIProject
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: .\venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   cp .env.example .env
   ```

5. **Edit `.env` file** with your API keys and configuration:
   ```ini
   # Choose: 'openai', 'gemini', 'deepseek', or 'grok'
   MODEL_TYPE=deepseek

   # Add your API key(s)
   OPENAI_API_KEY=your_openai_api_key_here
   GOOGLE_GEMINI_API_KEY=your_gemini_api_key_here
   DEEPSEEK_API_KEY=your_deepseek_api_key_here
   GROK_API_KEY=your_grok_api_key_here

   # Set default models (optional)
   DEFAULT_OPENAI_MODEL=gpt-3.5-turbo
   DEFAULT_GEMINI_MODEL=gemini-2.5-flash-lite
   DEFAULT_DEEPSEEK_MODEL=deepseek-chat
   DEFAULT_GROK_MODEL=grok-4-latest

   # Logging configuration (NEW)
   LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR, CRITICAL
   LOG_TO_CONSOLE=false              # Keep console clean for chat
   ```

## Usage

1. **Run the application**:
   ```bash
   python main.py
   ```

2. **Available commands** during chat:
   - Type your message and press Enter to get a response
   - `stats` - View token usage and cost statistics for current session
   - `help` - Show available commands
   - `exit` or `quit` - End the session
   - `Ctrl+C` - Exit at any time

3. **Example session**:
   ```
   === AI Chat ===
   Type 'exit' to quit, 'stats' to see token usage, or 'help' for commands

   You: Hello, how are you?
   Thinking /

   AI: I'm doing well, thank you for asking! How can I help you today?
   [Tokens: 45 | Cost: $0.000023 | Latency: 347ms]

   You: stats

   === Session Statistics ===
   Requests: 1
   Prompt tokens: 12
   Completion tokens: 33
   Total tokens: 45

   Input cost: $0.000003
   Output cost: $0.000020
   Total cost: $0.000023

   Last updated: 2026-01-04T00:45:12.123456
   ```

## Unified Response Contract

All provider clients return a standardized `UnifiedResponse` object:

```python
from api.openai_client import OpenAIClient

client = OpenAIClient(api_key="your-key")
resp = client.get_completion("What is Python?")

# Access standardized fields (works for ALL providers)
print(resp.text)                    # Assistant response
print(resp.token_usage.total_tokens)  # Token count
print(resp.estimated_cost)          # Pre-calculated cost
print(resp.latency_ms)              # Request latency
print(resp.request_id)              # Unique UUID
print(resp.provider)                # "openai"
print(resp.model)                   # "gpt-3.5-turbo"
print(resp.finish_reason)           # "stop"

# Error handling
if resp.is_error:
    print(f"Error: {resp.error.code} - {resp.error.message}")
    if resp.error.retryable:
        # Implement retry logic
        pass
```

**Key Benefits:**
- ✅ **Provider-agnostic**: Same interface for all providers
- ✅ **No exceptions**: Errors returned as structured responses
- ✅ **Type-safe**: Immutable frozen dataclasses
- ✅ **Request tracking**: UUID for distributed tracing
- ✅ **Pre-calculated costs**: No separate calculation needed
- ✅ **Standardized errors**: 6 error codes (timeout, auth, rate_limit, bad_request, provider_error, unknown)

See [UNIFIED_RESPONSE_CONTRACT.md](./UNIFIED_RESPONSE_CONTRACT.md) for complete documentation.

## Logging System

### Enterprise-Ready Structured Logging

All logs are written in **JSON format** to `logs/` directory:

| File | Content | Format | Purpose |
|------|---------|--------|---------|
| `logs/app.log` | INFO and above | JSON | All application events |
| `logs/error.log` | ERROR and above | JSON | Errors only (for alerts) |
| `logs/debug.log` | Everything | JSON | Debug info (when LOG_LEVEL=DEBUG) |

**Features:**
- 🔄 **Automatic rotation**: 10MB max per file, 5 backups
- 📊 **JSON structured**: Ready for ELK, Loki, Datadog
- 🔒 **Privacy-first**: No user messages or API keys logged
- 🎯 **Clean console**: Logs don't clutter chat interface
- ⚙️ **Environment config**: Control via LOG_LEVEL and LOG_TO_CONSOLE

### Log Configuration

```bash
# .env file
LOG_LEVEL=INFO          # DEBUG shows everything, INFO for production
LOG_TO_CONSOLE=false    # true = errors also in console (stderr)
```

### What Gets Logged

✅ **Application lifecycle** (startup, shutdown, model initialization)
✅ **API operations** (completions, token counts, costs, latency)
✅ **Errors** (with error codes, retryability, request IDs)
✅ **Request tracking** (unique request IDs for tracing)
❌ **NOT logged**: User messages, AI responses, API keys

### Viewing Logs

```bash
# Real-time monitoring
tail -f logs/app.log | python -m json.tool

# Search for errors
grep '"level": "ERROR"' logs/app.log | python -m json.tool

# Find specific request
grep '"request_id": "abc-123"' logs/app.log | python -m json.tool
```

### Integration with Log Aggregation

The JSON format is ready for enterprise logging systems:

- **Grafana Loki**: Use Promtail to ship logs
- **ELK Stack**: Use Filebeat or Logstash
- **Datadog**: Configure Datadog Agent
- **Splunk**: Use Splunk Forwarder

See [LOGGING.md](./LOGGING.md) for complete documentation and integration guides.

## Supported Models

### OpenAI
- **GPT-4**: `gpt-4`, `gpt-4-turbo`, `gpt-4-0125-preview`
- **GPT-3.5**: `gpt-3.5-turbo`, `gpt-3.5-turbo-0125`
- **Pricing**: $0.50-$60.00 per million tokens

### Google Gemini
- **Gemini 2.5**: `gemini-2.5-flash-lite`
- **Gemini 1.5**: `gemini-1.5-flash`, `gemini-1.5-pro`
- **Pricing**: $0.05-$5.00 per million tokens

### DeepSeek
- **DeepSeek V3**: `deepseek-chat` (general conversation)
- **DeepSeek R1**: `deepseek-reasoner` (advanced reasoning)
- **Pricing**: $0.27-$2.19 per million tokens

### Grok (X.AI)
- **Grok 4**: `grok-4-latest` (latest model)
- **Grok 2**: `grok-2`, `grok-2-mini`
- **Pricing**: $0.50-$15.00 per million tokens

## Project Structure

```
OpenAIProject/
├── .env                           # Your configuration (not in git)
├── .env.example                   # Example configuration template
├── .gitignore                     # Git ignore rules
├── README.md                      # This file
├── LOGGING.md                     # Logging system documentation
├── UNIFIED_RESPONSE_CONTRACT.md   # Response contract documentation
├── BILLING_ARCHITECTURE.md        # Billing system design (future feature)
├── PROJECT_MAP.md                 # Project overview map
├── CHANGELOG.md                   # Version history and changes
├── requirements.txt               # Python dependencies
├── pytest.ini                     # Pytest configuration
├── main.py                        # Main application entry point
├── test_conversation.py           # Conversation testing utility
│
├── models/                        # Response models
│   ├── __init__.py
│   └── unified_response.py        # UnifiedResponse, TokenUsage, NormalizedError
│
├── api/                           # API client implementations
│   ├── base_client.py             # Abstract base with contract enforcement
│   ├── openai_client.py           # OpenAI API client
│   ├── google_gemini_client.py    # Google Gemini client
│   ├── deepseek_client.py         # DeepSeek API client
│   └── grok_client.py             # Grok (X.AI) API client
│
├── config/                        # Configuration management
│   ├── __init__.py
│   ├── config.py                  # Configuration class
│   └── pricing.py                 # Model pricing data
│
├── context/                       # Context management
│   ├── __init__.py
│   └── conversation_manager.py    # Conversation history management
│
├── utils/                         # Utility modules
│   ├── __init__.py
│   ├── logger.py                  # Structured JSON logging
│   ├── token_tracker.py           # Token usage tracking
│   ├── cost_calculator.py         # Cost calculation logic
│   ├── model_utils.py             # Model utility functions
│   └── GeminiAvailableModels.py   # Gemini model listing utility
│
├── logs/                          # Log files (gitignored)
│   ├── .gitignore
│   ├── app.log                    # Application logs (JSON)
│   ├── error.log                  # Error logs (JSON)
│   └── debug.log                  # Debug logs (JSON, if enabled)
│
└── tests/                         # Test suite
    ├── __init__.py
    ├── README.md                  # Test documentation
    ├── conftest.py                # Pytest configuration
    ├── test_model_utils.py        # Model utility tests
    └── test_unified_response_contract.py  # Contract tests
```

## Architecture

### Unified Response Contract (NEW)

All API clients return `UnifiedResponse` - a locked contract ensuring consistency:

```python
@dataclass(frozen=True)
class UnifiedResponse:
    request_id: str              # UUID for tracking
    text: str                    # Assistant response
    provider: str                # Provider name
    model: str                   # Model used
    latency_ms: int              # Request time
    token_usage: TokenUsage      # Token counts
    estimated_cost: float        # Calculated cost
    finish_reason: str           # "stop" | "length" | "tool" | "content_filter" | "error"
    error: NormalizedError       # Structured error (if failed)
```

**Benefits:**
- No provider lock-in - switch providers without changing code
- Consistent error handling across all providers
- Request tracking with unique IDs
- Pre-calculated costs
- Immutable and type-safe

### API Clients

All API clients inherit from `BaseAIClient` and implement:
- `get_completion()` → `UnifiedResponse` (NEVER raises exceptions)
- `list_available_models()` → Displays available models

**Error Handling Contract:**
- All exceptions caught and returned as `UnifiedResponse` with `error` field
- Standardized error codes: `timeout`, `auth`, `rate_limit`, `bad_request`, `provider_error`, `unknown`
- Each error has `retryable` flag

### Token Tracking

`TokenTracker` class tracks:
- Number of requests
- Prompt (input) tokens
- Completion (output) tokens
- Total tokens used
- **NEW**: Accepts `UnifiedResponse` directly or dict

### Cost Calculation

`CostCalculator` class maintains **separation from token tracking**:
- Stores pricing information for all models
- Calculates per-request costs
- Maintains cumulative session costs
- Formats costs for display
- Integrated into `UnifiedResponse` (pre-calculated)

### Logging System (NEW)

`LoggerConfig` class provides:
- Structured JSON logging with rotating file handlers
- Environment-based configuration (LOG_LEVEL, LOG_TO_CONSOLE)
- Clean separation: logs to files, chat stays clean
- Ready for centralized log aggregation (ELK, Loki, Datadog)

**Design Principle**: Token tracking, cost calculation, and logging are separate modules that work independently, maintaining clean abstraction.

## Configuration Options

### Environment Variables

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `MODEL_TYPE` | AI provider to use | `openai`, `gemini`, `deepseek`, `grok` | `openai` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` | - |
| `GOOGLE_GEMINI_API_KEY` | Gemini API key | `AIza...` | - |
| `DEEPSEEK_API_KEY` | DeepSeek API key | `sk-...` | - |
| `GROK_API_KEY` | Grok API key | `xai-...` | - |
| `DEFAULT_OPENAI_MODEL` | Default OpenAI model | `gpt-3.5-turbo` | `gpt-3.5-turbo` |
| `DEFAULT_GEMINI_MODEL` | Default Gemini model | `gemini-2.5-flash-lite` | `gemini-1.5-flash` |
| `DEFAULT_DEEPSEEK_MODEL` | Default DeepSeek model | `deepseek-chat` | `deepseek-chat` |
| `DEFAULT_GROK_MODEL` | Default Grok model | `grok-4-latest` | `grok-4-latest` |
| **`LOG_LEVEL`** (NEW) | Logging verbosity | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` | `INFO` |
| **`LOG_TO_CONSOLE`** (NEW) | Log errors to console | `true`, `false` | `false` |

### Switching Providers

To switch between AI providers:
1. Open `.env` file
2. Change `MODEL_TYPE` to your desired provider
3. Ensure the corresponding API key is set
4. (Optional) Set the default model for that provider
5. Restart the application

## Getting API Keys

### OpenAI
1. Visit [OpenAI Platform](https://platform.openai.com/)
2. Sign up or log in
3. Navigate to API Keys section
4. Create a new secret key

### Google Gemini
1. Visit [Google AI Studio](https://makersuite.google.com/)
2. Sign in with Google account
3. Click "Get API Key"
4. Create an API key

### DeepSeek
1. Visit [DeepSeek Platform](https://platform.deepseek.com/)
2. Sign up or log in
3. Navigate to API Keys
4. Generate a new API key

### Grok (X.AI)
1. Visit [X.AI Console](https://console.x.ai/)
2. Sign up or log in
3. Navigate to API section
4. Create a new API key

## Troubleshooting

### Common Issues

**ModuleNotFoundError: No module named 'dotenv'**
```
ModuleNotFoundError: No module named 'dotenv'
```
**Solution**: Install the required packages:
```bash
pip install -r requirements.txt
```

**Python 3.14 Compatibility Error (proxies)**
```
Client.__init__() got an unexpected keyword argument 'proxies'
```
**Cause**: The `openai` package version 1.3.0 is incompatible with Python 3.14 and newer `httpx` versions.
**Solution**: Upgrade the OpenAI package:
```bash
pip install --upgrade openai
```

**Missing Google Module**
```
No module named 'google'
```
**Cause**: Google API packages are not installed (required for Gemini models).
**Solution**: Install the Google packages:
```bash
pip install google-genai google-api-python-client google-auth
```

**Virtual Environment Sync Issues (Multiple IDEs)**

If code works in one IDE (e.g., PyCharm) but fails in another (e.g., VS Code terminal), you likely have **multiple virtual environments** with different packages installed.

**Diagnosis**: Check which venv each IDE is using:
```bash
# Check Python version and location
python --version
where python  # Windows
which python  # Linux/Mac
```

**Solution**: Either:
1. Use the same virtual environment in all IDEs, or
2. Sync packages between environments:
```bash
pip install -r requirements.txt
```

---

**Missing API Key Error**
```
Error: OPENAI_API_KEY not found in environment variables
```
**Solution**: Add your API key to the `.env` file for the selected provider.

**Authentication Error**
```
[ERROR] AUTH: Authentication failed: 401 Unauthorized
(This error is not retryable)
```
**Solution**: Verify your API key is correct and active. Check error code for details.

**Rate Limit Error**
```
[ERROR] RATE_LIMIT: Rate limit exceeded: 429 Too Many Requests
(This error may be retryable)
```
**Solution**: Wait and retry, or upgrade your plan.

**Timeout Error**
```
[ERROR] TIMEOUT: Request timed out
(This error may be retryable)
```
**Solution**: Retry the request or check network connection.

**Model Not Available**
```
[ERROR] BAD_REQUEST: Invalid request: Model 'xyz' not found
```
**Solution**: Check that the model name is correct and you have access to it.

**Logs Too Large**
```
logs/app.log is taking up space
```
**Solution**: Logs auto-rotate at 10MB with 5 backups. Reduce LOG_LEVEL to WARNING or ERROR if needed.

### Debug Mode

Enable debug logging to see everything:
```bash
# .env
LOG_LEVEL=DEBUG
```

Then check `logs/debug.log` for detailed information.

### Getting Help

If you encounter issues:
1. Check the error code and message displayed
2. Look for retryable flag (indicates if retry is appropriate)
3. Check `logs/error.log` for detailed error context
4. Verify your `.env` configuration
5. Ensure your API key has sufficient credits
6. Check the provider's status page for outages

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run only unified response contract tests (NEW)
pytest tests/test_unified_response_contract.py -v

# Run with coverage
pytest --cov=models --cov=api --cov=utils --cov-report=html

# Run specific test
pytest tests/test_unified_response_contract.py::TestProviderContractCompliance -v
```

**Test Results**: 14/15 tests passing (93% pass rate)

### Adding a New Provider

1. Create a new client in `api/` that inherits from `BaseAIClient`
2. Implement required method: `get_completion()` → returns `UnifiedResponse`
3. **IMPORTANT**: Never raise exceptions - catch all and return `UnifiedResponse` with error
4. Use helper methods: `_generate_request_id()`, `_measure_latency()`, `_normalize_error()`, `_normalize_finish_reason()`
5. Add pricing information to `config/pricing.py`
6. Update `main.py` to include the new provider in `initialize_client()`
7. Update `.env.example` with new configuration options
8. Add tests to `tests/test_unified_response_contract.py`

**Example:**
```python
class NewProviderClient(BaseAIClient):
    def get_completion(self, prompt: str, *, save_full: bool = False, **kwargs) -> UnifiedResponse:
        request_id = self._generate_request_id()
        start_time = time.time()

        try:
            # Make API call
            response = self.client.create(...)

            return UnifiedResponse(
                request_id=request_id,
                text=response.text,
                provider="newprovider",
                model=self.model_name,
                latency_ms=self._measure_latency(start_time),
                token_usage=TokenUsage(...),
                estimated_cost=self.cost_calculator.calculate_cost(...),
                finish_reason=self._normalize_finish_reason(response.finish_reason),
                error=None
            )
        except Exception as e:
            return self._create_error_response(
                request_id=request_id,
                error=self._normalize_error(e),
                latency_ms=self._measure_latency(start_time)
            )
```

## Documentation

- [UNIFIED_RESPONSE_CONTRACT.md](./UNIFIED_RESPONSE_CONTRACT.md) - Complete response contract documentation
- [LOGGING.md](./LOGGING.md) - Logging system documentation and integration guides
- [BILLING_ARCHITECTURE.md](./BILLING_ARCHITECTURE.md) - Billing system architecture design (future feature)
- [PROJECT_MAP.md](./PROJECT_MAP.md) - Project overview and quick reference map
- [CHANGELOG.md](./CHANGELOG.md) - Version history and change log
- [tests/README.md](./tests/README.md) - Test suite documentation

## License

This project is open source and available under the MIT License.

## Acknowledgments

- OpenAI for GPT models
- Google for Gemini models
- DeepSeek for DeepSeek models
- X.AI for Grok models

---

**Last Updated**: January 2026
**Version**: 2.0 (Unified Response Contract + Enterprise Logging)
