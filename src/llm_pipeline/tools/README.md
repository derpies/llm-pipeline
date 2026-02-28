# tools/

Tools are functions that LLM agents can call. They're organized by **domain**
(what they do), not by which agent uses them.

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

## File roles

| File | Domain | What it wraps |
|------|--------|--------------|
| `common.py` | Shared utilities | `get_current_datetime`, `retrieve_documents` (RAG). Available to all agents. |
| `ml.py` | ML analysis | Read-only queries against `email_analytics/storage.py`. Aggregations, anomalies, trends, report summaries. |
| `circuit_breaker.py` | Cycle control | Budget checking, step logging. Used by orchestrator and investigator. |

## How to add a new tool

### Adding to an existing file

1. Write the `@tool` function in the appropriate file
2. Add it to the relevant registry list at the bottom of the file

Example — adding a cohort analysis tool to `ml.py`:

```python
# tools/ml.py

@tool
def run_cohort_analysis(
    run_id: str,
    dimension: str,
    group_by: str,
    metric: str = "delivery_rate",
) -> str:
    """Run a targeted cohort analysis for a specific dimension slice.

    Use this when you need to compare a metric across groups within a dimension.

    Args:
        run_id: The analysis run to query.
        dimension: The dimension to filter on (e.g. "listid").
        group_by: The dimension to group results by (e.g. "recipient_domain").
        metric: The metric to compare.
    """
    # ... implementation ...
    return json.dumps(results, indent=2)


# Update the registry:
INVESTIGATOR_ML_TOOLS = [
    get_aggregations, get_anomalies, get_trends, get_ml_report_summary,
    run_cohort_analysis,  # <-- add here
]
```

That's it. Any agent that imports `INVESTIGATOR_ML_TOOLS` automatically
gets the new tool.

### Creating a new tool file

When you have a new domain (e.g., knowledge store operations), create a new file:

1. Create `tools/knowledge.py`
2. Write your `@tool` functions
3. Define registry lists at the bottom
4. Import the registry in the agent that needs it

```python
# tools/knowledge.py

from langchain_core.tools import tool

@tool
def search_knowledge(query: str, tier: str = "all") -> str:
    """Search the knowledge store for relevant findings.

    Args:
        query: Search query text.
        tier: Knowledge tier to search ("hypotheses", "findings", "truth", "all").
    """
    # ... implementation ...
    return json.dumps(results, indent=2)

@tool
def store_finding(statement: str, evidence: str, status: str = "confirmed") -> str:
    """Store a confirmed finding in the knowledge store.

    Args:
        statement: The finding statement.
        evidence: Supporting evidence (comma-separated).
        status: Finding status ("confirmed", "disproven", "inconclusive").
    """
    # ... implementation ...
    return f"Stored finding: {statement}"


# Registries — group tools by which agents need them
INVESTIGATOR_KNOWLEDGE_TOOLS = [search_knowledge, store_finding]
CURATOR_KNOWLEDGE_TOOLS = [search_knowledge, store_finding]  # + promote, deprecate, etc.
```

### Connecting tools to an agent

In the agent file, import the registries and combine them:

```python
# agents/investigator.py

from llm_pipeline.tools.common import get_current_datetime
from llm_pipeline.tools.ml import INVESTIGATOR_ML_TOOLS
from llm_pipeline.tools.knowledge import INVESTIGATOR_KNOWLEDGE_TOOLS

# Combine all tools this agent can use
INVESTIGATOR_TOOLS = [get_current_datetime] + INVESTIGATOR_ML_TOOLS + INVESTIGATOR_KNOWLEDGE_TOOLS
```

The agent's `build_*_graph()` function passes this list to `ToolNode`:

```python
graph.add_node("tools", ToolNode(INVESTIGATOR_TOOLS))
```

And binds them to the LLM:

```python
llm = get_llm(role="investigator").bind_tools(INVESTIGATOR_TOOLS)
```

## Registry pattern explained

Each tool file defines one or more `*_TOOLS` lists at the bottom. These
are just plain Python lists of tool functions. Naming convention:

```
{AGENT_ROLE}_{DOMAIN}_TOOLS
```

Examples:
- `INVESTIGATOR_ML_TOOLS` — ML tools the investigator can use
- `ORCHESTRATOR_ML_TOOLS` — ML tools the orchestrator can use (subset)
- `CHAT_TOOLS` — all tools for the chat agent
- `CIRCUIT_BREAKER_TOOLS` — all circuit breaker tools

Different agents can get different subsets of tools from the same domain.
The orchestrator gets `get_ml_report_summary` (high-level) while the
investigator gets `get_aggregations` (detailed). This is just list curation —
no framework magic.

## Testing tools

Tools can be tested independently of agents:

```python
# tests/test_tools_ml.py

from unittest.mock import patch
from llm_pipeline.tools.ml import get_anomalies

def test_get_anomalies_returns_json():
    with patch("llm_pipeline.email_analytics.storage.get_engine") as mock_engine:
        # ... mock setup ...
        result = get_anomalies.invoke({"run_id": "test-123"})
        assert '"anomaly_type"' in result
```

Use `.invoke({"param": "value"})` to call a tool the same way LangGraph does.
