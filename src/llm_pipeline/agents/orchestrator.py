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
from llm_pipeline.models.token_tracker import get_tracker
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
        f"Create up to {settings.circuit_breaker_max_topics} focused investigation topics, prioritized by severity and impact. "
        f"Respond with a JSON array of objects, each with fields: "
        f"title, dimension, dimension_value, metrics (array), question, priority, context.\n"
        f"Respond with ONLY the JSON array, no other text."
    )

    response = llm.invoke([
        SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    get_tracker().record(response, model=settings.model_orchestrator)

    # Parse the response into InvestigationTopics
    topics = _parse_topics(response.content)

    budget = CircuitBreakerBudget(
        max_iterations=settings.circuit_breaker_max_iterations,
        max_seconds=settings.circuit_breaker_max_seconds,
        max_spend_usd=settings.circuit_breaker_max_spend_usd,
    )

    return {
        "investigation_plan": topics,
        "budget": budget,
        "started_at": datetime.now(UTC),
        "iteration_count": 0,
        "digest_lines": [f"[plan] Created {len(topics)} investigation topics from {run_id}"],
    }


def orchestrator_evaluate(state: InvestigationCycleState) -> dict:
    """Evaluate results from investigators, decide whether to continue.

    Uses LLM to assess findings and generate follow-up topics if needed.
    Respects circuit breaker budget — stops iteration when limits exceeded.
    """
    findings = state.get("findings", [])
    hypotheses = state.get("hypotheses", [])
    iteration_count = state.get("iteration_count", 0) + 1
    started_at = state.get("started_at", datetime.now(UTC))
    budget = state.get("budget", CircuitBreakerBudget())

    budget_check = check_budget_exceeded(
        iteration_count=iteration_count,
        started_at_ts=started_at.timestamp(),
        budget=budget,
    )

    tracker = get_tracker()
    digest_lines = [
        f"[eval] Iteration {iteration_count}: "
        f"{len(findings)} findings, {len(hypotheses)} hypotheses, "
        f"{budget_check['elapsed_seconds']}s elapsed, "
        f"spend=${tracker.total_cost_usd:.2f}"
    ]

    # If budget exceeded, stop iteration
    if budget_check["exceeded"]:
        reasons = ", ".join(budget_check["reasons"])
        digest_lines.append(f"[circuit_breaker] Budget exceeded: {reasons}")
        return {
            "iteration_count": iteration_count,
            "investigation_plan": [],
            "prior_findings": findings,
            "prior_hypotheses": hypotheses,
            "digest_lines": digest_lines,
        }

    # Check if all findings are resolved (no INCONCLUSIVE, no untested hypotheses)
    has_inconclusive = any(f.status.value == "inconclusive" for f in findings)
    has_hypotheses = len(hypotheses) > 0

    if not has_inconclusive and not has_hypotheses:
        digest_lines.append("[eval] All findings resolved, no untested hypotheses — stopping")
        return {
            "iteration_count": iteration_count,
            "investigation_plan": [],
            "prior_findings": findings,
            "prior_hypotheses": hypotheses,
            "digest_lines": digest_lines,
        }

    # Ask the LLM if follow-up investigation is warranted
    findings_summary = []
    for f in findings:
        line = f"[{f.status.value}] {f.statement}"
        if f.evidence:
            line += f" (evidence: {'; '.join(f.evidence[:2])})"
        findings_summary.append(line)

    hypotheses_summary = [f"[untested] {h.statement} — {h.reasoning}" for h in hypotheses]

    findings_block = "\n".join(findings_summary)
    hypotheses_block = "\n".join(hypotheses_summary) or "(none)"
    eval_prompt = (
        f"You are evaluating investigation results after iteration {iteration_count}.\n\n"
        f"Findings so far:\n{findings_block}\n\n"
        f"Untested hypotheses:\n{hypotheses_block}\n\n"
        "Should we investigate further? If yes, create 1-2 focused follow-up topics "
        "to test untested hypotheses or resolve inconclusive findings.\n"
        "If the findings are sufficient, respond with an empty JSON array [].\n"
        f"Respond with ONLY a JSON array of up to {settings.circuit_breaker_max_topics} investigation topic objects "
        "(fields: title, dimension, dimension_value, metrics, question, priority, context), "
        "or an empty array []."
    )

    try:
        llm = get_llm(role="orchestrator")
        response = llm.invoke([
            SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
            HumanMessage(content=eval_prompt),
        ])
        get_tracker().record(response, model=settings.model_orchestrator)
        follow_up_topics = _parse_topics(response.content)
    except Exception as e:
        logger.warning("Failed to get follow-up evaluation: %s", e)
        follow_up_topics = []

    if follow_up_topics:
        digest_lines.append(
            f"[eval] Generated {len(follow_up_topics)} follow-up topics"
        )
    else:
        digest_lines.append("[eval] No follow-up needed — moving to synthesis")

    return {
        "iteration_count": iteration_count,
        "investigation_plan": follow_up_topics,
        "prior_findings": findings,
        "prior_hypotheses": hypotheses,
        "digest_lines": digest_lines,
    }


def orchestrator_checkpoint(state: InvestigationCycleState) -> dict:
    """Produce the final checkpoint digest for human review."""
    digest_lines = state.get("digest_lines", [])
    findings = state.get("findings", [])
    hypotheses = state.get("hypotheses", [])

    sections = ["# Investigation Checkpoint\n"]
    sections.append(f"Run: {state.get('run_id', 'unknown')}")
    sections.append(f"Iterations: {state.get('iteration_count', 0)}")
    sections.append(f"Findings: {len(findings)}")
    sections.append(f"Hypotheses: {len(hypotheses)}")
    sections.append(f"Spend: {get_tracker().summary()}\n")

    # Group findings by status
    if findings:
        by_status: dict[str, list] = {}
        for f in findings:
            by_status.setdefault(f.status.value, []).append(f)

        for status_label in ["confirmed", "disproven", "inconclusive"]:
            group = by_status.get(status_label, [])
            if not group:
                continue
            sections.append(f"## Findings — {status_label.upper()}")
            for f in group:
                sections.append(f"- {f.statement}")
                if f.evidence:
                    for e in f.evidence[:3]:
                        sections.append(f"  evidence: {e}")
                if f.metrics_cited:
                    metrics_str = ", ".join(f"{k}={v}" for k, v in f.metrics_cited.items())
                    sections.append(f"  metrics: {metrics_str}")
            sections.append("")

    if hypotheses:
        sections.append("## Hypotheses (untested)")
        for h in hypotheses:
            sections.append(f"- {h.statement}")
            if h.reasoning:
                sections.append(f"  reasoning: {h.reasoning}")
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
        # Coerce unknown priority values to valid enum values
        _PRIORITY_MAP = {"critical": "high", "urgent": "high", "normal": "medium", "minor": "low"}
        _VALID_PRIORITIES = {"high", "medium", "low"}
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict) and "priority" in item:
                    p = str(item["priority"]).lower()
                    if p not in _VALID_PRIORITIES:
                        item["priority"] = _PRIORITY_MAP.get(p, "high")
        adapter = TypeAdapter(list[InvestigationTopic])
        return adapter.validate_python(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse investigation topics: %s", e)
        return []
