"""Top-level investigation cycle graph.

Flow:
    START → orchestrator_plan → [fan-out] investigate_{agent_type} → review_findings
      → orchestrator_evaluate → [_route_after_evaluate]
      → "assemble_report" OR [fan-out] investigate_{agent_type} (LOOP)
    assemble_report → synthesize_narrative → orchestrator_checkpoint → END
"""

from __future__ import annotations

import logging
import time

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from llm_pipeline.agents.orchestrator import (
    orchestrator_checkpoint,
    orchestrator_evaluate,
    orchestrator_plan,
)
from llm_pipeline.agents.registry import get_investigation_agents
from llm_pipeline.agents.reviewer import review_findings
from llm_pipeline.agents.state import InvestigationCycleState, InvestigatorState
from llm_pipeline.agents.synthesizer import synthesize_narrative

logger = logging.getLogger(__name__)

# Lazy-compiled graph cache per agent name
_compiled_cache: dict[str, object] = {}


def _make_investigate_runner(manifest):
    """Create a runner function for an investigation agent.

    Uses lazy compilation — the agent's graph is compiled on first invocation.
    """
    def _run(state: InvestigatorState) -> dict:
        from datetime import UTC, datetime

        from llm_pipeline.agents.models import Finding, FindingStatus

        topic = state["topic"]
        run_id = state.get("run_id", "")
        logger.info(
            "investigate_%s started run_id=%s topic=%s priority=%s",
            manifest.name,
            run_id,
            topic.title,
            topic.priority,
        )
        t0 = time.monotonic()
        try:
            # Lazy compile
            if manifest.name not in _compiled_cache:
                _compiled_cache[manifest.name] = manifest.build_graph()
            compiled = _compiled_cache[manifest.name]

            result = compiled.invoke(state)
            findings = result.get("findings", [])
            hypotheses = result.get("hypotheses", [])
            elapsed = time.monotonic() - t0
            logger.info(
                "investigate_%s completed run_id=%s topic=%s "
                "findings=%d hypotheses=%d elapsed_s=%.2f",
                manifest.name,
                run_id,
                topic.title,
                len(findings),
                len(hypotheses),
                elapsed,
            )
            raw_output = {
                "findings": findings,
                "hypotheses": hypotheses,
                "digest_lines": result.get("digest_lines", []),
                "completed_topics": [topic.title],
                "topic_errors": [],
            }
            if manifest.result_adapter:
                return manifest.result_adapter.adapt(raw_output)
            return raw_output
        except Exception as e:
            elapsed = time.monotonic() - t0
            error_msg = f"{topic.title}: {type(e).__name__}: {e}"
            logger.error(
                "Investigator %s failed for topic '%s': %s elapsed_s=%.2f",
                manifest.name,
                topic.title,
                e,
                elapsed,
            )

            # Salvage any findings/hypotheses reported before the crash
            from llm_pipeline.agents.plugins.investigator.extract import _extract_results

            salvaged_findings: list[Finding] = []
            salvaged_hypotheses = []
            digest_lines: list[str] = [f"[error] Investigator crashed: {error_msg}"]
            try:
                salvaged = _extract_results(state)
                salvaged_findings = salvaged.get("findings", [])
                salvaged_hypotheses = salvaged.get("hypotheses", [])
                digest_lines.extend(salvaged.get("digest_lines", []))
                if salvaged_findings:
                    logger.info(
                        "Salvaged %d findings, %d hypotheses from crashed investigator '%s'",
                        len(salvaged_findings),
                        len(salvaged_hypotheses),
                        topic.title,
                    )
            except Exception:
                logger.debug(
                    "Could not salvage findings from crashed investigator '%s'",
                    topic.title,
                )

            # If nothing was salvaged, create a fallback finding
            if not salvaged_findings:
                salvaged_findings = [
                    Finding(
                        topic_title=topic.title,
                        statement=f"Investigation failed: {type(e).__name__}: {e}",
                        status=FindingStatus.INCONCLUSIVE,
                        evidence=[],
                        created_at=datetime.now(UTC),
                        run_id=state.get("run_id", ""),
                        tool_use_failed=True,
                    )
                ]

            return {
                "findings": salvaged_findings,
                "hypotheses": salvaged_hypotheses,
                "digest_lines": digest_lines,
                "completed_topics": [topic.title],
                "topic_errors": [error_msg],
            }

    return _run


def _route_investigations(state: InvestigationCycleState) -> list[Send]:
    """Fan out: dispatch one investigator per topic, routing by agent_type."""
    from llm_pipeline.agents.roles import get_role_grounding

    topics = state.get("investigation_plan", [])
    run_id = state.get("run_id", "")
    ml_run_id = state.get("ml_run_id", "") or run_id
    logger.info("fan_out dispatching run_id=%s topic_count=%d", run_id, len(topics))

    sends = []
    for topic in topics:
        agent_name = getattr(topic, "agent_type", "investigator") or "investigator"
        node_name = f"investigate_{agent_name}"
        grounding_context = get_role_grounding(topic.role)
        sends.append(
            Send(
                node_name,
                {
                    "topic": topic,
                    "run_id": run_id,
                    "ml_run_id": ml_run_id,
                    "messages": [],
                    "findings": [],
                    "hypotheses": [],
                    "digest_lines": [],
                    "prior_context": "",
                    "grounding_context": grounding_context,
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
    run_id = state.get("run_id", "")
    ml_run_id = state.get("ml_run_id", "") or run_id

    if not topics:
        logger.debug("routing to assemble_report run_id=%s", run_id)
        return "assemble_report"

    from llm_pipeline.agents.roles import get_role_grounding

    logger.info("follow_up dispatching run_id=%s topic_count=%d", run_id, len(topics))

    # Build prior context for follow-up investigators
    prior_context = _build_prior_context(state)

    sends = []
    for topic in topics:
        agent_name = getattr(topic, "agent_type", "investigator") or "investigator"
        node_name = f"investigate_{agent_name}"
        grounding_context = get_role_grounding(topic.role)
        sends.append(
            Send(
                node_name,
                {
                    "topic": topic,
                    "run_id": run_id,
                    "ml_run_id": ml_run_id,
                    "messages": [],
                    "findings": [],
                    "hypotheses": [],
                    "digest_lines": [],
                    "prior_context": prior_context,
                    "grounding_context": grounding_context,
                },
            )
        )
    return sends


def _assemble_report(state: InvestigationCycleState) -> dict:
    """Build structured investigation report from ML data and findings.

    Deterministic assembly — no LLM calls. Delegates to the active domain's
    report_builder if one exists, otherwise returns findings as-is.
    """
    from llm_pipeline.agents.domain_registry import get_active_domain

    ml_report = state.get("ml_report")
    run_id = state.get("run_id", "")
    findings = state.get("findings", [])
    hypotheses = state.get("hypotheses", [])
    digest_lines = state.get("digest_lines", [])

    if ml_report is None:
        logger.warning("synthesize: no ml_report in state, skipping report assembly")
        return {
            "digest_lines": [
                f"[synthesize] No ML report available; {len(findings)} findings ready"
            ],
        }

    domain = get_active_domain()
    if domain is None or domain.report_builder is None:
        logger.warning("synthesize: no domain report builder, skipping report assembly")
        return {
            "digest_lines": [
                f"[synthesize] No report builder; {len(findings)} findings ready"
            ],
        }

    report = domain.report_builder(
        run_id=run_id,
        ml_run_id=ml_report.run_id,
        ml_report=ml_report,
        findings=findings,
        hypotheses=hypotheses,
        digest_lines=digest_lines,
    )

    logger.info(
        "synthesize completed run_id=%s segments=%d issues=%d trends=%d",
        run_id,
        len(report.structured.segment_health),
        len(report.structured.confirmed_issues),
        report.structured.trend_summary.degrading_count
        + report.structured.trend_summary.improving_count
        + report.structured.trend_summary.stable_count,
    )

    return {
        "report": report,
        "digest_lines": [
            f"[synthesize] Report assembled: "
            f"{len(report.structured.segment_health)} segments, "
            f"{len(report.structured.confirmed_issues)} confirmed issues, "
            f"{len(report.notes.hypotheses)} hypotheses"
        ],
    }


def build_investigation_graph():
    """Build and compile the top-level investigation cycle graph.

    Dynamically registers one node per discovered investigation agent plugin.
    """
    agents = get_investigation_agents()
    graph = StateGraph(InvestigationCycleState)

    # Nodes
    graph.add_node("orchestrator_plan", orchestrator_plan)
    graph.add_node("review_findings", review_findings)
    graph.add_node("orchestrator_evaluate", orchestrator_evaluate)
    graph.add_node("assemble_report", _assemble_report)
    graph.add_node("synthesize_narrative", synthesize_narrative)
    graph.add_node("orchestrator_checkpoint", orchestrator_checkpoint)

    # Register one node per discovered investigation agent
    for agent_name, manifest in agents.items():
        node_name = f"investigate_{agent_name}"
        graph.add_node(node_name, _make_investigate_runner(manifest))

    # Fallback: if no agents discovered, add a default investigate_investigator node
    # (shouldn't happen in practice but prevents graph build errors)
    if not agents:
        logger.warning("No investigation agents discovered — graph may not function correctly")

    # Edges
    graph.add_edge(START, "orchestrator_plan")
    graph.add_conditional_edges("orchestrator_plan", _route_investigations)

    # All investigation nodes → review_findings → orchestrator_evaluate
    for agent_name in agents:
        graph.add_edge(f"investigate_{agent_name}", "review_findings")

    graph.add_edge("review_findings", "orchestrator_evaluate")

    graph.add_conditional_edges(
        "orchestrator_evaluate",
        _route_after_evaluate,
        {"assemble_report": "assemble_report"},
    )
    graph.add_edge("assemble_report", "synthesize_narrative")
    graph.add_edge("synthesize_narrative", "orchestrator_checkpoint")
    graph.add_edge("orchestrator_checkpoint", END)

    return graph.compile()
