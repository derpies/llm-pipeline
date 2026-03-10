# models/

LLM provider factory.

## `llm.py` — `get_llm()`

This is how every agent gets its LLM instance. One function, three ways to control the model:

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

## Adding a new role

Three places to touch:

1. **`config.py`** — add the setting:
   ```python
   model_my_agent: str = "claude-sonnet-4-20250514"
   ```

2. **`models/llm.py`** — add to `_ROLE_MODEL_MAP`:
   ```python
   _ROLE_MODEL_MAP = {
       ...
       "my_agent": "model_my_agent",
   }
   ```

3. **Your agent file** — call with the role:
   ```python
   llm = get_llm(role="my_agent")
   ```

The model can then be changed via env var `MODEL_MY_AGENT=...` without
touching any code. Pydantic settings handles the env var → config mapping.

## Current role → model mapping

| Role | Config field | Default model |
|------|-------------|---------------|
| `orchestrator` | `model_orchestrator` | claude-sonnet-4 |
| `investigator` | `model_investigator` | claude-sonnet-4 |
| `investigator_deep` | `model_investigator_deep` | claude-opus-4 |
| `synthesizer` | `model_synthesizer` | claude-sonnet-4 |
| `curator` | `model_curator` | claude-haiku-4-5 |
| _(none / chat)_ | `llm_model` | claude-sonnet-4 |
