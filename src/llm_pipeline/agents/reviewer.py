"""Reviewer agent — challenges findings, spot-checks evidence via ML tools.

Runs as a single sequential node in the investigation cycle graph (not fan-out).
Produces ReviewAnnotation objects that inform the evaluator's follow-up decisions.
"""

from __future__ import annotations

import json
import logging

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from langgraph.prebuilt import ToolNode
from pydantic import TypeAdapter

from llm_pipeline.agents.models import (
    Finding,
    Hypothesis,
    ReviewAction,
    ReviewAnnotation,
    ReviewAssessment,
)
from llm_pipeline.agents.prompts import REVIEWER_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigationCycleState
from llm_pipeline.config import settings
from llm_pipeline.models.llm import get_llm
from llm_pipeline.models.rate_limiter import get_rate_limiter
from llm_pipeline.models.token_tracker import get_tracker
from llm_pipeline.tools.registry import get_tools

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Reviewer subgraph state
# ---------------------------------------------------------------------------

class _ReviewerState(dict):
    """Internal state for the reviewer subgraph tool loop."""

    pass


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------

def _get_reviewer_prompt() -> str:
    """Build the reviewer system prompt with domain knowledge."""
    from llm_pipeline.agents.domain_registry import get_active_domain

    domain = get_active_domain()
    domain_knowledge = domain.investigator_domain_prompt if domain else ""
    return REVIEWER_SYSTEM_PROMPT.format(domain_knowledge=domain_knowledge)


def _build_review_input(findings: list[Finding], hypotheses: list[Hypothesis]) -> str:
    """Format findings and hypotheses for the reviewer's input message."""
    lines = []

    if findings:
        lines.append("Findings to review:")
        for i, f in enumerate(findings):
            lines.append(f"  [{i}] [{f.status.value}] {f.statement}")
            if f.evidence:
                for e in f.evidence[:3]:
                    lines.append(f"      evidence: {e}")
            if f.metrics_cited:
                metrics_str = ", ".join(f"{k}={v}" for k, v in f.metrics_cited.items())
                lines.append(f"      metrics: {metrics_str}")
    else:
        lines.append("No findings to review.")

    if hypotheses:
        lines.append("\nUntested hypotheses:")
        for h in hypotheses:
            lines.append(f"  - {h.statement} ({h.reasoning})")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Annotation parsing
# ---------------------------------------------------------------------------

_VALID_ASSESSMENTS = {e.value for e in ReviewAssessment}
_VALID_ACTIONS = {e.value for e in ReviewAction}


def _parse_annotations(content: str, findings: list[Finding]) -> list[ReviewAnnotation]:
    """Parse LLM response into ReviewAnnotation list."""
    text = content.strip()
    if text.startswith("```"):
        text_lines = text.split("\n")
        text_lines = [line for line in text_lines if not line.strip().startswith("```")]
        text = "\n".join(text_lines)

    try:
        data = json.loads(text)
        if not isinstance(data, list):
            logger.warning("Reviewer response is not a JSON array")
            return []

        # Coerce invalid enum values
        for item in data:
            if isinstance(item, dict):
                if "assessment" in item and item["assessment"] not in _VALID_ASSESSMENTS:
                    item["assessment"] = "weak_evidence"
                if "suggested_action" in item and item["suggested_action"] not in _VALID_ACTIONS:
                    item["suggested_action"] = "flag_for_human"
                # Clamp finding_index
                if "finding_index" in item:
                    idx = item["finding_index"]
                    if not isinstance(idx, int) or idx < 0 or idx >= len(findings):
                        item["finding_index"] = 0

        adapter = TypeAdapter(list[ReviewAnnotation])
        return adapter.validate_python(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse reviewer annotations: %s", e)
        return []


# ---------------------------------------------------------------------------
# Reviewer subgraph nodes
# ---------------------------------------------------------------------------

def _call_reviewer(state: dict) -> dict:
    """Invoke the reviewer LLM."""
    tools = get_tools("reviewer")
    llm = get_llm(role="reviewer").bind_tools(tools)

    get_rate_limiter().acquire()
    response = llm.invoke(state["messages"])
    get_tracker().record(response, model=settings.model_reviewer)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        inp = (usage.get("input_tokens", 0) if isinstance(usage, dict)
               else getattr(usage, "input_tokens", 0))
        get_rate_limiter().record(inp)

    messages = list(state["messages"]) + [response]
    llm_calls = state.get("llm_calls", 0) + 1
    return {**state, "messages": messages, "llm_calls": llm_calls}


def _reviewer_should_continue(state: dict) -> str:
    """Route: continue tool loop or finish."""
    last = state["messages"][-1]
    if not (hasattr(last, "tool_calls") and last.tool_calls):
        return "done"

    if state.get("llm_calls", 0) >= settings.reviewer_max_llm_calls:
        logger.info("reviewer circuit breaker: max_llm_calls reached (%d)", state["llm_calls"])
        return "done"

    return "tools"


def _build_reviewer_subgraph():
    """Build the reviewer's internal tool loop subgraph."""
    tools = get_tools("reviewer")
    graph = StateGraph(dict)

    graph.add_node("reviewer_llm", _call_reviewer)
    graph.add_node("tools", ToolNode(tools))

    graph.add_edge(START, "reviewer_llm")
    graph.add_conditional_edges(
        "reviewer_llm",
        _reviewer_should_continue,
        {"tools": "tools", "done": END},
    )
    graph.add_edge("tools", "reviewer_llm")

    return graph.compile()


_reviewer_graph = None


def _get_reviewer_graph():
    """Lazy-compile the reviewer subgraph."""
    global _reviewer_graph
    if _reviewer_graph is None:
        _reviewer_graph = _build_reviewer_subgraph()
    return _reviewer_graph


# ---------------------------------------------------------------------------
# Top-level graph node
# ---------------------------------------------------------------------------

def review_findings(state: InvestigationCycleState) -> dict:
    """Review accumulated findings — quality gate between investigators and evaluator."""
    findings = state.get("findings", [])
    hypotheses = state.get("hypotheses", [])
    run_id = state.get("run_id", "")

    logger.info(
        "review_findings started run_id=%s findings=%d hypotheses=%d",
        run_id, len(findings), len(hypotheses),
    )

    if not findings:
        logger.info("review_findings: no findings to review, skipping")
        return {
            "review_annotations": [],
            "digest_lines": ["[review] No findings to review — skipped"],
        }

    review_input = _build_review_input(findings, hypotheses)
    system_prompt = _get_reviewer_prompt()

    messages: list[BaseMessage] = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=review_input),
    ]

    # Run the reviewer subgraph (tool loop)
    reviewer_graph = _get_reviewer_graph()
    result = reviewer_graph.invoke({"messages": messages, "llm_calls": 0})

    # Extract annotations from the last AI message
    annotations: list[ReviewAnnotation] = []
    for msg in reversed(result["messages"]):
        if isinstance(msg, AIMessage) and msg.content:
            annotations = _parse_annotations(msg.content, findings)
            break

    # Build digest
    digest_lines = [
        f"[review] Reviewed {len(findings)} findings, produced {len(annotations)} annotations"
    ]
    for ann in annotations:
        digest_lines.append(
            f"[review] [{ann.assessment.value}] \"{ann.finding_statement[:60]}\" "
            f"→ {ann.suggested_action.value}"
        )

    logger.info(
        "review_findings completed run_id=%s annotations=%d",
        run_id, len(annotations),
    )

    return {
        "review_annotations": annotations,
        "digest_lines": digest_lines,
    }
