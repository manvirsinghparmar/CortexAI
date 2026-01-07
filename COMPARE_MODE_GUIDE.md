# Compare Mode Usage Guide

## Overview

Compare Mode allows you to send every query to multiple LLM providers simultaneously and compare their responses side-by-side. This is useful for:

- Evaluating response quality across different models
- Finding the fastest model for your use case
- Comparing costs between providers
- Testing prompt effectiveness across models

## How to Enable Compare Mode

### Step 1: Edit your `.env` file

Add or update this line:
```bash
COMPARE_MODE=true
```

To disable compare mode and return to single-model mode:
```bash
COMPARE_MODE=false
```

### Step 2: Configure API Keys

Make sure you have at least one API key configured in `.env`:
```bash
OPENAI_API_KEY=sk-...
GOOGLE_GEMINI_API_KEY=AIza...
DEEPSEEK_API_KEY=sk-...
GROK_API_KEY=xai-...
```

The system will automatically use all configured providers.

### Step 3: Customize Comparison Targets (Optional)

Edit `config/config.py` to customize which models are compared:
```python
COMPARE_TARGETS = [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
    {"provider": "deepseek", "model": "deepseek-chat"},
    {"provider": "grok", "model": "grok-4-latest"},
]
```

### Step 4: Run the Application

```bash
python main.py
```

You'll see:
```
=== Compare Mode Active ===
Queries will be sent to 4 models simultaneously

=== AI Chat (Compare Mode, Multi-turn Context Enabled) ===
Type 'exit' to quit, 'stats' to see token usage, or 'help' for commands

You: _
```

## Usage Examples

### Example 1: Simple Query

```
You: What is Python?

=== Comparison Results ===

[1] OPENAI/gpt-4o-mini
    Latency: 347ms | Tokens: 45 | Cost: $0.000023
    Response: Python is a high-level, interpreted programming language...

[2] GEMINI/gemini-2.5-flash-lite
    Latency: 289ms | Tokens: 52 | Cost: $0.000015
    Response: Python is a versatile programming language known for...

[3] DEEPSEEK/deepseek-chat
    Latency: 412ms | Tokens: 38 | Cost: $0.000008
    Response: Python is an easy-to-learn programming language...

[4] GROK/grok-4-latest
    Latency: 523ms | Tokens: 61 | Cost: $0.000041
    Response: Python is a powerful, interpreted language that...

=== Summary ===
Successful: 4/4
Failed: 0/4
Total Tokens: 196
Total Cost: $0.000087
Session Total Cost: $0.000087
```

### Example 2: Conversation with Context

Compare mode maintains conversation history just like single mode:

```
You: What is machine learning?
[All 4 models respond with explanations]

You: Can you give me a simple example?
[All 4 models respond with examples, referencing previous context]
```

## Key Features

### 1. Automatic Conversation History

All models receive the full conversation context, so follow-up questions work naturally.

### 2. Session Statistics Tracking

All responses update your session statistics:
```
You: stats

=== Session Statistics ===
Requests: 8  (includes all model responses)
Total tokens: 372
Total cost: $0.000174
```

### 3. Error Handling

If some models fail, the system continues with successful responses:
```
[1] OPENAI/gpt-4o-mini
    Response: Successfully completed...

[2] GEMINI/gemini-2.5-flash-lite
    [ERROR] timeout: Request timed out after 60s

[3] DEEPSEEK/deepseek-chat
    Response: Successfully completed...

=== Summary ===
Successful: 2/3
Failed: 1/3
```

### 4. Help Command Shows Current Mode

```
You: help

=== Available Commands ===
help          - Show this help message
stats         - Show token usage statistics
/reset        - Clear conversation history
/history      - Show recent conversation
exit/quit     - Exit the program

Current Mode: Compare Mode (COMPARE_MODE=true)
All prompts are sent to multiple models for comparison
```

## Switching Between Modes

To switch from Compare Mode to Single Model Mode:

1. Edit `.env`:
   ```bash
   COMPARE_MODE=false
   MODEL_TYPE=openai  # or gemini, deepseek, grok
   ```

2. Restart the application:
   ```bash
   python main.py
   ```

You'll see:
```
Initialized OpenAI client with model: gpt-3.5-turbo

=== AI Chat (Single Model, Multi-turn Context Enabled) ===
Type 'exit' to quit, 'stats' to see token usage, or 'help' for commands

You: _
```

## Tips

1. **Cost Awareness**: Compare mode costs more since you're calling multiple APIs. Check `stats` regularly.

2. **Performance**: The slowest model determines response time. Consider removing slow models from `COMPARE_TARGETS`.

3. **API Rate Limits**: Each provider has rate limits. If one fails, others still work.

4. **Context Length**: All models receive the same conversation history. Long conversations may hit token limits on some models.

5. **Response Selection**: The first successful response is added to conversation history for context continuity.

## Troubleshooting

### "ERROR: COMPARE_MODE=true but no API keys configured"

Solution: Add at least one API key to `.env`.

### Some models always fail

Solution: Check that API keys are valid and have sufficient credits.

### Responses are too slow

Solution: Remove slow models from `COMPARE_TARGETS` in `config/config.py`.

### Want to compare only 2 models

Solution: Edit `COMPARE_TARGETS` to include only the models you want:
```python
COMPARE_TARGETS = [
    {"provider": "openai", "model": "gpt-4o-mini"},
    {"provider": "gemini", "model": "gemini-2.5-flash-lite"},
]
```

## Architecture Notes

- **Concurrent Execution**: All model calls run in parallel for speed
- **Timeout Protection**: Each model has a 60-second timeout
- **Immutable Results**: All responses are stored immutably for consistency
- **Order Preservation**: Results appear in the order configured, not completion order
- **Graceful Degradation**: System continues even if some models fail

---

**Last Updated:** 2026-01-06
**Applies To:** OpenAI Project v2.0+