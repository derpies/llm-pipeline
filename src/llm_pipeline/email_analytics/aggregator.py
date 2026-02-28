"""Polars-based dimensional aggregation for email delivery events."""

from __future__ import annotations

from pathlib import Path

import polars as pl

from llm_pipeline.config import settings
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    DeliveryEvent,
    DeliveryStatus,
    SmtpClassification,
)

DEFAULT_DIMENSIONS = ["recipient_domain", "outmtaid_ip", "sendid", "provider_hint"]


def events_to_dataframe(
    events: list[DeliveryEvent],
    classifications: list[SmtpClassification],
) -> pl.DataFrame:
    """Convert events and their SMTP classifications into a Polars DataFrame."""
    if not events:
        return pl.DataFrame(
            schema={
                "timestamp": pl.Datetime,
                "normalized_status": pl.Utf8,
                "recipient_domain": pl.Utf8,
                "outmtaid_ip": pl.Utf8,
                "sendid": pl.Utf8,
                "provider_hint": pl.Utf8,
            }
        )

    records = []
    for i, event in enumerate(events):
        clf = classifications[i] if i < len(classifications) else None
        records.append(
            {
                "timestamp": event.event_time,
                "normalized_status": event.normalized_status.value,
                "recipient_domain": event.recipient_domain,
                "outmtaid_ip": event.outmtaid_ip,
                "sendid": event.sendid,
                "provider_hint": clf.provider_hint if clf else "",
            }
        )

    return pl.DataFrame(records)


def _truncate_to_window(dt_col: pl.Expr, window_hours: int) -> pl.Expr:
    """Truncate a datetime column to the specified hour window."""
    return dt_col.dt.truncate(f"{window_hours}h")


def aggregate(
    df: pl.DataFrame,
    window_hours: int | None = None,
    dimensions: list[str] | None = None,
) -> list[AggregationBucket]:
    """Group by time window + dimension and compute delivery rates.

    Returns a flat list of AggregationBucket across all dimensions.
    """
    if df.is_empty():
        return []

    window_hours = window_hours or settings.email_time_window_hours
    dimensions = dimensions or DEFAULT_DIMENSIONS

    # Add time window column
    df = df.with_columns(
        _truncate_to_window(pl.col("timestamp"), window_hours).alias("time_window")
    )

    buckets: list[AggregationBucket] = []

    for dim in dimensions:
        if dim not in df.columns:
            continue

        grouped = (
            df.group_by(["time_window", dim])
            .agg(
                pl.len().alias("total"),
                (pl.col("normalized_status") == DeliveryStatus.DELIVERED.value)
                .sum()
                .alias("delivered"),
                (pl.col("normalized_status") == DeliveryStatus.BOUNCED.value)
                .sum()
                .alias("bounced"),
                (pl.col("normalized_status") == DeliveryStatus.DEFERRED.value)
                .sum()
                .alias("deferred"),
                (pl.col("normalized_status") == DeliveryStatus.COMPLAINT.value)
                .sum()
                .alias("complained"),
            )
            .sort(["time_window", dim])
        )

        for row in grouped.iter_rows(named=True):
            total = row["total"]
            buckets.append(
                AggregationBucket(
                    time_window=row["time_window"],
                    dimension=dim,
                    dimension_value=row[dim],
                    total=total,
                    delivered=row["delivered"],
                    bounced=row["bounced"],
                    deferred=row["deferred"],
                    complained=row["complained"],
                    delivery_rate=row["delivered"] / total if total > 0 else 0.0,
                    bounce_rate=row["bounced"] / total if total > 0 else 0.0,
                    deferral_rate=row["deferred"] / total if total > 0 else 0.0,
                    complaint_rate=row["complained"] / total if total > 0 else 0.0,
                )
            )

    return buckets


def merge_bucket_list(buckets: list[AggregationBucket]) -> list[AggregationBucket]:
    """Deduplicate and merge buckets that share the same key.

    Key is ``(time_window, dimension, dimension_value)``.  For matching keys
    the counts are summed and rates recomputed from the new totals.
    """
    if not buckets:
        return []

    acc: dict[tuple, dict] = {}
    for b in buckets:
        key = (b.time_window, b.dimension, b.dimension_value)
        if key in acc:
            rec = acc[key]
            rec["total"] += b.total
            rec["delivered"] += b.delivered
            rec["bounced"] += b.bounced
            rec["deferred"] += b.deferred
            rec["complained"] += b.complained
        else:
            acc[key] = {
                "total": b.total,
                "delivered": b.delivered,
                "bounced": b.bounced,
                "deferred": b.deferred,
                "complained": b.complained,
            }

    merged: list[AggregationBucket] = []
    for (tw, dim, dv), rec in acc.items():
        total = rec["total"]
        merged.append(
            AggregationBucket(
                time_window=tw,
                dimension=dim,
                dimension_value=dv,
                total=total,
                delivered=rec["delivered"],
                bounced=rec["bounced"],
                deferred=rec["deferred"],
                complained=rec["complained"],
                delivery_rate=rec["delivered"] / total if total > 0 else 0.0,
                bounce_rate=rec["bounced"] / total if total > 0 else 0.0,
                deferral_rate=rec["deferred"] / total if total > 0 else 0.0,
                complaint_rate=rec["complained"] / total if total > 0 else 0.0,
            )
        )
    return merged


def aggregate_file(
    path: str | Path,
    chunk_size: int | None = None,
    window_hours: int | None = None,
    dimensions: list[str] | None = None,
    json_format: str | None = None,
) -> tuple[list[AggregationBucket], int]:
    """Stream a file and produce merged aggregation buckets.

    Reads the file in chunks via :func:`iter_event_chunks`, aggregates each
    chunk independently, and merges overlapping buckets.  Peak memory is
    bounded to one chunk of events + one Polars DataFrame.

    *json_format* is forwarded to :func:`iter_event_chunks` — ``"ndjson"``
    or ``"concatenated"``.

    Returns ``(merged_buckets, total_event_count)``.
    """
    from llm_pipeline.email_analytics.loader import iter_event_chunks

    all_buckets: list[AggregationBucket] = []
    total_events = 0

    for events_chunk, classifications_chunk in iter_event_chunks(
        path, chunk_size=chunk_size, json_format=json_format
    ):
        total_events += len(events_chunk)
        df = events_to_dataframe(events_chunk, classifications_chunk)
        chunk_buckets = aggregate(df, window_hours=window_hours, dimensions=dimensions)
        all_buckets.extend(chunk_buckets)

    merged = merge_bucket_list(all_buckets)
    return merged, total_events
