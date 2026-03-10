# Code Documentation Standards

Canonical reference for documentation and commenting standards in this codebase.

These standards serve two audiences: **humans reading code** and **AI agents gathering context**. The per-subpackage READMEs are the primary mechanism for AI context — an agent reads the README before deciding which files to open.

---

## 1. File-Level Docstring

**Required on every `.py` file**, including `__init__.py` and test files.

Rules:
- Active voice, terse — what the file *does*, not what it *is*
- For `__init__.py`: describe the package, not just "Package init"
- For test files: describe what area of functionality is being tested

Good:
```python
"""Auto-discovery tool registry. Scans tools/ for modules with TOOL_ROLES dicts."""
```

```python
"""Anomaly detection using modified z-score (MAD-based)."""
```

```python
"""Tests for ML anomaly detection — z-score thresholds, segment baselines."""
```

Bad:
```python
"""This module contains the registry class."""
```

```python
"""Package init."""
```

Multi-line docstrings are fine when context is needed (e.g., algorithmic rationale):
```python
"""Anomaly detection using modified z-score (MAD-based).

Email delivery data is heavy-tailed — standard z-score is inflated by
outliers. Modified z-score based on Median Absolute Deviation is robust
to this. Falls back to standard z-score when MAD=0.
"""
```

---

## 2. Section Comments

Use `# ---` separator comments to delimit logical sections in files longer than ~50 lines.

```python
# --- Constants ---

SEGMENT_BASELINES = { ... }

# --- Public API ---

def detect_anomalies(...):
    ...

# --- Helpers ---

def _compute_z_score(...):
    ...
```

Rules:
- Not required in short files (<50 lines)
- Use consistent section names across files: `Constants`, `Public API`, `Helpers`, `Types/Models`, `Enums`, `Tool role declarations`
- The existing `# --- Tool role declarations for auto-discovery ---` pattern is the model to follow
- Longer dashed separators (`# ---------------------------------------------------------------------------`) are acceptable in files that already use them (e.g., `knowledge/models.py`)

---

## 3. Function/Method Docstrings

Google-style `Args:`/`Returns:`/`Raises:` format.

### When docstrings are required

| Context | Required? |
|---------|-----------|
| Public functions | Yes |
| `@tool` functions | Yes |
| Private functions >10 lines | Yes |
| Short private helpers with obvious name + signature | No |

### `@tool` functions

Docstrings on `@tool` functions are **instructions to the LLM** — they're the interface the agent sees. Write them as usage guidance, not developer docs.

```python
@tool
def get_aggregations(
    run_id: str,
    dimension: str | None = None,
    dimension_value: str | None = None,
    limit: int = 50,
) -> str:
    """Retrieve aggregation data from an ML analysis run.

    Args:
        run_id: The analysis run to query.
        dimension: Filter by dimension (e.g. "listid", "recipient_domain").
        dimension_value: Filter by specific dimension value.
        limit: Max rows to return.
    """
```

### Non-tool functions

Write for developers reading the code.

```python
def compute_confidence(
    tier: KnowledgeTier,
    finding_status: str | None = None,
    observation_count: int = 1,
    temporal_span_days: int = 0,
) -> float:
    """Compute confidence score based on tier and evidence strength."""
```

### Args/Returns/Raises

- Include `Args:` when parameter purpose isn't obvious from the name
- Include `Returns:` when the return value isn't obvious
- Include `Raises:` only for exceptions callers should handle

---

## 4. Inline Comments

Comments should explain **why**, not **what**.

Rules:
- Comment domain assumptions, non-obvious thresholds, algorithmic choices
- Don't comment obvious code
- Use comments to flag edge cases or gotchas
- Constants with domain meaning should always have a comment

Good:
```python
# Metrics where a drop is bad (lower = worse)
_POSITIVE_METRICS = {"delivery_rate"}

# Minimum data points needed — fewer than this and statistical tests are unreliable
MIN_SAMPLE_SIZE = 5
```

Bad:
```python
# Set the logger
logger = logging.getLogger(__name__)

# Increment counter
count += 1
```

---

## 5. `__init__.py` Content

Every package `__init__.py` must have:

1. **Module docstring** — what this package does
2. **Imports + re-exports** of public API
3. **`__all__` list** — explicit public API surface
4. For tool packages: **`TOOL_ROLES` declaration**

Example (from `tools/ml/__init__.py`):
```python
"""ML-as-a-tool — read-only wrappers around email_analytics storage queries."""

from llm_pipeline.tools.ml.compare_dimensions import compare_dimensions
from llm_pipeline.tools.ml.get_aggregations import get_aggregations
from llm_pipeline.tools.ml.get_anomalies import get_anomalies
# ...

# --- Tool role declarations for auto-discovery ---
TOOL_ROLES = [
    (get_aggregations, ["investigator"]),
    (get_anomalies, ["investigator", "orchestrator"]),
    # ...
]

__all__ = [
    "get_aggregations",
    "get_anomalies",
    # ...
    "TOOL_ROLES",
]
```

---

## 6. Per-Subpackage README.md

**Every directory that contains Python code** gets a `README.md`. This is the primary mechanism for AI context-gathering — an agent reads the README before deciding which files to open.

### Template

```markdown
# package_name/

One-sentence purpose.

## Files

| File | Purpose |
|------|---------|
| `foo.py` | Does X |
| `bar.py` | Does Y |

## Key Concepts

Brief explanation of domain concepts needed to understand this code.
Only include when the package involves non-obvious domain logic.

## Contracts

How this package interacts with the rest of the system:
- What it imports from (dependencies)
- What it exports (public API)
- Key interfaces/protocols it implements
```

### Rules

- **Files table is mandatory** — every `.py` file in the directory must appear
- **Key Concepts** — include when domain knowledge is needed (e.g., email_analytics, knowledge tiers). Skip for straightforward packages.
- **Contracts** — include for packages consumed by other packages. Skip for leaf packages.
- Target 30–80 lines. If the README exceeds ~100 lines, the package is probably too large.
- **Update the README when adding, removing, or renaming files** — a stale file table is worse than no README

---

## 7. Pydantic Model Field Documentation

Use `Field(description=...)` for fields whose purpose isn't obvious from the name + type alone.

```python
class Finding(BaseModel):
    statement: str = Field(description="One-sentence description of what was found")
    status: FindingStatus  # no description needed — type is self-explanatory
    evidence: list[str] = Field(default_factory=list, description="Supporting evidence strings")
    metrics_cited: dict[str, float] = Field(
        default_factory=dict,
        description='Metric name → value, e.g. {"delivery_rate": 0.88}',
    )
```

Rules:
- **Required** on fields where type + name isn't sufficient (e.g., `metrics_cited: dict`)
- **Not required** on self-explanatory fields (e.g., `status: FindingStatus`, `run_id: str`)
- Don't duplicate the type hint in the description

---

## 8. Test File Documentation

```python
"""Tests for ML anomaly detection — z-score thresholds, segment baselines."""
```

Rules:
- Module docstring required — what area of functionality is being tested
- Individual test functions: docstring optional, but the function name must be descriptive (e.g., `test_high_bounce_rate_triggers_anomaly`)
- No docstrings on trivial assertion-only tests

---

## Anti-Patterns (Don'ts)

1. **Don't add `# removed` comments** — if code is deleted, just delete it
2. **Don't write changelog comments** — git history is the changelog
3. **Don't document type hints in docstrings** — the types are in the signature
4. **Don't add boilerplate headers** (copyright, author, date) — we don't use those
5. **Don't add docstrings to every single private helper** — short, obvious helpers don't need them
6. **Don't put architecture docs in READMEs** — those go in `docs/` or `CLAUDE.md`. READMEs describe the files in the directory, not system-wide design.
