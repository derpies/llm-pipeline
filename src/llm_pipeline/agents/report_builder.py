"""Deterministic report assembly — pure functions, no LLM calls.

Each function builds one section of the structured report from ML data
and investigation findings.
"""

from __future__ import annotations

from datetime import UTC, datetime

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.agents.report_models import (
    CompletenessRow,
    ComplianceRow,
    ConfirmedIssue,
    InvestigationNotes,
    InvestigationReport,
    SegmentHealthRow,
    StructuredReport,
    TrendRow,
    TrendSummary,
)
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnalysisReport,
    DataCompleteness,
    TrendFinding,
)


def build_segment_health(
    aggregations: list[AggregationBucket],
) -> list[SegmentHealthRow]:
    """Build segment health rows from engagement_segment aggregations.

    Uses the most recent time_window per segment.
    """
    # Filter to engagement_segment dimension
    seg_buckets = [a for a in aggregations if a.dimension == "engagement_segment"]
    if not seg_buckets:
        return []

    # Keep only the most recent time_window per segment
    latest: dict[str, AggregationBucket] = {}
    for b in seg_buckets:
        existing = latest.get(b.dimension_value)
        if existing is None or b.time_window > existing.time_window:
            latest[b.dimension_value] = b

    rows = []
    for seg in sorted(latest.keys()):
        b = latest[seg]
        rows.append(
            SegmentHealthRow(
                segment=seg,
                total=b.total,
                delivery_rate=b.delivery_rate,
                bounce_rate=b.bounce_rate,
                deferral_rate=b.deferral_rate,
                complaint_rate=b.complaint_rate,
                delivery_time_mean=b.delivery_time_mean,
                delivery_time_p50=b.delivery_time_p50,
                delivery_time_p95=b.delivery_time_p95,
                delivery_time_p99=b.delivery_time_p99,
                delivery_time_max=b.delivery_time_max,
                pre_edge_latency_mean=b.pre_edge_latency_mean,
                pre_edge_latency_p50=b.pre_edge_latency_p50,
                pre_edge_latency_p95=b.pre_edge_latency_p95,
                pre_edge_latency_p99=b.pre_edge_latency_p99,
                pre_edge_latency_max=b.pre_edge_latency_max,
            )
        )
    return rows


def build_confirmed_issues(findings: list[Finding]) -> list[ConfirmedIssue]:
    """Extract confirmed findings into structured issues."""
    issues = []
    for f in findings:
        if f.status != FindingStatus.CONFIRMED:
            continue

        # Extract dimension info from topic_title if available
        dimension = ""
        dimension_value = ""
        metric = ""

        # Try to extract from metrics_cited keys
        if f.metrics_cited:
            metric = next(iter(f.metrics_cited.keys()), "")

        # Build magnitude from metrics_cited values
        if f.metrics_cited:
            parts = [f"{k}={v}" for k, v in f.metrics_cited.items()]
            magnitude = ", ".join(parts)
        else:
            magnitude = "see evidence"

        evidence_summary = "; ".join(f.evidence[:3]) if f.evidence else f.statement

        issues.append(
            ConfirmedIssue(
                dimension=dimension,
                dimension_value=dimension_value,
                metric=metric,
                magnitude=magnitude,
                evidence_summary=evidence_summary,
            )
        )
    return issues


def build_trend_summary(
    trends: list[TrendFinding],
    top_n: int = 5,
) -> TrendSummary:
    """Count trends by direction and extract top movers by abs(slope)."""
    degrading = 0
    improving = 0
    stable = 0

    trend_rows = []
    for t in trends:
        direction = t.direction.value
        if direction == "degrading":
            degrading += 1
        elif direction == "improving":
            improving += 1
        else:
            stable += 1

        trend_rows.append(
            TrendRow(
                dimension=t.dimension,
                dimension_value=t.dimension_value,
                metric=t.metric,
                direction=direction,
                slope=t.slope,
                start_value=t.start_value,
                end_value=t.end_value,
            )
        )

    # Sort by absolute slope descending for top movers
    trend_rows.sort(key=lambda r: abs(r.slope), reverse=True)

    return TrendSummary(
        degrading_count=degrading,
        improving_count=improving,
        stable_count=stable,
        top_movers=trend_rows[:top_n],
    )


def build_data_completeness(
    completeness: list[DataCompleteness],
    threshold: float = 0.10,
) -> list[CompletenessRow]:
    """Map completeness records to rows, flagging high zero-rates."""
    rows = []
    for c in completeness:
        rows.append(
            CompletenessRow(
                field_name=c.field_name,
                dimension=c.dimension,
                dimension_value=c.dimension_value,
                zero_rate=c.zero_rate,
                total_records=c.total_records,
                flagged=c.zero_rate >= threshold,
            )
        )
    return rows


def build_compliance(
    aggregations: list[AggregationBucket],
) -> list[ComplianceRow]:
    """Build compliance rows from compliance_status aggregations."""
    comp_buckets = [a for a in aggregations if a.dimension == "compliance_status"]
    if not comp_buckets:
        return []

    # Most recent time_window per dimension_value
    latest: dict[str, AggregationBucket] = {}
    for b in comp_buckets:
        existing = latest.get(b.dimension_value)
        if existing is None or b.time_window > existing.time_window:
            latest[b.dimension_value] = b

    rows = []
    for dim_val in sorted(latest.keys()):
        b = latest[dim_val]
        # For v1, account_id comes from dimension_value (compliance_status string)
        rows.append(
            ComplianceRow(
                account_id=dim_val,
                compliance_status=dim_val,
                total=b.total,
            )
        )
    return rows


def assemble_structured_report(
    run_id: str,
    ml_run_id: str,
    ml_report: AnalysisReport,
    findings: list[Finding],
) -> StructuredReport:
    """Orchestrate all section builders into a single StructuredReport."""
    return StructuredReport(
        run_id=run_id,
        ml_run_id=ml_run_id,
        generated_at=datetime.now(UTC),
        segment_health=build_segment_health(ml_report.aggregations),
        confirmed_issues=build_confirmed_issues(findings),
        trend_summary=build_trend_summary(ml_report.trends),
        data_completeness=build_data_completeness(ml_report.completeness),
        compliance=build_compliance(ml_report.aggregations),
        observations=[],  # Empty in v1 — future LLM enhancement
    )


def assemble_investigation_notes(
    run_id: str,
    hypotheses: list[Hypothesis],
    findings: list[Finding],
    digest_lines: list[str] | None = None,
) -> InvestigationNotes:
    """Assemble Document 2: investigation overflow notes."""
    hyp_strs = [
        f"[{h.topic_title}] {h.statement} — {h.reasoning}" for h in hypotheses
    ]

    # Unexpected observations: disproven findings (unexpected enough to note)
    unexpected = [
        f"[{f.topic_title}] DISPROVEN: {f.statement}"
        for f in findings
        if f.status == FindingStatus.DISPROVEN
    ]

    # Process notes from digest lines
    process = list(digest_lines or [])

    return InvestigationNotes(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        hypotheses=hyp_strs,
        unexpected_observations=unexpected,
        process_notes=process,
    )


def assemble_full_report(
    run_id: str,
    ml_run_id: str,
    ml_report: AnalysisReport,
    findings: list[Finding],
    hypotheses: list[Hypothesis],
    digest_lines: list[str] | None = None,
) -> InvestigationReport:
    """Build the complete InvestigationReport (Document 1 + Document 2)."""
    return InvestigationReport(
        structured=assemble_structured_report(run_id, ml_run_id, ml_report, findings),
        notes=assemble_investigation_notes(run_id, hypotheses, findings, digest_lines),
    )
