"""Top-level investigation cycle graph.

Flow:
    START → orchestrator_plan → run_investigations → orchestrator_evaluate
      → [synthesize] → orchestrator_checkpoint → END (interrupt for human review)
"""

from __future__ import annotations

import logging

from langgraph.constants import Send
from langgraph.graph import END, START, StateGraph

from llm_pipeline.agents.investigator import build_investigator_graph
from llm_pipeline.agents.orchestrator import (
    orchestrator_checkpoint,
    orchestrator_evaluate,
    orchestrator_plan,
    should_continue_or_synthesize,
)
from llm_pipeline.agents.state import InvestigationCycleState, InvestigatorState

logger = logging.getLogger(__name__)

# Pre-compiled investigator subgraph
_investigator_graph = build_investigator_graph()


def _investigate_topic(state: InvestigatorState) -> dict:
    """Run a single investigator instance for one topic."""
    result = _investigator_graph.invoke(state)
    # Return only the fan-in fields
    return {
        "findings": result.get("findings", []),
        "hypotheses": result.get("hypotheses", []),
        "digest_lines": result.get("digest_lines", []),
        "completed_topics": [state["topic"].title],
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
        should_continue_or_synthesize,
        {"synthesize": "synthesize"},
    )
    graph.add_edge("synthesize", "orchestrator_checkpoint")
    graph.add_edge("orchestrator_checkpoint", END)

    return graph.compile()
