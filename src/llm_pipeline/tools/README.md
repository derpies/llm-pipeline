# tools/

Tools are functions that LLM agents can call. They're organized by **domain**
(what they do), not by which agent uses them. Each domain is a self-contained
subpackage.

## How tools work in this codebase

A tool is a Python function decorated with `@tool` from LangChain. The
decorator turns it into something LangGraph's `ToolNode` can execute
automatically when an LLM requests it.

```python
from langchain_core.tools import tool

@tool
def my_tool(param: str) -> str:
    """Docstring becomes the tool description the LLM sees.

    Args:
        param: This becomes the parameter description.
    """
    # Do work, return a string
    return "result"
```

Key rules:
- **Return type must be `str`**. The LLM reads the return value as text.
  For structured data, `json.dumps()` it.
- **The docstring matters**. The LLM uses it to decide when/how to call the tool.
  Write it like you're explaining to someone what this function does and when
  to use it.
- **Args docstring matters too**. Each parameter's description helps the LLM
  provide correct arguments.
- **Use lazy imports** for heavy dependencies inside the function body
  (not at module level) to keep startup fast and avoid circular imports.

## Directory structure

```
tools/
  __init__.py              # Package root
  registry.py              # Auto-discovery registry (get_tools)
  result.py                # Shared ToolStatus/tool_result convention

  datetime/                # Shared utilities
    __init__.py            # TOOL_ROLES, re-exports
    get_current_datetime.py

  rag/                     # RAG retrieval
    __init__.py
    retrieve_documents.py

  reporting/               # Structured output from investigators
    __init__.py
    report_finding.py
    report_hypothesis.py

  circuit_breaker/         # Cycle control
    __init__.py
    check_budget_exceeded.py   # Non-tool helper, re-exported
    report_step.py
    check_budget.py

  knowledge/               # Knowledge store queries
    __init__.py
    retrieve_knowledge.py

  ml/                      # ML analysis queries
    __init__.py
    get_aggregations.py
    get_anomalies.py
    get_trends.py
    get_ml_report_summary.py
    get_data_completeness.py
    compare_dimensions.py
```

## How to add a new tool

### Adding to an existing package

1. Create a new file in the appropriate package (e.g. `tools/ml/my_new_tool.py`)
2. Write the `@tool` function
3. Import it in the package's `__init__.py` and add to `TOOL_ROLES`

Example — adding a cohort analysis tool to `ml/`:

```python
# tools/ml/run_cohort_analysis.py

from langchain_core.tools import tool
from llm_pipeline.tools.result import ToolStatus, tool_result

@tool
def run_cohort_analysis(run_id: str, dimension: str, group_by: str) -> str:
    """Run a targeted cohort analysis."""
    # ... implementation ...
    return tool_result(ToolStatus.OK, "results here")
```

Then update `tools/ml/__init__.py`:

```python
from llm_pipeline.tools.ml.run_cohort_analysis import run_cohort_analysis

TOOL_ROLES = [
    ...
    (run_cohort_analysis, ["investigator"]),
]
```

That's it. `get_tools("investigator")` automatically includes the new tool.

### Creating a new tool package

1. Create `tools/my_domain/`
2. Create `tools/my_domain/__init__.py` with `TOOL_ROLES`
3. Create `tools/my_domain/my_tool.py` with the `@tool` function

The registry auto-discovers packages via `pkgutil.iter_modules`.

## Registry pattern explained

Each package's `__init__.py` defines a `TOOL_ROLES` list:

```python
TOOL_ROLES = [
    (tool_function, ["role1", "role2"]),
    ...
]
```

- List of `(tool_fn, role_list)` tuples. Not a dict — `StructuredTool` objects are not hashable.
- `"*"` is a wildcard role — the tool is available to all roles.
- An empty role list `[]` means the tool is disabled.

Agents get tools via `get_tools("role_name")` from `tools/registry.py`.

## Testing tools

Tools can be tested independently of agents:

```python
from unittest.mock import patch
from llm_pipeline.tools.ml import get_anomalies

def test_get_anomalies_returns_json():
    with patch("llm_pipeline.email_analytics.storage.get_engine") as mock_engine:
        # ... mock setup ...
        result = get_anomalies.invoke({"run_id": "test-123"})
        assert '"anomaly_type"' in result
```

Use `.invoke({"param": "value"})` to call a tool the same way LangGraph does.
