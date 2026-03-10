# Plugin Guide: Adding Tools and Agents

This document explains how to add new tools and agents to the pipeline using the auto-discovery registries.

---

## Adding a New Tool

Each tool domain is a subpackage under `src/llm_pipeline/tools/`. One tool function per file. The package's `__init__.py` declares `TOOL_ROLES` and re-exports.

### Example: `tools/latency/`

```
tools/latency/
├── __init__.py
├── get_latency_percentiles.py
└── compare_latency.py
```

```python
# tools/latency/get_latency_percentiles.py

from langchain_core.tools import tool
from llm_pipeline.tools.result import ToolStatus, tool_result

@tool
def get_latency_percentiles(
    run_id: str,
    dimension: str | None = None,
    limit: int = 20,
) -> str:
    """Retrieve latency percentile data from an ML analysis run.

    Args:
        run_id: The analysis run to query.
        dimension: Filter by dimension.
        limit: Max results to return.
    """
    # ... implementation ...
    return tool_result(ToolStatus.OK, "results here")
```

```python
# tools/latency/__init__.py

from llm_pipeline.tools.latency.get_latency_percentiles import get_latency_percentiles
from llm_pipeline.tools.latency.compare_latency import compare_latency

TOOL_ROLES = [
    (get_latency_percentiles, ["investigator"]),
    (compare_latency,         ["investigator", "orchestrator"]),
]
```

That's it. On next startup, `get_tools("investigator")` includes both tools and `get_tools("orchestrator")` includes `compare_latency`.

### TOOL_ROLES Format

```python
TOOL_ROLES = [
    (tool_function, ["role1", "role2"]),
    ...
]
```

- List of `(tool_fn, role_list)` tuples. Not a dict — `StructuredTool` objects are not hashable.
- `"*"` is a wildcard role — the tool is available to all roles (e.g., `get_current_datetime`).
- An empty role list `[]` means the tool is not available to anyone (useful for conditional inclusion).

### Built-in Roles

| Role | Used by | Description |
|------|---------|-------------|
| `investigator` | Investigation agent plugin | ML query tools, reporting tools, circuit breaker tools |
| `orchestrator` | Orchestrator (plan/evaluate) | Summary-level ML tools |
| `chat` | Chat agent | RAG retrieval, general tools |
| `*` | All roles | Wildcard — included everywhere |

You can define new roles. Any string works — the registry just indexes by string key.

### Conditional Inclusion

To include a tool only when a setting is enabled:

```python
from llm_pipeline.config import settings

TOOL_ROLES = [
    (my_tool, ["investigator"] if settings.some_flag else []),
]
```

The condition is evaluated at import time. If the setting changes, call `reset_registry()` to re-discover.

### Conventions

- Return values should use `tool_result(ToolStatus.OK|EMPTY|ERROR, content)` from `tools/result.py`. This enables the circuit breaker to detect consecutive failures.
- Tool docstrings are sent to the LLM — write them as instructions for the model.
- Defer heavy imports (SQLAlchemy, etc.) inside the function body to keep startup fast.

---

## Adding a New Investigation Agent

Investigation agents participate in the orchestrator's fan-out. They receive topics, run their own tool loop, and produce findings/hypotheses that feed back into the investigation cycle.

### Directory Structure

```
src/llm_pipeline/agents/plugins/my_agent/
├── __init__.py
├── manifest.py      # AgentManifest declaration (required)
├── agent.py         # Graph build function
└── extract.py       # Result extraction + ResultAdapter
```

### Step 1: Create the directory

```
mkdir -p src/llm_pipeline/agents/plugins/my_agent
touch src/llm_pipeline/agents/plugins/my_agent/__init__.py
```

### Step 2: Define tools (if needed)

If your agent needs its own tools, create a tool package (see above) with a role matching your agent's `tool_role`. For example, if your manifest sets `tool_role="compliance_auditor"`:

```python
# tools/compliance/__init__.py
from llm_pipeline.tools.compliance.check_spf_alignment import check_spf_alignment
from llm_pipeline.tools.compliance.check_dkim_alignment import check_dkim_alignment

TOOL_ROLES = [
    (check_spf_alignment, ["compliance_auditor"]),
    (check_dkim_alignment, ["compliance_auditor"]),
]
```

Your agent can also reuse existing tools by listing shared roles.

### Step 3: Build the agent graph (`agent.py`)

```python
"""Compliance auditor agent."""

from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agents.state import InvestigatorState
from llm_pipeline.models.llm import get_llm
from llm_pipeline.tools.registry import get_tools


def _call_agent(state):
    tools = get_tools("compliance_auditor")
    llm = get_llm(role="investigator").bind_tools(tools)
    # ... build messages, invoke LLM, return {"messages": [response]}
    ...


def _should_continue(state):
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _extract_results(state):
    # Parse findings/hypotheses from message history
    # See investigator/extract.py for the full pattern
    ...
    return {"findings": findings, "hypotheses": hypotheses, "digest_lines": lines}


def build_compliance_graph():
    tools = get_tools("compliance_auditor")
    graph = StateGraph(InvestigatorState)

    graph.add_node("agent", _call_agent)
    graph.add_node("tools", ToolNode(tools))
    graph.add_node("extract_results", _extract_results)

    graph.add_edge(START, "agent")
    graph.add_conditional_edges("agent", _should_continue, {"tools": "tools", END: "extract_results"})
    graph.add_edge("tools", "agent")
    graph.add_edge("extract_results", END)

    return graph.compile()
```

The agent's graph must accept `InvestigatorState` (or a compatible TypedDict) as input and produce `findings`, `hypotheses`, and `digest_lines` in its output.

### Step 4: Create the result adapter (`extract.py`)

If your agent produces output in the standard format (findings/hypotheses/digest_lines), use a pass-through adapter:

```python
from llm_pipeline.agents.contracts import InvestigationOutput


class ComplianceResultAdapter:
    def adapt(self, raw_output: dict) -> InvestigationOutput:
        return InvestigationOutput(
            findings=raw_output.get("findings", []),
            hypotheses=raw_output.get("hypotheses", []),
            digest_lines=raw_output.get("digest_lines", []),
            completed_topics=raw_output.get("completed_topics", []),
            topic_errors=raw_output.get("topic_errors", []),
        )
```

If your agent produces a different output shape, the adapter is where you convert it:

```python
class ComplianceResultAdapter:
    def adapt(self, raw_output: dict) -> InvestigationOutput:
        # Convert violations → findings
        findings = []
        for v in raw_output.get("violations", []):
            findings.append(Finding(
                topic_title=v.topic,
                statement=f"Compliance violation: {v.description}",
                status=FindingStatus.CONFIRMED,
                evidence=v.evidence,
                created_at=v.detected_at,
            ))
        return InvestigationOutput(
            findings=findings,
            hypotheses=[],
            digest_lines=[f"[compliance] {len(findings)} violations found"],
            completed_topics=raw_output.get("completed_topics", []),
            topic_errors=raw_output.get("topic_errors", []),
        )
```

### Step 5: Declare the manifest (`manifest.py`)

```python
from llm_pipeline.agents.contracts import AgentManifest
from llm_pipeline.agents.plugins.my_agent.agent import build_compliance_graph
from llm_pipeline.agents.plugins.my_agent.extract import ComplianceResultAdapter
from llm_pipeline.agents.state import InvestigatorState

manifest = AgentManifest(
    name="compliance_auditor",
    agent_type="investigation",
    tool_role="compliance_auditor",
    build_graph=build_compliance_graph,
    state_class=InvestigatorState,
    result_adapter=ComplianceResultAdapter(),
    description="Compliance auditor — checks SPF/DKIM/DMARC alignment",
)
```

Key fields:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Unique ID. Must match what the orchestrator puts in `agent_type`. |
| `agent_type` | Yes | `"investigation"` for fan-out agents, `"pipeline"` for standalone. |
| `tool_role` | Yes | Role string passed to `get_tools()`. |
| `build_graph` | Yes | Callable returning a compiled LangGraph. Called lazily on first use. |
| `state_class` | Yes | The TypedDict used by the agent's graph. |
| `result_adapter` | For investigation agents | Converts raw output to `InvestigationOutput`. |
| `description` | Recommended | Shown in orchestrator prompts and CLI help. |

### Step 6: Test it

The orchestrator assigns `agent_type` on each `InvestigationTopic`. The graph routes to `investigate_{agent_type}`. To have the orchestrator dispatch to your agent, the LLM must set `agent_type: "compliance_auditor"` in its topic JSON. The orchestrator validates `agent_type` against the registry and falls back to `"investigator"` for unknown values.

For testing, you can construct topics directly:

```python
topic = InvestigationTopic(
    title="SPF alignment check",
    dimension="accountid",
    dimension_value="12345",
    metrics=["compliance_rate"],
    question="Is SPF aligned?",
    agent_type="compliance_auditor",
)
```

---

## Adding a Pipeline Agent (Standalone CLI Command)

Pipeline agents are standalone workflows with their own graph and CLI command. They don't participate in the investigation fan-out.

### Manifest

```python
import typer

from llm_pipeline.agents.contracts import AgentManifest
from llm_pipeline.agents.plugins.my_pipeline.agent import build_pipeline_graph


def run_pipeline(input_path: str) -> None:
    """CLI handler for the pipeline agent."""
    graph = build_pipeline_graph()
    result = graph.invoke({"input_path": input_path})
    typer.echo(f"Done: {result}")


manifest = AgentManifest(
    name="my_pipeline",
    agent_type="pipeline",
    tool_role="my_pipeline",
    build_graph=build_pipeline_graph,
    state_class=dict,
    description="My custom pipeline agent",
    cli_command="my-pipeline",
    cli_handler=run_pipeline,
)
```

The CLI command is auto-registered at startup: `uv run python -m llm_pipeline.cli my-pipeline <args>`.

---

## Registry API Reference

### Tool Registry (`tools/registry.py`)

```python
from llm_pipeline.tools.registry import get_tools, reset_registry

tools = get_tools("investigator")  # list of tool functions
reset_registry()                   # force re-discovery (for testing)
```

### Agent Registry (`agents/registry.py`)

```python
from llm_pipeline.agents.registry import (
    get_agent,                  # get_agent("investigator") → AgentManifest | None
    get_investigation_agents,   # → dict[str, AgentManifest]
    get_pipeline_agents,        # → dict[str, AgentManifest]
    list_agents,                # → dict[str, AgentManifest] (all)
    reset_registry,             # force re-discovery (for testing)
)
```

---

## How Discovery Works

### Tools

1. On first call to `get_tools()`, the registry imports every module/package in `llm_pipeline.tools.*` via `pkgutil.iter_modules`.
2. Modules starting with `_` and `registry`/`result` are skipped.
3. For packages (e.g. `tools/ml/`), the package's `__init__.py` is imported.
4. Each module/package's `TOOL_ROLES` attribute (if present) is read.
5. Tools are indexed by role. Wildcard (`*`) tools are added to every role query.
6. Results are cached. Call `reset_registry()` to re-scan.

### Agents

1. On first call to `get_agent()` (or similar), the registry imports every subpackage in `llm_pipeline.agents.plugins.*`.
2. Only packages (directories) are scanned, not loose files.
3. Each package's `manifest` module is imported and its `manifest` attribute read.
4. The attribute must be an `AgentManifest` instance.
5. Results are cached. Call `reset_registry()` to re-scan.
