"""Polars-based dimensional aggregation for HTTP access log events.

Minute-level time windows (HTTP has much higher event density than email).
Streaming: process chunks independently, merge overlapping buckets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from llm_pipeline.http_analytics.models import (
    HttpAccessEvent,
    HttpAggregationBucket,
    HttpDataCompleteness,
)

DEFAULT_DIMENSIONS = [
    "http_host",
    "host_category",
    "status_code_str",
    "status_class",
    "request_category",
    "http_method",
    "upstream",
    "ua_category",
]

# Fields tracked for data completeness (empty = missing)
_COMPLETENESS_FIELDS = [
    "useragent",
    "upstream",
    "http_referrer",
    "accountid",
]


def events_to_dataframe(events: list[HttpAccessEvent]) -> pl.DataFrame:
    """Convert HttpAccessEvent list into a Polars DataFrame."""
    if not events:
        return pl.DataFrame(
            schema={
                "event_time": pl.Datetime("us", "UTC"),
                "http_host": pl.Utf8,
                "host_category": pl.Utf8,
                "status_code": pl.Int64,
                "status_code_str": pl.Utf8,
                "status_class": pl.Utf8,
                "request_category": pl.Utf8,
                "http_method": pl.Utf8,
                "upstream": pl.Utf8,
                "ua_category": pl.Utf8,
                "tts_seconds": pl.Float64,
                "size_bytes": pl.Int64,
                "useragent": pl.Utf8,
                "http_referrer": pl.Utf8,
                "accountid": pl.Utf8,
            }
        )

    records = []
    for e in events:
        records.append(
            {
                "event_time": e.event_time,
                "http_host": e.http_host,
                "host_category": e.host_category.value,
                "status_code": e.status_code,
                "status_code_str": str(e.status_code),
                "status_class": e.status_class.value,
                "request_category": e.request_category.value,
                "http_method": e.http_method,
                "upstream": e.upstream,
                "ua_category": e.ua_category.value,
                "tts_seconds": e.tts_seconds,
                "size_bytes": e.size_bytes,
                "useragent": e.useragent,
                "http_referrer": e.http_referrer,
                "accountid": e.accountid,
            }
        )

    return pl.DataFrame(records)


def _truncate_to_window(dt_col: pl.Expr, window_minutes: int) -> pl.Expr:
    """Truncate a datetime column to the specified minute window."""
    return dt_col.dt.truncate(f"{window_minutes}m")


def aggregate(
    df: pl.DataFrame,
    window_minutes: int | None = None,
    dimensions: list[str] | None = None,
) -> list[HttpAggregationBucket]:
    """Group by time window + dimension and compute HTTP status rates and latency.

    Returns a flat list of HttpAggregationBucket across all dimensions.
    """
    if df.is_empty():
        return []

    from llm_pipeline.config import settings

    window_minutes = window_minutes or getattr(settings, "http_time_window_minutes", 1)
    dimensions = dimensions or DEFAULT_DIMENSIONS

    # Add time window column
    df = df.with_columns(
        _truncate_to_window(pl.col("event_time"), window_minutes).alias("time_window")
    )

    buckets: list[HttpAggregationBucket] = []

    # Status count expressions
    status_aggs = [
        pl.len().alias("total"),
        (pl.col("status_class") == "2xx").sum().alias("status_2xx"),
        (pl.col("status_class") == "3xx").sum().alias("status_3xx"),
        (pl.col("status_class") == "4xx").sum().alias("status_4xx"),
        (pl.col("status_class") == "5xx").sum().alias("status_5xx"),
        (pl.col("status_class") == "679").sum().alias("status_679"),
        (
            ~pl.col("status_class").is_in(["2xx", "3xx", "4xx", "5xx", "679"])
        )
        .sum()
        .alias("status_other"),
    ]

    # TTS latency aggregations
    tts_aggs = [
        pl.col("tts_seconds").median().alias("tts_p50"),
        pl.col("tts_seconds").quantile(0.90).alias("tts_p90"),
        pl.col("tts_seconds").quantile(0.95).alias("tts_p95"),
        pl.col("tts_seconds").quantile(0.99).alias("tts_p99"),
        pl.col("tts_seconds").max().alias("tts_max"),
        pl.col("tts_seconds").mean().alias("tts_mean"),
    ]

    # Size aggregations
    size_aggs = [
        pl.col("size_bytes").sum().alias("total_bytes"),
        pl.col("size_bytes").mean().alias("mean_bytes"),
    ]

    # Completeness counts
    completeness_aggs = [
        (pl.col("useragent") == "").sum().alias("empty_ua_count"),
        (pl.col("upstream") == "").sum().alias("empty_upstream_count"),
        (pl.col("http_referrer") == "").sum().alias("empty_referrer_count"),
    ]

    all_aggs = status_aggs + tts_aggs + size_aggs + completeness_aggs

    for dim in dimensions:
        if dim not in df.columns:
            continue

        grouped = (
            df.group_by(["time_window", dim])
            .agg(all_aggs)
            .sort(["time_window", dim])
        )

        for row in grouped.iter_rows(named=True):
            total = row["total"]
            s2 = row["status_2xx"]
            s4 = row["status_4xx"]
            s5 = row["status_5xx"]
            s679 = row["status_679"]

            buckets.append(
                HttpAggregationBucket(
                    time_window=row["time_window"],
                    dimension=dim,
                    dimension_value=str(row[dim]),
                    total=total,
                    status_2xx=s2,
                    status_3xx=row["status_3xx"],
                    status_4xx=s4,
                    status_5xx=s5,
                    status_679=s679,
                    status_other=row["status_other"],
                    success_rate=s2 / total if total > 0 else 0.0,
                    client_error_rate=s4 / total if total > 0 else 0.0,
                    server_error_rate=s5 / total if total > 0 else 0.0,
                    known_content_error_rate=s679 / total if total > 0 else 0.0,
                    tts_p50=row["tts_p50"],
                    tts_p90=row["tts_p90"],
                    tts_p95=row["tts_p95"],
                    tts_p99=row["tts_p99"],
                    tts_max=row["tts_max"],
                    tts_mean=row["tts_mean"],
                    total_bytes=int(row["total_bytes"] or 0),
                    mean_bytes=float(row["mean_bytes"] or 0.0),
                    empty_ua_count=row["empty_ua_count"],
                    empty_upstream_count=row["empty_upstream_count"],
                    empty_referrer_count=row["empty_referrer_count"],
                )
            )

    return buckets


def compute_data_completeness(
    df: pl.DataFrame,
    window_minutes: int | None = None,
    dimensions: list[str] | None = None,
) -> list[HttpDataCompleteness]:
    """Compute empty-value rates for key fields, grouped by time_window + dimension."""
    if df.is_empty():
        return []

    from llm_pipeline.config import settings

    window_minutes = window_minutes or getattr(settings, "http_time_window_minutes", 1)
    dimensions = dimensions or ["http_host", "request_category"]

    df = df.with_columns(
        _truncate_to_window(pl.col("event_time"), window_minutes).alias("time_window")
    )

    results: list[HttpDataCompleteness] = []

    for dim in dimensions:
        if dim not in df.columns:
            continue

        for field_name in _COMPLETENESS_FIELDS:
            if field_name not in df.columns:
                continue

            empty_expr = (pl.col(field_name) == "").sum().alias("empty_count")

            grouped = (
                df.group_by(["time_window", dim])
                .agg(pl.len().alias("total_records"), empty_expr)
                .sort(["time_window", dim])
            )

            for row in grouped.iter_rows(named=True):
                total = row["total_records"]
                empty_count = row["empty_count"]
                results.append(
                    HttpDataCompleteness(
                        time_window=row["time_window"],
                        dimension=dim,
                        dimension_value=str(row[dim]),
                        total_records=total,
                        field_name=field_name,
                        empty_count=empty_count,
                        empty_rate=empty_count / total if total > 0 else 0.0,
                    )
                )

    return results


def merge_bucket_list(
    buckets: list[HttpAggregationBucket],
) -> list[HttpAggregationBucket]:
    """Deduplicate and merge buckets that share the same key.

    Key is ``(time_window, dimension, dimension_value)``. Counts are summed,
    rates recomputed. TTS uses weighted mean for _mean; percentiles dropped
    on merge (imprecise with pre-aggregated data).
    """
    if not buckets:
        return []

    acc: dict[tuple, dict] = {}
    for b in buckets:
        key = (b.time_window, b.dimension, b.dimension_value)
        if key in acc:
            rec = acc[key]
            rec["total"] += b.total
            rec["status_2xx"] += b.status_2xx
            rec["status_3xx"] += b.status_3xx
            rec["status_4xx"] += b.status_4xx
            rec["status_5xx"] += b.status_5xx
            rec["status_679"] += b.status_679
            rec["status_other"] += b.status_other
            rec["total_bytes"] += b.total_bytes
            rec["empty_ua_count"] += b.empty_ua_count
            rec["empty_upstream_count"] += b.empty_upstream_count
            rec["empty_referrer_count"] += b.empty_referrer_count
            # Weighted mean for TTS
            if b.tts_mean is not None:
                rec["tts_mean_sum"] += b.tts_mean * b.total
                rec["tts_mean_count"] += b.total
        else:
            acc[key] = {
                "total": b.total,
                "status_2xx": b.status_2xx,
                "status_3xx": b.status_3xx,
                "status_4xx": b.status_4xx,
                "status_5xx": b.status_5xx,
                "status_679": b.status_679,
                "status_other": b.status_other,
                "total_bytes": b.total_bytes,
                "empty_ua_count": b.empty_ua_count,
                "empty_upstream_count": b.empty_upstream_count,
                "empty_referrer_count": b.empty_referrer_count,
                "tts_mean_sum": (b.tts_mean or 0.0) * b.total,
                "tts_mean_count": b.total if b.tts_mean is not None else 0,
            }

    merged: list[HttpAggregationBucket] = []
    for (tw, dim, dv), rec in acc.items():
        total = rec["total"]
        s2 = rec["status_2xx"]
        s4 = rec["status_4xx"]
        s5 = rec["status_5xx"]
        s679 = rec["status_679"]
        tts_cnt = rec["tts_mean_count"]

        merged.append(
            HttpAggregationBucket(
                time_window=tw,
                dimension=dim,
                dimension_value=dv,
                total=total,
                status_2xx=s2,
                status_3xx=rec["status_3xx"],
                status_4xx=s4,
                status_5xx=s5,
                status_679=s679,
                status_other=rec["status_other"],
                success_rate=s2 / total if total > 0 else 0.0,
                client_error_rate=s4 / total if total > 0 else 0.0,
                server_error_rate=s5 / total if total > 0 else 0.0,
                known_content_error_rate=s679 / total if total > 0 else 0.0,
                tts_mean=rec["tts_mean_sum"] / tts_cnt if tts_cnt > 0 else None,
                total_bytes=rec["total_bytes"],
                mean_bytes=rec["total_bytes"] / total if total > 0 else 0.0,
                empty_ua_count=rec["empty_ua_count"],
                empty_upstream_count=rec["empty_upstream_count"],
                empty_referrer_count=rec["empty_referrer_count"],
            )
        )
    return merged


def merge_completeness(
    items: list[HttpDataCompleteness],
) -> list[HttpDataCompleteness]:
    """Merge completeness records with the same key by summing counts."""
    if not items:
        return []

    acc: dict[tuple, dict] = {}
    for c in items:
        key = (c.time_window, c.dimension, c.dimension_value, c.field_name)
        if key in acc:
            rec = acc[key]
            rec["total_records"] += c.total_records
            rec["empty_count"] += c.empty_count
        else:
            acc[key] = {
                "total_records": c.total_records,
                "empty_count": c.empty_count,
            }

    merged: list[HttpDataCompleteness] = []
    for (tw, dim, dv, fn), rec in acc.items():
        total = rec["total_records"]
        merged.append(
            HttpDataCompleteness(
                time_window=tw,
                dimension=dim,
                dimension_value=dv,
                total_records=total,
                field_name=fn,
                empty_count=rec["empty_count"],
                empty_rate=rec["empty_count"] / total if total > 0 else 0.0,
            )
        )
    return merged


@dataclass
class FileAggregationResult:
    """Return type for aggregate_file — buckets + completeness + count."""

    buckets: list[HttpAggregationBucket] = field(default_factory=list)
    completeness: list[HttpDataCompleteness] = field(default_factory=list)
    event_count: int = 0


def aggregate_file(
    path: str | Path,
    chunk_size: int | None = None,
    window_minutes: int | None = None,
    dimensions: list[str] | None = None,
) -> FileAggregationResult:
    """Stream a file and produce merged aggregation buckets + completeness.

    Reads the file in chunks, aggregates each chunk independently, and
    merges overlapping buckets. Peak memory bounded to one chunk.
    """
    from llm_pipeline.http_analytics.loader import iter_http_event_chunks

    all_buckets: list[HttpAggregationBucket] = []
    all_completeness: list[HttpDataCompleteness] = []
    total_events = 0

    for events_chunk in iter_http_event_chunks(path, chunk_size=chunk_size):
        total_events += len(events_chunk)
        df = events_to_dataframe(events_chunk)
        chunk_buckets = aggregate(
            df, window_minutes=window_minutes, dimensions=dimensions
        )
        all_buckets.extend(chunk_buckets)
        chunk_completeness = compute_data_completeness(
            df, window_minutes=window_minutes
        )
        all_completeness.extend(chunk_completeness)

    merged_buckets = merge_bucket_list(all_buckets)
    merged_completeness = merge_completeness(all_completeness)
    return FileAggregationResult(
        buckets=merged_buckets,
        completeness=merged_completeness,
        event_count=total_events,
    )
