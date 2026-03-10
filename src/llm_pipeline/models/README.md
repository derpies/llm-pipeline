# models/

LLM provider factory, token tracking, rate limiting, and dry-run simulation.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `llm.py` | `get_llm(provider, model, role)` — role-based model selection, supports Anthropic/OpenAI/dry-run |
| `dry_run.py` | Dry-run LLM that simulates calls without hitting providers. Canned responses per agent role. Full pipeline exercisable for testing |
| `token_tracker.py` | Thread-safe token tracker with per-model cost computation. Price table for Haiku/Opus/Sonnet/GPT-4o |
| `rate_limiter.py` | Sliding-window rate limiter (60-sec window). `acquire()` blocks until capacity available |

## Key Concepts

### `get_llm()` — role-based model selection

Every agent gets its LLM instance through one function with three ways to control the model:

```python
from llm_pipeline.models.llm import get_llm

# 1. Default: uses llm_model from config (claude-sonnet-4)
llm = get_llm()

# 2. Role-based: uses per-agent model from config
llm = get_llm(role="curator")        # → claude-haiku-4-5
llm = get_llm(role="investigator")   # → claude-sonnet-4
llm = get_llm(role="orchestrator")   # → claude-sonnet-4

# 3. Explicit override: ignores config entirely
llm = get_llm(model="claude-opus-4-20250514")
```

Priority: **explicit model > role-based > default**

### Current role → model mapping

| Role | Config field | Default model |
|------|-------------|---------------|
| `orchestrator` | `model_orchestrator` | claude-sonnet-4 |
| `investigator` | `model_investigator` | claude-sonnet-4 |
| `investigator_deep` | `model_investigator_deep` | claude-opus-4 |
| `synthesizer` | `model_synthesizer` | claude-sonnet-4 |
| `curator` | `model_curator` | claude-haiku-4-5 |
| _(none / chat)_ | `llm_model` | claude-sonnet-4 |

### Adding a new role

1. **`config.py`** — add `model_my_agent: str = "claude-sonnet-4-20250514"`
2. **`models/llm.py`** — add to `_ROLE_MODEL_MAP`: `"my_agent": "model_my_agent"`
3. **Your agent** — call `get_llm(role="my_agent")`

The model can then be changed via env var `MODEL_MY_AGENT=...` without touching code.

## Contracts

- **Imports from**: `config` (API keys, model names, provider selection)
- **Exports**: `get_llm()`, `TokenTracker`/`get_tracker()`, `RateLimiter`/`get_rate_limiter()`
- **Consumed by**: every agent (LLM calls), `agents/orchestrator.py` (cost tracking), `tools/` (rate limiting)
