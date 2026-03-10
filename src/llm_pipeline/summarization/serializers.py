"""Convert structured ML findings into LLM-digestible text blocks.

Pure functions — no LLM calls, no side effects.
"""

from __future__ import annotations

from collections import Counter

from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnalysisReport,
    AnomalyFinding,
    TrendFinding,
)


def filter_buckets(
    buckets: list[AggregationBucket],
    dimension: str,
    dimension_value: str,
) -> list[AggregationBucket]:
    """Extract buckets matching a specific dimension/value pair."""
    return [
        b for b in buckets
        if b.dimension == dimension and b.dimension_value == dimension_value
    ]


def get_top_dimensions(report: AnalysisReport, top_n: int = 10) -> list[tuple[str, str]]:
    """Identify highest-volume dimension values for dimensional summaries.

    Returns list of (dimension, dimension_value) tuples sorted by total volume.
    """
    volume: Counter[tuple[str, str]] = Counter()
    for b in report.aggregations:
        volume[(b.dimension, b.dimension_value)] += b.total

    return [key for key, _ in volume.most_common(top_n)]


def _fmt_rate(value: float) -> str:
    """Format a rate as a percentage string."""
    return f"{value * 100:.2f}%"


def _fmt_number(value: int) -> str:
    """Format large numbers with commas."""
    return f"{value:,}"


def _bucket_summary_line(b: AggregationBucket) -> str:
    """One-line summary of a bucket."""
    return (
        f"  {b.time_window.strftime('%Y-%m-%d %H:%M')} | "
        f"{b.dimension}={b.dimension_value} | "
        f"total={_fmt_number(b.total)} | "
        f"delivery={_fmt_rate(b.delivery_rate)} | "
        f"bounce={_fmt_rate(b.bounce_rate)} | "
        f"deferral={_fmt_rate(b.deferral_rate)} | "
        f"complaint={_fmt_rate(b.complaint_rate)}"
    )


def serialize_executive_digest(report: AnalysisReport) -> str:
    """Compact digest of the full report for the executive summary prompt."""
    lines: list[str] = []

    # Volume overview
    total_volume = sum(b.total for b in report.aggregations)
    total_delivered = sum(b.delivered for b in report.aggregations)
    total_bounced = sum(b.bounced for b in report.aggregations)
    total_deferred = sum(b.deferred for b in report.aggregations)
    total_complained = sum(b.complained for b in report.aggregations)

    lines.append("=== VOLUME OVERVIEW ===")
    lines.append(f"Total events: {_fmt_number(total_volume)}")
    if total_volume > 0:
        del_rate = _fmt_rate(total_delivered / total_volume)
        bnc_rate = _fmt_rate(total_bounced / total_volume)
        def_rate = _fmt_rate(total_deferred / total_volume)
        cmp_rate = _fmt_rate(total_complained / total_volume)
        lines.append(f"Delivered: {_fmt_number(total_delivered)} ({del_rate})")
        lines.append(f"Bounced: {_fmt_number(total_bounced)} ({bnc_rate})")
        lines.append(f"Deferred: {_fmt_number(total_deferred)} ({def_rate})")
        lines.append(f"Complaints: {_fmt_number(total_complained)} ({cmp_rate})")
    lines.append(f"Aggregation buckets: {len(report.aggregations)}")
    lines.append("")

    # Top dimensions by volume
    top_dims = get_top_dimensions(report, top_n=5)
    if top_dims:
        lines.append("=== TOP DIMENSIONS BY VOLUME ===")
        for dim, dim_val in top_dims:
            dim_buckets = filter_buckets(report.aggregations, dim, dim_val)
            vol = sum(b.total for b in dim_buckets)
            avg_delivery = (
                sum(b.delivery_rate for b in dim_buckets) / len(dim_buckets)
                if dim_buckets else 0
            )
            avg_del = _fmt_rate(avg_delivery)
            lines.append(
                f"  {dim}={dim_val}: {_fmt_number(vol)} events, "
                f"avg delivery={avg_del}"
            )
        lines.append("")

    # Anomalies summary
    if report.anomalies:
        lines.append(f"=== ANOMALIES ({len(report.anomalies)}) ===")
        sorted_anomalies = sorted(
            report.anomalies,
            key=lambda a: abs(a.z_score),
            reverse=True,
        )
        for a in sorted_anomalies[:10]:
            lines.append(
                f"  [{a.severity}] {a.anomaly_type.value}: {a.dimension}={a.dimension_value} "
                f"| {a.metric}: current={_fmt_rate(a.current_value)}, "
                f"baseline={_fmt_rate(a.baseline_mean)}, z-score={a.z_score:.2f}"
            )
        if len(report.anomalies) > 10:
            lines.append(f"  ... and {len(report.anomalies) - 10} more")
        lines.append("")

    # Trends summary
    if report.trends:
        lines.append(f"=== TRENDS ({len(report.trends)}) ===")
        for t in report.trends:
            lines.append(
                f"  {t.direction.value}: {t.dimension}={t.dimension_value} "
                f"| {t.metric}: {_fmt_rate(t.start_value)} -> {_fmt_rate(t.end_value)} "
                f"(slope={t.slope:.4f}, R²={t.r_squared:.3f}, {t.num_points} points)"
            )
        lines.append("")

    return "\n".join(lines)


def serialize_anomaly_context(
    anomaly: AnomalyFinding,
    related_buckets: list[AggregationBucket],
) -> str:
    """Serialize an anomaly with surrounding aggregation context."""
    lines: list[str] = []

    lines.append("=== ANOMALY ===")
    lines.append(f"Type: {anomaly.anomaly_type.value}")
    lines.append(f"Dimension: {anomaly.dimension}={anomaly.dimension_value}")
    lines.append(f"Metric: {anomaly.metric}")
    lines.append(f"Current value: {_fmt_rate(anomaly.current_value)}")
    lines.append(f"Baseline mean: {_fmt_rate(anomaly.baseline_mean)}")
    lines.append(f"Z-score: {anomaly.z_score:.2f}")
    lines.append(f"Severity: {anomaly.severity}")
    lines.append("")

    relevant = filter_buckets(related_buckets, anomaly.dimension, anomaly.dimension_value)
    if relevant:
        lines.append("=== RELATED AGGREGATION DATA ===")
        sorted_buckets = sorted(relevant, key=lambda b: b.time_window)
        for b in sorted_buckets:
            lines.append(_bucket_summary_line(b))
        lines.append("")

    return "\n".join(lines)


def serialize_trend_context(
    trend: TrendFinding,
    related_buckets: list[AggregationBucket],
) -> str:
    """Serialize a trend with time-series context."""
    lines: list[str] = []

    lines.append("=== TREND ===")
    lines.append(f"Direction: {trend.direction.value}")
    lines.append(f"Dimension: {trend.dimension}={trend.dimension_value}")
    lines.append(f"Metric: {trend.metric}")
    lines.append(f"Start value: {_fmt_rate(trend.start_value)}")
    lines.append(f"End value: {_fmt_rate(trend.end_value)}")
    lines.append(f"Slope: {trend.slope:.4f}")
    lines.append(f"R²: {trend.r_squared:.3f}")
    lines.append(f"Data points: {trend.num_points}")
    lines.append("")

    relevant = filter_buckets(related_buckets, trend.dimension, trend.dimension_value)
    if relevant:
        lines.append("=== TIME-SERIES DATA ===")
        sorted_buckets = sorted(relevant, key=lambda b: b.time_window)
        for b in sorted_buckets:
            lines.append(_bucket_summary_line(b))
        lines.append("")

    return "\n".join(lines)


def serialize_dimension_context(
    dimension: str,
    dimension_value: str,
    buckets: list[AggregationBucket],
    anomalies: list[AnomalyFinding],
    trends: list[TrendFinding],
) -> str:
    """Serialize everything known about one dimension slice."""
    lines: list[str] = []

    relevant_buckets = filter_buckets(buckets, dimension, dimension_value)
    relevant_anomalies = [
        a for a in anomalies
        if a.dimension == dimension and a.dimension_value == dimension_value
    ]
    relevant_trends = [
        t for t in trends
        if t.dimension == dimension and t.dimension_value == dimension_value
    ]

    # Volume summary
    total = sum(b.total for b in relevant_buckets)
    lines.append(f"=== DIMENSION: {dimension}={dimension_value} ===")
    lines.append(f"Total volume: {_fmt_number(total)}")
    lines.append(f"Aggregation windows: {len(relevant_buckets)}")
    lines.append("")

    # Time-series data
    if relevant_buckets:
        lines.append("=== AGGREGATION DATA ===")
        sorted_buckets = sorted(relevant_buckets, key=lambda b: b.time_window)
        for b in sorted_buckets:
            lines.append(_bucket_summary_line(b))
        lines.append("")

    # Anomalies for this dimension
    if relevant_anomalies:
        lines.append(f"=== ANOMALIES ({len(relevant_anomalies)}) ===")
        for a in relevant_anomalies:
            lines.append(
                f"  [{a.severity}] {a.anomaly_type.value}: {a.metric} "
                f"current={_fmt_rate(a.current_value)}, "
                f"baseline={_fmt_rate(a.baseline_mean)}, z={a.z_score:.2f}"
            )
        lines.append("")

    # Trends for this dimension
    if relevant_trends:
        lines.append(f"=== TRENDS ({len(relevant_trends)}) ===")
        for t in relevant_trends:
            lines.append(
                f"  {t.direction.value}: {t.metric} "
                f"{_fmt_rate(t.start_value)} -> {_fmt_rate(t.end_value)} "
                f"(slope={t.slope:.4f}, R²={t.r_squared:.3f})"
            )
        lines.append("")

    return "\n".join(lines)
