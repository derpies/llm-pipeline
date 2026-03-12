"""Deterministic report assembly for HTTP analytics — pure functions, no LLM calls.

Each function builds one section of the structured report from ML data
and investigation findings.
"""

from __future__ import annotations

from datetime import UTC, datetime

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.domains.http_analytics.report_models import (
    BotTrafficSummary,
    CategoryBreakdownRow,
    CompletenessRow,
    ConfirmedIssue,
    HostHealthRow,
    HttpInvestigationNotes,
    HttpInvestigationReport,
    HttpStructuredReport,
    Status679Summary,
    TrendRow,
    TrendSummary,
)
from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpAnalysisReport,
    HttpDataCompleteness,
    HttpTrendFinding,
)


def build_host_health(
    aggregations: list[HttpAggregationBucket],
) -> list[HostHealthRow]:
    """Build host health rows from host_category aggregations.

    Uses the most recent time_window per host category.
    """
    host_buckets = [a for a in aggregations if a.dimension == "host_category"]
    if not host_buckets:
        return []

    latest: dict[str, HttpAggregationBucket] = {}
    for b in host_buckets:
        existing = latest.get(b.dimension_value)
        if existing is None or b.time_window > existing.time_window:
            latest[b.dimension_value] = b

    rows = []
    for hc in sorted(latest.keys()):
        b = latest[hc]
        rows.append(
            HostHealthRow(
                host_category=hc,
                total=b.total,
                success_rate=b.success_rate,
                client_error_rate=b.client_error_rate,
                server_error_rate=b.server_error_rate,
                known_content_error_rate=b.known_content_error_rate,
                tts_mean=b.tts_mean,
                tts_p50=b.tts_p50,
                tts_p95=b.tts_p95,
                tts_p99=b.tts_p99,
                tts_max=b.tts_max,
            )
        )
    return rows


def build_category_breakdown(
    aggregations: list[HttpAggregationBucket],
) -> list[CategoryBreakdownRow]:
    """Build request category traffic distribution."""
    cat_buckets = [a for a in aggregations if a.dimension == "request_category"]
    if not cat_buckets:
        return []

    # Sum across time windows per category
    totals: dict[str, dict] = {}
    for b in cat_buckets:
        cat = b.dimension_value
        if cat not in totals:
            totals[cat] = {
                "total": 0,
                "status_2xx": 0,
                "status_4xx": 0,
            }
        totals[cat]["total"] += b.total
        totals[cat]["status_2xx"] += b.status_2xx
        totals[cat]["status_4xx"] += b.status_4xx

    grand_total = sum(t["total"] for t in totals.values())

    rows = []
    for cat in sorted(totals.keys(), key=lambda c: totals[c]["total"], reverse=True):
        t = totals[cat]
        total = t["total"]
        rows.append(
            CategoryBreakdownRow(
                category=cat,
                total=total,
                percentage=total / grand_total if grand_total > 0 else 0.0,
                success_rate=t["status_2xx"] / total if total > 0 else 0.0,
                client_error_rate=t["status_4xx"] / total if total > 0 else 0.0,
            )
        )
    return rows


def build_status_679_summary(
    aggregations: list[HttpAggregationBucket],
) -> Status679Summary:
    """Summarize 679 (known-content-missing) errors."""
    total_679 = 0
    total_all = 0
    affected_hosts: set[str] = set()

    for b in aggregations:
        if b.dimension == "http_host":
            total_all += b.total
            if b.status_679 > 0:
                total_679 += b.status_679
                affected_hosts.add(b.dimension_value)

    return Status679Summary(
        total_679=total_679,
        affected_hosts=sorted(affected_hosts),
        rate_overall=total_679 / total_all if total_all > 0 else 0.0,
    )


def build_bot_traffic_summary(
    aggregations: list[HttpAggregationBucket],
) -> BotTrafficSummary:
    """Summarize bot and scanner traffic from ua_category aggregations."""
    ua_buckets = [a for a in aggregations if a.dimension == "ua_category"]
    if not ua_buckets:
        return BotTrafficSummary()

    # Sum across time windows per ua_category
    totals: dict[str, int] = {}
    total_empty_ua = 0
    total_all = 0
    for b in ua_buckets:
        totals[b.dimension_value] = totals.get(b.dimension_value, 0) + b.total
        total_all += b.total
        total_empty_ua += b.empty_ua_count

    # Also count from request_category for PHP probes
    php_buckets = [
        a for a in aggregations
        if a.dimension == "request_category" and a.dimension_value == "php_probe"
    ]
    php_total = sum(b.total for b in php_buckets)

    return BotTrafficSummary(
        empty_ua_rate=total_empty_ua / total_all if total_all > 0 else 0.0,
        scanner_count=totals.get("scanner", 0),
        bot_crawler_count=totals.get("bot_crawler", 0),
        php_probe_count=php_total,
        real_browser_count=totals.get("real_browser", 0),
    )


def build_confirmed_issues(findings: list[Finding]) -> list[ConfirmedIssue]:
    """Extract confirmed findings into structured issues."""
    issues = []
    for f in findings:
        if f.status != FindingStatus.CONFIRMED:
            continue

        metric = ""
        if f.metrics_cited:
            metric = next(iter(f.metrics_cited.keys()), "")

        if f.metrics_cited:
            parts = [f"{k}={v}" for k, v in f.metrics_cited.items()]
            magnitude = ", ".join(parts)
        else:
            magnitude = "see evidence"

        evidence_summary = "; ".join(f.evidence[:3]) if f.evidence else f.statement

        issues.append(
            ConfirmedIssue(
                dimension="",
                dimension_value="",
                metric=metric,
                magnitude=magnitude,
                evidence_summary=evidence_summary,
            )
        )
    return issues


def build_trend_summary(
    trends: list[HttpTrendFinding],
    top_n: int = 5,
) -> TrendSummary:
    """Count trends by direction and extract top movers."""
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

    trend_rows.sort(key=lambda r: abs(r.slope), reverse=True)

    return TrendSummary(
        degrading_count=degrading,
        improving_count=improving,
        stable_count=stable,
        top_movers=trend_rows[:top_n],
    )


def build_data_completeness(
    completeness: list[HttpDataCompleteness],
    threshold: float = 0.10,
) -> list[CompletenessRow]:
    """Map completeness records to rows, flagging high empty-rates."""
    rows = []
    for c in completeness:
        rows.append(
            CompletenessRow(
                field_name=c.field_name,
                dimension=c.dimension,
                dimension_value=c.dimension_value,
                empty_rate=c.empty_rate,
                total_records=c.total_records,
                flagged=c.empty_rate >= threshold,
            )
        )
    return rows


def assemble_structured_report(
    run_id: str,
    ml_run_id: str,
    ml_report: HttpAnalysisReport,
    findings: list[Finding],
) -> HttpStructuredReport:
    """Orchestrate all section builders into a single HttpStructuredReport."""
    return HttpStructuredReport(
        run_id=run_id,
        ml_run_id=ml_run_id,
        generated_at=datetime.now(UTC),
        host_health=build_host_health(ml_report.aggregations),
        category_breakdown=build_category_breakdown(ml_report.aggregations),
        status_679=build_status_679_summary(ml_report.aggregations),
        bot_traffic=build_bot_traffic_summary(ml_report.aggregations),
        confirmed_issues=build_confirmed_issues(findings),
        trend_summary=build_trend_summary(ml_report.trends),
        data_completeness=build_data_completeness(ml_report.completeness),
        observations=[],
    )


def assemble_investigation_notes(
    run_id: str,
    hypotheses: list[Hypothesis],
    findings: list[Finding],
    digest_lines: list[str] | None = None,
) -> HttpInvestigationNotes:
    """Assemble Document 2: investigation overflow notes."""
    hyp_strs = [
        f"[{h.topic_title}] {h.statement} — {h.reasoning}" for h in hypotheses
    ]

    unexpected = [
        f"[{f.topic_title}] DISPROVEN: {f.statement}"
        for f in findings
        if f.status == FindingStatus.DISPROVEN
    ]

    process = list(digest_lines or [])

    return HttpInvestigationNotes(
        run_id=run_id,
        generated_at=datetime.now(UTC),
        hypotheses=hyp_strs,
        unexpected_observations=unexpected,
        process_notes=process,
    )


def assemble_full_report(
    run_id: str,
    ml_run_id: str,
    ml_report: HttpAnalysisReport,
    findings: list[Finding],
    hypotheses: list[Hypothesis],
    digest_lines: list[str] | None = None,
) -> HttpInvestigationReport:
    """Build the complete HttpInvestigationReport (Document 1 + Document 2)."""
    return HttpInvestigationReport(
        structured=assemble_structured_report(run_id, ml_run_id, ml_report, findings),
        notes=assemble_investigation_notes(run_id, hypotheses, findings, digest_lines),
    )
