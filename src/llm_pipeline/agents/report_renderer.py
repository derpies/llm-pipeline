"""Render InvestigationReport to JSON and markdown.

Markdown is a pure function of the JSON model — re-render anytime.
"""

from __future__ import annotations

from llm_pipeline.agents.report_models import InvestigationReport


def render_json(report: InvestigationReport) -> str:
    """Render the full report as JSON (canonical format)."""
    return report.model_dump_json(indent=2)


def render_markdown(report: InvestigationReport) -> str:
    """Render the full report as deterministic markdown."""
    lines: list[str] = []
    sr = report.structured
    notes = report.notes

    # Header
    lines.append(f"# Structured Investigation Report — {sr.run_id}")
    lines.append("")
    lines.append(f"**ML Run:** {sr.ml_run_id}")
    lines.append(f"**Generated:** {sr.generated_at:%Y-%m-%d %H:%M:%S UTC}")
    lines.append("")

    # Segment Health
    lines.append("## Segment Health")
    lines.append("")
    if sr.segment_health:
        lines.append(
            "| Segment | Total | Delivery | Bounce | Deferral | Complaint "
            "| DT Mean | DT p50 | DT p95 | DT p99 | DT Max "
            "| PE Mean | PE p50 | PE p95 | PE p99 | PE Max |"
        )
        lines.append(
            "|---------|------:|--------:|-------:|---------:|----------:"
            "|--------:|-------:|-------:|-------:|-------:"
            "|--------:|-------:|-------:|-------:|-------:|"
        )
        for r in sr.segment_health:
            def _fmt(v: float | None) -> str:
                return f"{v:.2f}" if v is not None else "-"

            lines.append(
                f"| {r.segment} | {r.total} "
                f"| {r.delivery_rate:.2%} | {r.bounce_rate:.2%} "
                f"| {r.deferral_rate:.2%} | {r.complaint_rate:.2%} "
                f"| {_fmt(r.delivery_time_mean)} | {_fmt(r.delivery_time_p50)} "
                f"| {_fmt(r.delivery_time_p95)} | {_fmt(r.delivery_time_p99)} "
                f"| {_fmt(r.delivery_time_max)} "
                f"| {_fmt(r.pre_edge_latency_mean)} | {_fmt(r.pre_edge_latency_p50)} "
                f"| {_fmt(r.pre_edge_latency_p95)} | {_fmt(r.pre_edge_latency_p99)} "
                f"| {_fmt(r.pre_edge_latency_max)} |"
            )
    else:
        lines.append("No segment health data available.")
    lines.append("")

    # Confirmed Issues
    lines.append("## Confirmed Issues")
    lines.append("")
    if sr.confirmed_issues:
        for i, issue in enumerate(sr.confirmed_issues, 1):
            lines.append(f"**{i}.** {issue.evidence_summary}")
            parts = []
            if issue.dimension:
                parts.append(f"dimension={issue.dimension}")
            if issue.dimension_value:
                parts.append(f"value={issue.dimension_value}")
            if issue.metric:
                parts.append(f"metric={issue.metric}")
            parts.append(f"magnitude={issue.magnitude}")
            lines.append(f"   {', '.join(parts)}")
            lines.append("")
    else:
        lines.append("No confirmed issues.")
    lines.append("")

    # Trend Summary
    lines.append("## Trend Summary")
    lines.append("")
    ts = sr.trend_summary
    lines.append(
        f"Degrading: {ts.degrading_count} | "
        f"Improving: {ts.improving_count} | "
        f"Stable: {ts.stable_count}"
    )
    lines.append("")
    if ts.top_movers:
        lines.append("**Top movers (by absolute slope):**")
        lines.append("")
        lines.append(
            "| Dimension | Value | Metric | Direction | Slope | Start | End |"
        )
        lines.append(
            "|-----------|-------|--------|-----------|------:|------:|----:|"
        )
        for t in ts.top_movers:
            lines.append(
                f"| {t.dimension} | {t.dimension_value} | {t.metric} "
                f"| {t.direction} | {t.slope:.6f} "
                f"| {t.start_value:.4f} | {t.end_value:.4f} |"
            )
    lines.append("")

    # Data Completeness
    lines.append("## Data Completeness")
    lines.append("")
    if sr.data_completeness:
        flagged = [c for c in sr.data_completeness if c.flagged]
        lines.append(
            f"{len(sr.data_completeness)} fields tracked, "
            f"{len(flagged)} flagged (>= 10% zero-rate)"
        )
        lines.append("")
        if flagged:
            lines.append(
                "| Field | Dimension | Value | Zero Rate | Records | Flagged |"
            )
            lines.append(
                "|-------|-----------|-------|----------:|--------:|:-------:|"
            )
            for c in flagged:
                lines.append(
                    f"| {c.field_name} | {c.dimension} | {c.dimension_value} "
                    f"| {c.zero_rate:.2%} | {c.total_records} | YES |"
                )
    else:
        lines.append("No data completeness records.")
    lines.append("")

    # Compliance
    lines.append("## Compliance")
    lines.append("")
    if sr.compliance:
        lines.append("| Account/Status | Compliance | Total |")
        lines.append("|----------------|------------|------:|")
        for c in sr.compliance:
            lines.append(
                f"| {c.account_id} | {c.compliance_status} | {c.total} |"
            )
    else:
        lines.append("No compliance data.")
    lines.append("")

    # Observations (empty in v1)
    if sr.observations:
        lines.append("## Observations")
        lines.append("")
        for obs in sr.observations:
            lines.append(f"- **{obs.section}**: {obs.note}")
        lines.append("")

    # Document 2: Investigation Notes
    lines.append("---")
    lines.append("")
    lines.append("# Investigation Notes")
    lines.append("")

    if notes.hypotheses:
        lines.append("## Untested Hypotheses")
        lines.append("")
        for h in notes.hypotheses:
            lines.append(f"- {h}")
        lines.append("")

    if notes.unexpected_observations:
        lines.append("## Unexpected Observations")
        lines.append("")
        for o in notes.unexpected_observations:
            lines.append(f"- {o}")
        lines.append("")

    if notes.process_notes:
        lines.append("## Process Notes")
        lines.append("")
        for p in notes.process_notes:
            lines.append(f"- {p}")
        lines.append("")

    if not notes.hypotheses and not notes.unexpected_observations and not notes.process_notes:
        lines.append("No investigation notes.")
        lines.append("")

    return "\n".join(lines)
