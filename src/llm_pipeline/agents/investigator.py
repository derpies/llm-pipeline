"""Investigator agent — examines a specific topic using ML tools."""

from __future__ import annotations

import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agents.prompts import INVESTIGATOR_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigatorState
from llm_pipeline.models.llm import get_llm
from llm_pipeline.tools.common import get_current_datetime
from llm_pipeline.tools.ml import INVESTIGATOR_ML_TOOLS

logger = logging.getLogger(__name__)

# Tools available to the investigator
INVESTIGATOR_TOOLS = [get_current_datetime] + INVESTIGATOR_ML_TOOLS


def _should_continue(state: InvestigatorState) -> str:
    """Route: continue tool loop or finish."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _call_investigator(state: InvestigatorState) -> dict:
    """Invoke the investigator LLM with the current state."""
    llm = get_llm(role="investigator").bind_tools(INVESTIGATOR_TOOLS)

    # On first call, inject the investigation brief
    if len(state["messages"]) == 0 or (
        len(state["messages"]) == 1 and isinstance(state["messages"][0], HumanMessage)
    ):
        topic = state["topic"]
        brief = (
            f"Investigate: {topic.title}\n"
            f"Dimension: {topic.dimension}={topic.dimension_value}\n"
            f"Metrics of interest: {', '.join(topic.metrics)}\n"
            f"Question: {topic.question}\n"
            f"Context: {topic.context}\n"
            f"Run ID: {state['run_id']}\n\n"
            f"Use the ML tools to examine the data. Form a hypothesis, test it, "
            f"and report your finding. When done, provide your final assessment "
            f"without calling any more tools."
        )
        messages = [
            SystemMessage(content=INVESTIGATOR_SYSTEM_PROMPT),
            HumanMessage(content=brief),
        ]
    else:
        messages = [SystemMessage(content=INVESTIGATOR_SYSTEM_PROMPT)] + state["messages"]

    response = llm.invoke(messages)
    return {"messages": [response]}


def _extract_results(state: InvestigatorState) -> dict:
    """Extract findings from the investigator's final message."""
    from datetime import UTC, datetime

    from llm_pipeline.agents.models import Finding, FindingStatus

    topic = state["topic"]
    last_message = state["messages"][-1]
    content = last_message.content if hasattr(last_message, "content") else str(last_message)

    # For Phase A, create a finding from the final message content
    finding = Finding(
        topic_title=topic.title,
        statement=content[:500] if len(content) > 500 else content,
        status=FindingStatus.INCONCLUSIVE,
        evidence=[],
        created_at=datetime.now(UTC),
        run_id=state.get("run_id", ""),
    )

    digest = f"[investigate] {topic.title}: {finding.status.value}"

    return {
        "findings": [finding],
        "digest_lines": [digest],
    }


def build_investigator_graph():
    """Build the investigator subgraph with its own tool loop."""
    graph = StateGraph(InvestigatorState)

    graph.add_node("investigator", _call_investigator)
    graph.add_node("tools", ToolNode(INVESTIGATOR_TOOLS))
    graph.add_node("extract_results", _extract_results)

    graph.add_edge(START, "investigator")
    graph.add_conditional_edges(
        "investigator",
        _should_continue,
        {"tools": "tools", END: "extract_results"},
    )
    graph.add_edge("tools", "investigator")
    graph.add_edge("extract_results", END)

    return graph.compile()
