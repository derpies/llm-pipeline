"""Investigator agent — examines a specific topic using ML tools."""

from __future__ import annotations

import json
import logging

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode

from llm_pipeline.agents.prompts import INVESTIGATOR_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigatorState
from llm_pipeline.config import settings
from llm_pipeline.models.llm import get_llm
from llm_pipeline.models.token_tracker import get_tracker
from llm_pipeline.tools.common import get_current_datetime
from llm_pipeline.tools.ml import INVESTIGATOR_ML_TOOLS
from llm_pipeline.tools.reporting import REPORTING_TOOLS

logger = logging.getLogger(__name__)

# Base tools (always available)
INVESTIGATOR_BASE_TOOLS = [get_current_datetime] + INVESTIGATOR_ML_TOOLS + REPORTING_TOOLS

# Legacy alias — full list including conditional tools
INVESTIGATOR_TOOLS = INVESTIGATOR_BASE_TOOLS


def _get_investigator_tools() -> list:
    """Build the investigator tool list, conditionally including knowledge retrieval."""
    tools = list(INVESTIGATOR_BASE_TOOLS)
    if settings.investigator_use_knowledge_store:
        from llm_pipeline.tools.knowledge import retrieve_knowledge

        tools.append(retrieve_knowledge)
    return tools


def _should_continue(state: InvestigatorState) -> str:
    """Route: continue tool loop or finish."""
    last = state["messages"][-1]
    if hasattr(last, "tool_calls") and last.tool_calls:
        return "tools"
    return END


def _call_investigator(state: InvestigatorState) -> dict:
    """Invoke the investigator LLM with the current state."""
    tools = _get_investigator_tools()
    llm = get_llm(role="investigator").bind_tools(tools)

    # On first call, inject the investigation brief
    if len(state["messages"]) == 0 or (
        len(state["messages"]) == 1 and isinstance(state["messages"][0], HumanMessage)
    ):
        topic = state["topic"]
        brief_parts = [
            f"Investigate: {topic.title}",
            f"Dimension: {topic.dimension}={topic.dimension_value}",
            f"Metrics of interest: {', '.join(topic.metrics)}",
            f"Question: {topic.question}",
            f"Context: {topic.context}",
            f"Run ID: {state['run_id']}",
        ]

        # Inject prior context for follow-up rounds
        prior_context = state.get("prior_context", "")
        if prior_context:
            brief_parts.append(f"\n--- Prior findings from earlier rounds ---\n{prior_context}")

        brief_parts.append(
            "\nUse the ML tools to examine the data. Form a hypothesis, test it, "
            "and report your findings using report_finding and report_hypothesis tools. "
            "You MUST call report_finding at least once before finishing."
        )
        brief = "\n".join(brief_parts)

        messages = [
            SystemMessage(content=INVESTIGATOR_SYSTEM_PROMPT),
            HumanMessage(content=brief),
        ]
    else:
        messages = [SystemMessage(content=INVESTIGATOR_SYSTEM_PROMPT)] + state["messages"]

    response = llm.invoke(messages)
    get_tracker().record(response, model=settings.model_investigator)
    return {"messages": [response]}


def _extract_results(state: InvestigatorState) -> dict:
    """Extract findings from reporting tool calls in the message history.

    Scans all messages for report_finding and report_hypothesis tool calls,
    parses their arguments into Finding/Hypothesis objects. Falls back to
    creating an INCONCLUSIVE finding from the final message if no reporting
    tools were called.
    """
    from datetime import UTC, datetime

    from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis

    topic = state["topic"]
    run_id = state.get("run_id", "")
    now = datetime.now(UTC)

    findings: list[Finding] = []
    hypotheses: list[Hypothesis] = []
    digest_lines: list[str] = []

    # Scan all messages for reporting tool calls
    for msg in state["messages"]:
        if not hasattr(msg, "tool_calls") or not msg.tool_calls:
            continue
        for tc in msg.tool_calls:
            name = tc.get("name", "")
            args = tc.get("args", {})

            if name == "report_finding":
                # Parse metrics_cited — could be JSON string or dict
                metrics_cited = args.get("metrics_cited", "{}")
                if isinstance(metrics_cited, str):
                    try:
                        metrics_cited = json.loads(metrics_cited)
                    except (json.JSONDecodeError, TypeError):
                        metrics_cited = {}
                if not isinstance(metrics_cited, dict):
                    metrics_cited = {}
                # Filter to numeric values only (LLM sometimes passes strings like "7-24")
                clean_metrics: dict[str, float] = {}
                for k, v in metrics_cited.items():
                    try:
                        clean_metrics[k] = float(v)
                    except (ValueError, TypeError):
                        pass
                metrics_cited = clean_metrics

                # Parse evidence — could be JSON string or list
                evidence = args.get("evidence", "[]")
                if isinstance(evidence, str):
                    try:
                        evidence = json.loads(evidence)
                    except (json.JSONDecodeError, TypeError):
                        evidence = [evidence] if evidence else []
                if not isinstance(evidence, list):
                    evidence = [str(evidence)]

                # Parse status
                status_str = args.get("status", "inconclusive")
                try:
                    status = FindingStatus(status_str)
                except ValueError:
                    status = FindingStatus.INCONCLUSIVE

                finding = Finding(
                    topic_title=topic.title,
                    statement=args.get("statement", ""),
                    status=status,
                    evidence=evidence,
                    metrics_cited=metrics_cited,
                    created_at=now,
                    run_id=run_id,
                )
                findings.append(finding)
                digest_lines.append(
                    f"[finding:{status.value}] {finding.statement}"
                )

            elif name == "report_hypothesis":
                hypothesis = Hypothesis(
                    topic_title=topic.title,
                    statement=args.get("statement", ""),
                    reasoning=args.get("reasoning", ""),
                    created_at=now,
                    run_id=run_id,
                )
                hypotheses.append(hypothesis)
                digest_lines.append(f"[hypothesis] {hypothesis.statement}")

    # Fallback: no reporting tools were called — create INCONCLUSIVE from final message
    if not findings:
        last_message = state["messages"][-1]
        content = last_message.content if hasattr(last_message, "content") else str(last_message)
        finding = Finding(
            topic_title=topic.title,
            statement=content[:500] if len(content) > 500 else content,
            status=FindingStatus.INCONCLUSIVE,
            evidence=[],
            created_at=now,
            run_id=run_id,
        )
        findings.append(finding)
        digest_lines.append(f"[finding:inconclusive] {topic.title}: no reporting tools called")

    return {
        "findings": findings,
        "hypotheses": hypotheses,
        "digest_lines": digest_lines,
    }


def build_investigator_graph():
    """Build the investigator subgraph with its own tool loop."""
    tools = _get_investigator_tools()
    graph = StateGraph(InvestigatorState)

    graph.add_node("investigator", _call_investigator)
    graph.add_node("tools", ToolNode(tools))
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
