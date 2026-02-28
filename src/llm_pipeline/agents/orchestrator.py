"""Orchestrator agent — plans investigations and tracks circuit breaker state."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import TypeAdapter

from llm_pipeline.agents.models import CircuitBreakerBudget, InvestigationTopic
from llm_pipeline.agents.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigationCycleState
from llm_pipeline.config import settings
from llm_pipeline.models.llm import get_llm
from llm_pipeline.tools.circuit_breaker import check_budget_exceeded

logger = logging.getLogger(__name__)


def orchestrator_plan(state: InvestigationCycleState) -> dict:
    """Read ML report summary, produce investigation topics."""
    report = state["ml_report"]
    run_id = state["run_id"]

    # Build a summary of what's in the report for the LLM
    summary_lines = [
        f"ML Analysis Run: {run_id}",
        f"Events parsed: {report.events_parsed}",
        f"Aggregation buckets: {len(report.aggregations)}",
        f"Anomalies detected: {len(report.anomalies)}",
        f"Trends detected: {len(report.trends)}",
    ]

    if report.anomalies:
        summary_lines.append("\nAnomalies (sorted by |z_score|):")
        sorted_anomalies = sorted(report.anomalies, key=lambda a: abs(a.z_score), reverse=True)
        for a in sorted_anomalies[:10]:
            summary_lines.append(
                f"  [{a.severity}] {a.anomaly_type.value}: {a.dimension}={a.dimension_value} "
                f"({a.metric}: {a.current_value:.4f}, baseline: {a.baseline_mean:.4f}, "
                f"z={a.z_score:.2f})"
            )

    if report.trends:
        summary_lines.append("\nTrends:")
        for t in report.trends[:10]:
            summary_lines.append(
                f"  {t.direction.value}: {t.dimension}={t.dimension_value} "
                f"({t.metric}: {t.start_value:.4f} → {t.end_value:.4f}, R²={t.r_squared:.3f})"
            )

    summary = "\n".join(summary_lines)

    llm = get_llm(role="orchestrator")
    prompt = (
        f"Review this ML analysis report and create investigation topics.\n\n"
        f"{summary}\n\n"
        f"Create up to 3 focused investigation topics, prioritized by severity and impact. "
        f"Respond with a JSON array of objects, each with fields: "
        f"title, dimension, dimension_value, metrics (array), question, priority, context.\n"
        f"Respond with ONLY the JSON array, no other text."
    )

    response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    # Parse the response into InvestigationTopics
    topics = _parse_topics(response.content)

    budget = CircuitBreakerBudget(
        max_iterations=settings.circuit_breaker_max_iterations,
        max_seconds=settings.circuit_breaker_max_seconds,
    )

    return {
        "investigation_plan": topics,
        "budget": budget,
        "started_at": datetime.now(UTC),
        "iteration_count": 0,
        "digest_lines": [f"[plan] Created {len(topics)} investigation topics from {run_id}"],
    }


def orchestrator_evaluate(state: InvestigationCycleState) -> dict:
    """Evaluate results from investigators, decide whether to continue."""
    findings = state.get("findings", [])
    iteration_count = state.get("iteration_count", 0) + 1
    started_at = state.get("started_at", datetime.now(UTC))
    budget = state.get("budget", CircuitBreakerBudget())

    budget_check = check_budget_exceeded(
        iteration_count=iteration_count,
        started_at_ts=started_at.timestamp(),
        budget=budget,
    )

    digest_lines = [
        f"[eval] Iteration {iteration_count}: "
        f"{len(findings)} findings so far, "
        f"{budget_check['elapsed_seconds']}s elapsed"
    ]

    if budget_check["exceeded"]:
        reasons = ", ".join(budget_check["reasons"])
        digest_lines.append(f"[circuit_breaker] Budget exceeded: {reasons}")

    return {
        "iteration_count": iteration_count,
        "digest_lines": digest_lines,
    }


def should_continue_or_synthesize(state: InvestigationCycleState) -> str:
    """Route: continue investigating or move to synthesis."""
    budget = state.get("budget", CircuitBreakerBudget())
    started_at = state.get("started_at", datetime.now(UTC))
    iteration_count = state.get("iteration_count", 0)

    budget_check = check_budget_exceeded(
        iteration_count=iteration_count,
        started_at_ts=started_at.timestamp(),
        budget=budget,
    )

    if budget_check["exceeded"]:
        return "synthesize"
    return "synthesize"  # For Phase A, always go to synthesis after one round


def orchestrator_checkpoint(state: InvestigationCycleState) -> dict:
    """Produce the final checkpoint digest for human review."""
    digest_lines = state.get("digest_lines", [])
    findings = state.get("findings", [])
    hypotheses = state.get("hypotheses", [])

    sections = ["# Investigation Checkpoint\n"]
    sections.append(f"Run: {state.get('run_id', 'unknown')}")
    sections.append(f"Iterations: {state.get('iteration_count', 0)}")
    sections.append(f"Findings: {len(findings)}")
    sections.append(f"Hypotheses: {len(hypotheses)}\n")

    if findings:
        sections.append("## Findings")
        for f in findings:
            sections.append(f"- [{f.status.value}] {f.statement}")
            if f.evidence:
                for e in f.evidence[:3]:
                    sections.append(f"  - {e}")
        sections.append("")

    if hypotheses:
        sections.append("## Hypotheses (untested)")
        for h in hypotheses:
            sections.append(f"- {h.statement}")
        sections.append("")

    sections.append("## Investigation Log")
    for line in digest_lines:
        sections.append(f"- {line}")

    checkpoint_digest = "\n".join(sections)
    return {"checkpoint_digest": checkpoint_digest}


def _parse_topics(content: str) -> list[InvestigationTopic]:
    """Parse LLM response into InvestigationTopic list."""
    # Strip markdown code fences if present
    text = content.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first and last lines (```json and ```)
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)

    try:
        data = json.loads(text)
        adapter = TypeAdapter(list[InvestigationTopic])
        return adapter.validate_python(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse investigation topics: %s", e)
        return []
