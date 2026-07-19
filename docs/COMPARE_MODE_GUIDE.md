# Compare Mode Usage Guide

## Overview

Compare Mode allows you to send every query to multiple LLM providers simultaneously and compare their responses side-by-side. This is useful for:

- Evaluating response quality across different models
- Finding the fastest model for your use case
- Comparing costs between providers
- Testing prompt effectiveness across models

This guide covers both:
- API compare mode (`POST /v1/compare`, `POST /v1/compare/stream`)
- CLI compare mode (`COMPARE_MODE=true`)
- Browser Compare mode, where `With sources` is enabled by default for new page sessions and can be turned off manually.

The API accepts two or three explicit targets. Subscription enforcement may reduce the effective maximum: Free and Plus allow two targets, while Pro allows three. The four-provider examples below describe the legacy CLI `COMPARE_MODE=true` flow, not the FastAPI request limit.

In database-backed API mode, all target/model entitlements and monthly counters are enforced before providers start. Successful targets settle independently, failed targets release their reserved model-response units, and shared research settles once only when it actually ran. On a streaming disconnect or error, only successful targets whose output started are settled; completed-but-unemitted targets are released.

## Release Notes (2026-02-18)

- FastAPI `POST /v1/compare` now persists compare runs to DB when `DATABASE_URL` is set.
- Each model response in a compare run writes one `llm_requests` + one `llm_responses` row.
- `request_group_id` is now canonical and shared across:
  - API response payload
  - orchestrator compare logs
  - `public.llm_requests.request_group_id`
- API key attribution for compare now uses the same guardrails as chat:
  - mapped key owner is authoritative
  - unmapped key behavior controlled by `AUTO_REGISTER_UNMAPPED_API_KEYS` and `ALLOW_UNMAPPED_API_KEY_PERSIST`
- Required DB migrations for compare persistence:
  - `db/migrations/20260218_llm_requests_api_key_owner_guard.sql`
  - `db/migrations/20260218_add_request_group_id_to_llm_requests.sql`

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
- **Canonical Grouping**: API compare returns one `request_group_id` used consistently in logs and DB persistence
- **Browser Source Default**: The frontend starts Compare with `With sources` on and preserves a user's manual off choice while switching modes in the same page session.
- **Readable Multi-Turn Layout**: One desktop Compare turn fills the available transcript, and desktop/tablet comparisons keep tall visible cards with internal response-body scrolling. Phone-sized mobile uses a segmented model switcher, shows one selected response card at a time in natural page flow, and turns the stuck switcher into a frosted provider-tinted reading cue without shifting model pills horizontally.
- **Shared Prompt Presentation**: Compare prompts use the same right-aligned `You` bubble as Ask mode, including attachment and prompt-optimization states. While Improve is pending, the prompt and optimization status remain visible but model tabs, response cards, and aggregate totals stay hidden; they appear only after optimization resolves and model generation begins. Aggregate Compare totals render separately.
- **New-Turn Reveal**: Submitting a Compare follow-up always smoothly reveals that new question once, even when the user was viewing an older turn. Streaming response growth does not continuously move the transcript, and the UI no longer renders a floating down-arrow jump control.
- **Independent Response Readiness**: Every browser response card shows the shared provider/model logo treatment and owns its own calm loading state. Loading cards show live elapsed time with `Queued`, `Refining prompt`, `Connecting to model`, `Generating response`, or `Finalizing` instead of placeholder zero metrics. The skeleton body disappears when that card streams its first token or returns an error, while slower targets continue showing their own source/improvement-aware loading treatment. Failed cards show elapsed failure time, and completed cards hide unavailable token counts.
- **Compact Compare Composer**: The React composer starts as a single-line prompt, expands only for longer input, and relies on the main Ask/Compare navigation instead of duplicating a mode switch beside Send. On narrow screens, active model chips stay in their options row and scroll horizontally when a third model is added.
- **Responsive Compare Cue**: Active model chips are separated by a decorative opposing-arrows connector instead of a literal `VS` label. Desktop uses a quiet circular medallion; mobile removes the border and background to preserve model-name space inside the horizontal selector scroller.
- **Mobile Model Picker**: Compare model dropdowns render through a fixed-position body portal, keeping every option visible and selectable above the horizontally scrollable mobile model row.
- **Purposeful Empty State**: Before the first turn, Compare mode explains the ask-once, multi-model workflow and the value of comparing accuracy, depth, speed, tone, and usefulness. Three practical examples fill the prompt without submitting or changing the selected models.
- **Controlled Response Rhythm**: Compare card titles, metadata, paragraphs, Markdown headings, and lists use a restrained type scale and tighter spacing so long model outputs remain readable without excessive vertical gaps.

---

**Last Updated:** 2026-06-11
**Applies To:** OpenAI Project v2.0+
