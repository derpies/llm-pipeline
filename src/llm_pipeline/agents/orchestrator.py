"""Orchestrator agent — plans investigations and tracks circuit breaker state."""

from __future__ import annotations

import json
import logging
import time
from datetime import UTC, datetime

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import TypeAdapter

from llm_pipeline.agents.models import CircuitBreakerBudget, InvestigationTopic
from llm_pipeline.agents.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from llm_pipeline.agents.state import InvestigationCycleState
from llm_pipeline.config import settings
from llm_pipeline.models.llm import get_llm
from llm_pipeline.models.rate_limiter import get_rate_limiter
from llm_pipeline.models.token_tracker import get_tracker
from llm_pipeline.tools.circuit_breaker import check_budget_exceeded

logger = logging.getLogger(__name__)


def _get_orchestrator_prompt(domain_name: str | None = None) -> str:
    """Build the orchestrator system prompt with domain-specific role descriptions."""
    from llm_pipeline.agents.domain_registry import get_active_domain

    domain = get_active_domain(domain_name)
    if domain and domain.orchestrator_role_prompt:
        role_descriptions = domain.orchestrator_role_prompt
    else:
        role_descriptions = (
            '- role: Which specialist to assign. Default to "diagnostics" if unclear.'
        )
    return ORCHESTRATOR_SYSTEM_PROMPT.format(domain_role_descriptions=role_descriptions)


def _append_aggregation_summary(lines: list[str], aggregations: list) -> None:
    """Add a compact summary of aggregation data for the orchestrator."""
    from collections import defaultdict

    # Group by dimension, sum totals across values
    dim_totals: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for b in aggregations:
        dim_totals[b.dimension][b.dimension_value] += b.total

    for dim, values in sorted(dim_totals.items()):
        # Show top 5 values by volume
        top = sorted(values.items(), key=lambda x: x[1], reverse=True)[:5]
        total_all = sum(values.values())
        parts = ", ".join(f"{v}={c} ({100*c/total_all:.0f}%)" for v, c in top)
        lines.append(f"  {dim} (total={total_all}): {parts}")

    # Also show notable rates from a few high-volume buckets
    by_volume = sorted(aggregations, key=lambda b: b.total, reverse=True)
    notable = []
    for b in by_volume[:20]:
        # Look for non-trivial error rates or interesting patterns
        success_rate = getattr(b, "success_rate", None)
        if success_rate is not None and success_rate < 0.5 and b.total >= 100:
            notable.append(
                f"  ! {b.dimension}={b.dimension_value}: success_rate={success_rate:.2f} (n={b.total})"
            )
    if notable:
        lines.append("\nNotable low success rates:")
        lines.extend(notable[:10])


def _append_completeness_summary(lines: list[str], completeness: list) -> None:
    """Add a compact summary of data completeness metrics."""
    # Group by field_name, average the empty rates
    from collections import defaultdict

    field_rates: dict[str, list[float]] = defaultdict(list)
    for c in completeness:
        field_name = getattr(c, "field_name", None)
        empty_rate = getattr(c, "empty_rate", None) or getattr(c, "zero_rate", None)
        if field_name and empty_rate is not None and empty_rate > 0.1:
            field_rates[field_name].append(empty_rate)

    for field, rates in sorted(field_rates.items(), key=lambda x: -max(x[1])):
        avg_rate = sum(rates) / len(rates)
        if avg_rate > 0.1:
            lines.append(f"  {field}: avg empty rate {avg_rate:.1%} across {len(rates)} dimensions")


def orchestrator_plan(state: InvestigationCycleState) -> dict:
    """Read ML report summary, produce investigation topics."""
    report = state["ml_report"]
    run_id = state["run_id"]
    logger.info(
        "orchestrator_plan started run_id=%s anomalies=%d trends=%d",
        run_id,
        len(report.anomalies),
        len(report.trends),
    )
    t0 = time.monotonic()

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

    # When no anomalies/trends, include aggregation highlights so LLM has data to reason about
    if not report.anomalies and not report.trends and report.aggregations:
        summary_lines.append("\nAggregation highlights (top dimensions by volume):")
        _append_aggregation_summary(summary_lines, report.aggregations)

    # Include completeness highlights if available
    completeness = getattr(report, "completeness", [])
    if completeness:
        summary_lines.append("\nData completeness issues:")
        _append_completeness_summary(summary_lines, completeness)

    summary = "\n".join(summary_lines)

    llm = get_llm(role="orchestrator")
    prompt = (
        f"Review this ML analysis report and create investigation topics.\n\n"
        f"{summary}\n\n"
        f"Create up to {settings.circuit_breaker_max_topics} focused investigation topics, prioritized by severity and impact. "
        f"Respond with a JSON array of objects, each with fields: "
        f"title, dimension, dimension_value, metrics (array), question, priority, context, role.\n"
        f"Respond with ONLY the JSON array, no other text."
    )

    domain_name = state.get("domain_name")
    get_rate_limiter().acquire()
    response = llm.invoke(
        [
            SystemMessage(content=_get_orchestrator_prompt(domain_name)),
            HumanMessage(content=prompt),
        ]
    )
    get_tracker().record(response, model=settings.model_orchestrator)
    usage = getattr(response, "usage_metadata", None)
    if usage:
        inp = (usage.get("input_tokens", 0) if isinstance(usage, dict)
               else getattr(usage, "input_tokens", 0))
        get_rate_limiter().record(inp)

    # Parse the response into InvestigationTopics
    topics = _parse_topics(response.content, domain_name=domain_name)

    elapsed = time.monotonic() - t0
    logger.info(
        "orchestrator_plan completed run_id=%s topics=%d elapsed_s=%.2f",
        run_id,
        len(topics),
        elapsed,
    )

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
    run_id = state.get("run_id", "")
    logger.info(
        "orchestrator_evaluate started run_id=%s iteration=%d findings=%d hypotheses=%d",
        run_id,
        iteration_count,
        len(findings),
        len(hypotheses),
    )
    t0 = time.monotonic()

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
        logger.warning(
            "orchestrator_evaluate budget_exceeded run_id=%s iteration=%d reasons=%s",
            run_id,
            iteration_count,
            reasons,
        )
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

    # Include reviewer annotations if available
    review_annotations = state.get("review_annotations", [])
    annotations_block = ""
    if review_annotations:
        ann_lines = ["Reviewer assessments:"]
        for ann in review_annotations:
            ann_lines.append(
                f"  [{ann.assessment.value}] \"{ann.finding_statement[:80]}\" "
                f"— \"{ann.reasoning}\""
            )
            if ann.suggested_action.value == "investigate_further" and ann.follow_up_question:
                ann_lines.append(f"    → investigate_further: \"{ann.follow_up_question}\"")
            else:
                ann_lines.append(f"    → {ann.suggested_action.value}")
        annotations_block = "\n" + "\n".join(ann_lines) + "\n"

    eval_prompt = (
        f"You are evaluating investigation results after iteration {iteration_count}.\n\n"
        f"Findings so far:\n{findings_block}\n\n"
        f"Untested hypotheses:\n{hypotheses_block}\n"
        f"{annotations_block}\n"
        "Should we investigate further? If yes, create 1-2 focused follow-up topics "
        "to test untested hypotheses or resolve inconclusive findings. "
        "Pay attention to reviewer assessments — findings marked 'investigate_further' "
        "with follow-up questions are strong candidates for follow-up topics.\n"
        "If the findings are sufficient, respond with an empty JSON array [].\n"
        f"Respond with ONLY a JSON array of up to {settings.circuit_breaker_max_topics} investigation topic objects "
        "(fields: title, dimension, dimension_value, metrics, question, priority, context, role), "
        "or an empty array []."
    )

    domain_name = state.get("domain_name")
    evaluation_error = False
    try:
        llm = get_llm(role="orchestrator")
        get_rate_limiter().acquire()
        response = llm.invoke(
            [
                SystemMessage(content=_get_orchestrator_prompt(domain_name)),
                HumanMessage(content=eval_prompt),
            ]
        )
        get_tracker().record(response, model=settings.model_orchestrator)
        usage = getattr(response, "usage_metadata", None)
        if usage:
            inp = (usage.get("input_tokens", 0) if isinstance(usage, dict)
                   else getattr(usage, "input_tokens", 0))
            get_rate_limiter().record(inp)
        follow_up_topics = _parse_topics(response.content, domain_name=domain_name)
    except Exception as e:
        logger.error("Orchestrator evaluation failed: %s: %s", type(e).__name__, e)
        digest_lines.append(f"[error] Orchestrator evaluation failed: {type(e).__name__}: {e}")
        evaluation_error = True
        follow_up_topics = []

    if follow_up_topics:
        digest_lines.append(f"[eval] Generated {len(follow_up_topics)} follow-up topics")
    elif not evaluation_error:
        digest_lines.append("[eval] No follow-up needed — moving to synthesis")

    elapsed = time.monotonic() - t0
    decision = "follow_up" if follow_up_topics else ("error" if evaluation_error else "synthesize")
    logger.info(
        "orchestrator_evaluate completed run_id=%s iteration=%d "
        "decision=%s follow_up=%d elapsed_s=%.2f",
        run_id,
        iteration_count,
        decision,
        len(follow_up_topics),
        elapsed,
    )

    return {
        "iteration_count": iteration_count,
        "investigation_plan": follow_up_topics,
        "prior_findings": findings,
        "prior_hypotheses": hypotheses,
        "digest_lines": digest_lines,
        "evaluation_error": evaluation_error,
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

    # Reviewer annotations
    review_annotations = state.get("review_annotations", [])
    if review_annotations:
        sections.append("## Reviewer Annotations")
        for ann in review_annotations:
            sections.append(
                f"- [{ann.assessment.value}] {ann.finding_statement[:80]} "
                f"→ {ann.suggested_action.value}"
            )
            if ann.reasoning:
                sections.append(f"  reasoning: {ann.reasoning}")
            if ann.follow_up_question:
                sections.append(f"  follow-up: {ann.follow_up_question}")
        sections.append("")

    # Synthesis narrative
    synthesis_narrative = state.get("synthesis_narrative", "")
    if synthesis_narrative:
        sections.append("## Synthesis")
        sections.append(synthesis_narrative)
        sections.append("")

    # Surface errors prominently
    error_lines = [line for line in digest_lines if line.startswith("[error]")]
    if error_lines:
        sections.append("## Errors")
        for line in error_lines:
            sections.append(f"- {line}")
        sections.append("")

    sections.append("## Investigation Log")
    for line in digest_lines:
        sections.append(f"- {line}")

    checkpoint_digest = "\n".join(sections)
    logger.info(
        "orchestrator_checkpoint produced run_id=%s findings=%d hypotheses=%d digest_len=%d",
        state.get("run_id", ""),
        len(findings),
        len(hypotheses),
        len(checkpoint_digest),
    )
    return {"checkpoint_digest": checkpoint_digest}


def _parse_topics(content: str, *, domain_name: str | None = None) -> list[InvestigationTopic]:
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
        # Get valid roles from active domain
        from llm_pipeline.agents.domain_registry import get_domain_roles

        _VALID_ROLES = set(get_domain_roles(domain_name).keys())

        # Get valid agent types from registry
        from llm_pipeline.agents.registry import get_investigation_agents

        _VALID_AGENT_TYPES = set(get_investigation_agents().keys())

        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    if "priority" in item:
                        p = str(item["priority"]).lower()
                        if p not in _VALID_PRIORITIES:
                            item["priority"] = _PRIORITY_MAP.get(p, "high")
                    if "role" in item:
                        r = str(item["role"]).lower()
                        if r not in _VALID_ROLES:
                            item["role"] = "diagnostics"
                    # Coerce invalid agent_type to default
                    if "agent_type" in item:
                        at = str(item["agent_type"]).lower()
                        if _VALID_AGENT_TYPES and at not in _VALID_AGENT_TYPES:
                            item["agent_type"] = "investigator"
        adapter = TypeAdapter(list[InvestigationTopic])
        return adapter.validate_python(data)
    except (json.JSONDecodeError, Exception) as e:
        logger.warning("Failed to parse investigation topics: %s", e)
        return []
