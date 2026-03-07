"""Top-level investigation cycle graph.

Flow:
    START → orchestrator_plan → [fan-out] investigate_topic → orchestrator_evaluate
      → [_route_after_evaluate] → "synthesize" OR [fan-out] investigate_topic (LOOP)
    synthesize → orchestrator_checkpoint → END (interrupt for human review)
"""

from __future__ import annotations

import logging

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from llm_pipeline.agents.investigator import build_investigator_graph
from llm_pipeline.agents.orchestrator import (
    orchestrator_checkpoint,
    orchestrator_evaluate,
    orchestrator_plan,
)
from llm_pipeline.agents.state import InvestigationCycleState, InvestigatorState

logger = logging.getLogger(__name__)

# Pre-compiled investigator subgraph
_investigator_graph = build_investigator_graph()


def _investigate_topic(state: InvestigatorState) -> dict:
    """Run a single investigator instance for one topic.

    Catches exceptions to prevent one failed investigator from crashing
    the entire fan-out.
    """
    from datetime import UTC, datetime

    from llm_pipeline.agents.models import Finding, FindingStatus

    topic = state["topic"]
    try:
        result = _investigator_graph.invoke(state)
        return {
            "findings": result.get("findings", []),
            "hypotheses": result.get("hypotheses", []),
            "digest_lines": result.get("digest_lines", []),
            "completed_topics": [topic.title],
            "topic_errors": [],
        }
    except Exception as e:
        error_msg = f"{topic.title}: {type(e).__name__}: {e}"
        logger.error("Investigator failed for topic '%s': %s", topic.title, e)
        fallback = Finding(
            topic_title=topic.title,
            statement=f"Investigation failed: {type(e).__name__}: {e}",
            status=FindingStatus.INCONCLUSIVE,
            evidence=[],
            created_at=datetime.now(UTC),
            run_id=state.get("run_id", ""),
            tool_use_failed=True,
        )
        return {
            "findings": [fallback],
            "hypotheses": [],
            "digest_lines": [f"[error] Investigator crashed: {error_msg}"],
            "completed_topics": [topic.title],
            "topic_errors": [error_msg],
        }


def _route_investigations(state: InvestigationCycleState) -> list[Send]:
    """Fan out: dispatch one investigator per topic."""
    topics = state.get("investigation_plan", [])
    run_id = state.get("run_id", "")

    sends = []
    for topic in topics:
        sends.append(
            Send(
                "investigate_topic",
                {
                    "topic": topic,
                    "run_id": run_id,
                    "messages": [],
                    "findings": [],
                    "hypotheses": [],
                    "digest_lines": [],
                    "prior_context": "",
                },
            )
        )
    return sends


def _build_prior_context(state: InvestigationCycleState) -> str:
    """Build a plain-text summary of prior findings for follow-up investigators."""
    findings = state.get("prior_findings", [])
    hypotheses = state.get("prior_hypotheses", [])

    if not findings and not hypotheses:
        return ""

    lines = []
    if findings:
        lines.append("Previous findings:")
        for f in findings:
            lines.append(f"  [{f.status.value}] {f.statement}")
            if f.evidence:
                for e in f.evidence[:2]:
                    lines.append(f"    - {e}")

    if hypotheses:
        lines.append("Untested hypotheses from prior rounds:")
        for h in hypotheses:
            lines.append(f"  - {h.statement} ({h.reasoning})")

    return "\n".join(lines)


def _route_after_evaluate(
    state: InvestigationCycleState,
) -> str | list[Send]:
    """Route after evaluation: synthesize if done, or fan-out for more investigation."""
    topics = state.get("investigation_plan", [])

    if not topics:
        return "synthesize"

    # Build prior context for follow-up investigators
    prior_context = _build_prior_context(state)
    run_id = state.get("run_id", "")

    sends = []
    for topic in topics:
        sends.append(
            Send(
                "investigate_topic",
                {
                    "topic": topic,
                    "run_id": run_id,
                    "messages": [],
                    "findings": [],
                    "hypotheses": [],
                    "digest_lines": [],
                    "prior_context": prior_context,
                },
            )
        )
    return sends


def _synthesize_placeholder(state: InvestigationCycleState) -> dict:
    """Placeholder for the synthesizer agent (Phase B).

    For now, just pass through — the checkpoint will contain the findings.
    """
    findings = state.get("findings", [])
    return {
        "digest_lines": [f"[synthesize] Placeholder: {len(findings)} findings ready for synthesis"],
    }


def build_investigation_graph():
    """Build and compile the top-level investigation cycle graph."""
    graph = StateGraph(InvestigationCycleState)

    # Nodes
    graph.add_node("orchestrator_plan", orchestrator_plan)
    graph.add_node("investigate_topic", _investigate_topic)
    graph.add_node("orchestrator_evaluate", orchestrator_evaluate)
    graph.add_node("synthesize", _synthesize_placeholder)
    graph.add_node("orchestrator_checkpoint", orchestrator_checkpoint)

    # Edges
    graph.add_edge(START, "orchestrator_plan")
    graph.add_conditional_edges("orchestrator_plan", _route_investigations)
    graph.add_edge("investigate_topic", "orchestrator_evaluate")
    graph.add_conditional_edges(
        "orchestrator_evaluate",
        _route_after_evaluate,
        {"synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", "orchestrator_checkpoint")
    graph.add_edge("orchestrator_checkpoint", END)

    return graph.compile()
