"""Render HttpInvestigationReport to JSON and markdown."""

from __future__ import annotations

from llm_pipeline.domains.http_analytics.report_models import HttpInvestigationReport


def render_json(report: HttpInvestigationReport) -> str:
    """Render the full report as JSON (canonical format)."""
    return report.model_dump_json(indent=2)


def render_markdown(report: HttpInvestigationReport) -> str:
    """Render the full report as deterministic markdown."""
    lines: list[str] = []
    sr = report.structured
    notes = report.notes

    def _fmt(v: float | None) -> str:
        return f"{v:.3f}" if v is not None else "-"

    # Header
    lines.append(f"# HTTP Investigation Report — {sr.run_id}")
    lines.append("")
    lines.append(f"**ML Run:** {sr.ml_run_id}")
    lines.append(f"**Generated:** {sr.generated_at:%Y-%m-%d %H:%M:%S UTC}")
    lines.append("")

    # Host Health
    lines.append("## Host Health")
    lines.append("")
    if sr.host_health:
        lines.append(
            "| Host Category | Total | Success | 4xx | 5xx | 679 "
            "| TTS Mean | TTS p50 | TTS p95 | TTS p99 | TTS Max |"
        )
        lines.append(
            "|---------------|------:|--------:|----:|----:|----:"
            "|---------:|--------:|--------:|--------:|--------:|"
        )
        for r in sr.host_health:
            lines.append(
                f"| {r.host_category} | {r.total} "
                f"| {r.success_rate:.2%} | {r.client_error_rate:.2%} "
                f"| {r.server_error_rate:.2%} | {r.known_content_error_rate:.2%} "
                f"| {_fmt(r.tts_mean)} | {_fmt(r.tts_p50)} "
                f"| {_fmt(r.tts_p95)} | {_fmt(r.tts_p99)} "
                f"| {_fmt(r.tts_max)} |"
            )
    else:
        lines.append("No host health data available.")
    lines.append("")

    # Category Breakdown
    lines.append("## Request Category Breakdown")
    lines.append("")
    if sr.category_breakdown:
        lines.append("| Category | Total | % Traffic | Success | 4xx |")
        lines.append("|----------|------:|----------:|--------:|----:|")
        for r in sr.category_breakdown:
            lines.append(
                f"| {r.category} | {r.total} | {r.percentage:.1%} "
                f"| {r.success_rate:.2%} | {r.client_error_rate:.2%} |"
            )
    else:
        lines.append("No category breakdown data.")
    lines.append("")

    # Status 679 Summary
    lines.append("## Status 679 (Known-Content-Missing)")
    lines.append("")
    s679 = sr.status_679
    if s679.total_679 > 0:
        lines.append(f"- **Total 679 errors:** {s679.total_679}")
        lines.append(f"- **Overall rate:** {s679.rate_overall:.4%}")
        lines.append(f"- **Affected hosts:** {len(s679.affected_hosts)}")
        if s679.affected_hosts[:10]:
            for h in s679.affected_hosts[:10]:
                lines.append(f"  - {h}")
    else:
        lines.append("No 679 errors detected.")
    lines.append("")

    # Bot Traffic
    lines.append("## Bot & Scanner Traffic")
    lines.append("")
    bt = sr.bot_traffic
    lines.append(f"- Empty user-agent rate: {bt.empty_ua_rate:.1%}")
    lines.append(f"- PHP probes: {bt.php_probe_count:,}")
    lines.append(f"- Scanners: {bt.scanner_count:,}")
    lines.append(f"- Bot crawlers: {bt.bot_crawler_count:,}")
    lines.append(f"- Real browsers: {bt.real_browser_count:,}")
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
            f"{len(flagged)} flagged (>= 10% empty-rate)"
        )
        lines.append("")
        if flagged:
            lines.append(
                "| Field | Dimension | Value | Empty Rate | Records | Flagged |"
            )
            lines.append(
                "|-------|-----------|-------|----------:|--------:|:-------:|"
            )
            for c in flagged:
                lines.append(
                    f"| {c.field_name} | {c.dimension} | {c.dimension_value} "
                    f"| {c.empty_rate:.2%} | {c.total_records} | YES |"
                )
    else:
        lines.append("No data completeness records.")
    lines.append("")

    # Observations
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
