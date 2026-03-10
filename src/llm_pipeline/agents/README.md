# agents/

This directory contains the multi-agent system. Each agent is a LangGraph graph
that receives state, calls an LLM (optionally with tools), and returns updated state.

## How it fits together

```
cli.py
  └─ calls build_investigation_graph()  (from agents/graph.py)
       └─ orchestrator_plan()           (from agents/orchestrator.py)
       └─ build_investigator_graph()    (from agents/investigator.py)
       └─ orchestrator_evaluate()       (from agents/orchestrator.py)
       └─ orchestrator_checkpoint()     (from agents/orchestrator.py)
```

The top-level graph (`graph.py`) wires agents together. Individual agent files
define the LLM calls, tool bindings, and node functions. They don't know about
each other — only `graph.py` knows the full topology.

## File roles

| File | What it does |
|------|-------------|
| `graph.py` | Top-level investigation cycle. Wires agents together, defines fan-out/fan-in. This is the only file that imports from other agent files. |
| `orchestrator.py` | Plans investigations from ML reports, evaluates results, produces checkpoint digests. No tool loop — single LLM calls. |
| `investigator.py` | Examines one topic. Has its own tool loop (LLM calls tools, gets results, calls more tools, concludes). Runs as a subgraph. |
| `chat.py` | Interactive conversational agent (the `chat` CLI command). Completely separate from the investigation cycle. |
| `state.py` | TypedDict state schemas that define what data flows between agents. |
| `models.py` | Pydantic models for domain objects (Hypothesis, Finding, InvestigationTopic, etc.). |
| `prompts.py` | System prompts for every agent, all in one place. |

## How to add a new agent

### 1. Define its system prompt in `prompts.py`

```python
# prompts.py

SYNTHESIZER_SYSTEM_PROMPT = """\
You are a document synthesizer. You take investigation findings and produce
coherent plain-language documents...
"""
```

### 2. Create the agent file

Create `agents/synthesizer.py`. The file needs:

- A `build_*_graph()` function that returns a compiled LangGraph graph
- Internal node functions (prefixed with `_`) for LLM calls and routing
- Tool imports from `tools/`

Here's the minimal pattern — an agent with a tool loop:

```python
# agents/synthesizer.py

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agents.prompts import SYNTHESIZER_SYSTEM_PROMPT
from llm_pipeline.agents.state import SynthesizerState  # you'll define this
from llm_pipeline.models.llm import get_llm
from llm_pipeline.tools.knowledge import SYNTHESIZER_KNOWLEDGE_TOOLS  # tools it needs


# Assemble the tool list for this agent
SYNTHESIZER_TOOLS = SYNTHESIZER_KNOWLEDGE_TOOLS


def _should_continue(state: SynthesizerState) -> str:
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _call_synthesizer(state: SynthesizerState) -> dict:
    # role= controls which model is used (see models/llm.py)
    llm = get_llm(role="synthesizer").bind_tools(SYNTHESIZER_TOOLS)
    messages = [SystemMessage(content=SYNTHESIZER_SYSTEM_PROMPT)] + state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}


def build_synthesizer_graph():
    graph = StateGraph(SynthesizerState)

    graph.add_node("synthesizer", _call_synthesizer)
    graph.add_node("tools", ToolNode(SYNTHESIZER_TOOLS))

    graph.add_edge(START, "synthesizer")
    graph.add_conditional_edges(
        "synthesizer", _should_continue,
        {"tools": "tools", END: END},
    )
    graph.add_edge("tools", "synthesizer")

    return graph.compile()
```

If your agent doesn't need tools (like the orchestrator), skip `ToolNode`
and `bind_tools` — just make direct LLM calls and return state updates.

### 3. Add its state schema to `state.py` (if needed)

If the agent has its own subgraph with private state, define a state class:

```python
# state.py

class SynthesizerState(MessagesState):
    """Private state for the synthesizer subgraph."""
    findings: list[Finding]
    run_id: str
    # Output fields
    documents: Annotated[list[GeneratedDocument], operator.add]
```

If it just participates as a node in the top-level graph, it uses
`InvestigationCycleState` directly and you don't need a new class.

### 4. Add any new Pydantic models to `models.py`

If your agent produces new types of output, define them here:

```python
# models.py

class SynthesisDocument(BaseModel):
    title: str
    content: str
    created_at: datetime
```

### 5. Register the model role (if it needs a specific LLM)

In `config.py`, add a setting:

```python
model_synthesizer: str = "claude-sonnet-4-20250514"
```

In `models/llm.py`, add to `_ROLE_MODEL_MAP`:

```python
_ROLE_MODEL_MAP = {
    ...
    "synthesizer": "model_synthesizer",
}
```

Then your agent calls `get_llm(role="synthesizer")` and the model is
controlled by config/env vars without the agent knowing which model it is.

**This step is already done for: orchestrator, investigator, investigator_deep,
synthesizer, curator.**

### 6. Wire it into `graph.py`

Import your build function and add it as a node:

```python
# graph.py

from llm_pipeline.agents.synthesizer import build_synthesizer_graph

_synthesizer_graph = build_synthesizer_graph()

def _synthesize(state: InvestigationCycleState) -> dict:
    result = _synthesizer_graph.invoke(...)
    return {
        "documents": result.get("documents", []),
        "digest_lines": result.get("digest_lines", []),
    }

# In build_investigation_graph():
graph.add_node("synthesize", _synthesize)
```

### 7. Add a CLI command (if it should be independently runnable)

In `cli.py`, add a new `@app.command()` function that builds and invokes
the graph. See the `investigate` command for the pattern.

## The two graph patterns

**Tool-loop agent** (investigator, chat): The LLM can call tools repeatedly.
Uses `MessagesState`, `ToolNode`, and a `_should_continue` router that loops
back from tools → LLM until the LLM stops calling tools.

```
START → llm_call → [has tool calls?] → tools → llm_call → ... → END
```

**Single-call agent** (orchestrator nodes): Makes one LLM call, parses the
response, returns state. No tool loop. These are just regular functions that
happen to call an LLM internally.

```
START → function_that_calls_llm → END
```

Both patterns are valid. Use tool-loop when the agent needs to iteratively
explore (call tool, think, call another tool). Use single-call when the agent
just needs to produce structured output from its input.

## State and data flow

State flows through the graph via TypedDict fields. Fields annotated with
`Annotated[list[X], operator.add]` are **fan-in fields** — when multiple
parallel nodes write to them, the lists get concatenated. This is how
multiple investigators' findings merge back together.

Fields without the annotation are **overwrite fields** — the last writer wins.

When an agent runs as a subgraph (like the investigator), its internal
`messages` list is private. Only the explicitly returned fan-in fields
(findings, hypotheses, digest_lines) flow back to the parent graph.
