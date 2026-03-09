"""Polars-based dimensional aggregation for email delivery events."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

from llm_pipeline.config import settings
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    DataCompleteness,
    DeliveryEvent,
    DeliveryStatus,
    SmtpClassification,
)

DEFAULT_DIMENSIONS = [
    "listid",
    "recipient_domain",
    "outmtaid_ip",
    "listid_type",
    "engagement_segment",
    "xmrid_account_id",
    "compliance_status",
    "provider_hint",
]

# Fields tracked for data completeness (zero/empty = missing data)
_COMPLETENESS_FIELDS = [
    "xmrid_account_id",
    "xmrid_contact_id",
    "compliance_status",
    "op_queue_time_parsed",
    "last_active_ts",
]

# String ID fields where "0" means "unknown/missing" (not just empty)
_ZERO_VALUE_ID_FIELDS = frozenset({
    "xmrid_account_id",
    "xmrid_contact_id",
})


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
                "listid": pl.Utf8,
                "listid_type": pl.Utf8,
                "engagement_segment": pl.Utf8,
                "xmrid_account_id": pl.Utf8,
                "xmrid_contact_id": pl.Utf8,
                "compliance_status": pl.Utf8,
                "is_zero_cohort": pl.Boolean,
                "pre_edge_latency": pl.Float64,
                "delivery_attempt_time": pl.Float64,
                "marketing_flag": pl.Int64,
                "op_queue_time_parsed": pl.Float64,
                "last_active_ts": pl.Float64,
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
                "listid": event.listid,
                "listid_type": event.listid_type,
                "engagement_segment": event.engagement_segment,
                "xmrid_account_id": event.xmrid_account_id,
                "xmrid_contact_id": event.xmrid_contact_id,
                "compliance_status": event.compliance_status,
                "is_zero_cohort": event.is_zero_cohort,
                "pre_edge_latency": event.pre_edge_latency,
                "delivery_attempt_time": event.delivery_attempt_time,
                "marketing_flag": event.marketing_flag,
                "op_queue_time_parsed": event.op_queue_time_parsed,
                "last_active_ts": event.last_active_ts,
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

    # Build latency aggregation expressions
    latency_aggs = []
    has_pre_edge = "pre_edge_latency" in df.columns
    has_delivery_time = "delivery_attempt_time" in df.columns

    if has_pre_edge:
        latency_aggs.extend([
            pl.col("pre_edge_latency").drop_nulls().mean().alias("pre_edge_latency_mean"),
            pl.col("pre_edge_latency").drop_nulls().median().alias("pre_edge_latency_p50"),
            pl.col("pre_edge_latency").drop_nulls().quantile(0.95).alias("pre_edge_latency_p95"),
            pl.col("pre_edge_latency").drop_nulls().quantile(0.99).alias("pre_edge_latency_p99"),
            pl.col("pre_edge_latency").drop_nulls().max().alias("pre_edge_latency_max"),
        ])
    if has_delivery_time:
        latency_aggs.extend([
            pl.col("delivery_attempt_time").drop_nulls().mean().alias("delivery_time_mean"),
            pl.col("delivery_attempt_time").drop_nulls().median().alias("delivery_time_p50"),
            pl.col("delivery_attempt_time").drop_nulls().quantile(0.95).alias("delivery_time_p95"),
            pl.col("delivery_attempt_time").drop_nulls().quantile(0.99).alias("delivery_time_p99"),
            pl.col("delivery_attempt_time").drop_nulls().max().alias("delivery_time_max"),
        ])

    for dim in dimensions:
        if dim not in df.columns:
            continue

        base_aggs = [
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
        ]

        grouped = (
            df.group_by(["time_window", dim])
            .agg(base_aggs + latency_aggs)
            .sort(["time_window", dim])
        )

        for row in grouped.iter_rows(named=True):
            total = row["total"]
            bucket_kwargs: dict = {
                "time_window": row["time_window"],
                "dimension": dim,
                "dimension_value": row[dim],
                "total": total,
                "delivered": row["delivered"],
                "bounced": row["bounced"],
                "deferred": row["deferred"],
                "complained": row["complained"],
                "delivery_rate": row["delivered"] / total if total > 0 else 0.0,
                "bounce_rate": row["bounced"] / total if total > 0 else 0.0,
                "deferral_rate": row["deferred"] / total if total > 0 else 0.0,
                "complaint_rate": row["complained"] / total if total > 0 else 0.0,
            }

            if has_pre_edge:
                bucket_kwargs["pre_edge_latency_mean"] = row.get("pre_edge_latency_mean")
                bucket_kwargs["pre_edge_latency_p50"] = row.get("pre_edge_latency_p50")
                bucket_kwargs["pre_edge_latency_p95"] = row.get("pre_edge_latency_p95")
                bucket_kwargs["pre_edge_latency_p99"] = row.get("pre_edge_latency_p99")
                bucket_kwargs["pre_edge_latency_max"] = row.get("pre_edge_latency_max")
            if has_delivery_time:
                bucket_kwargs["delivery_time_mean"] = row.get("delivery_time_mean")
                bucket_kwargs["delivery_time_p50"] = row.get("delivery_time_p50")
                bucket_kwargs["delivery_time_p95"] = row.get("delivery_time_p95")
                bucket_kwargs["delivery_time_p99"] = row.get("delivery_time_p99")
                bucket_kwargs["delivery_time_max"] = row.get("delivery_time_max")

            buckets.append(AggregationBucket(**bucket_kwargs))

    return buckets


def compute_data_completeness(
    df: pl.DataFrame,
    window_hours: int | None = None,
    dimensions: list[str] | None = None,
) -> list[DataCompleteness]:
    """Compute zero-value rates for key fields, grouped by time_window + dimension.

    Tracks how many records have zero/empty values for fields that should
    contain real data (account_id, contact_id, compliance, etc.).
    """
    if df.is_empty():
        return []

    window_hours = window_hours or settings.email_time_window_hours
    dimensions = dimensions or ["listid", "engagement_segment"]

    df = df.with_columns(
        _truncate_to_window(pl.col("timestamp"), window_hours).alias("time_window")
    )

    results: list[DataCompleteness] = []

    for dim in dimensions:
        if dim not in df.columns:
            continue

        for field_name in _COMPLETENESS_FIELDS:
            if field_name not in df.columns:
                continue

            col = pl.col(field_name)
            dtype = df.schema[field_name]

            # Zero/empty check depends on the column type
            if dtype in (pl.Utf8, pl.String):
                if field_name in _ZERO_VALUE_ID_FIELDS:
                    # "0" means missing for ID fields
                    zero_expr = (
                        (col == "") | (col == "0")
                    ).sum().alias("zero_count")
                else:
                    zero_expr = (col == "").sum().alias("zero_count")
            else:
                zero_expr = (col == 0).sum().alias("zero_count")

            grouped = (
                df.group_by(["time_window", dim])
                .agg(pl.len().alias("total_records"), zero_expr)
                .sort(["time_window", dim])
            )

            for row in grouped.iter_rows(named=True):
                total = row["total_records"]
                zero_count = row["zero_count"]
                results.append(
                    DataCompleteness(
                        time_window=row["time_window"],
                        dimension=dim,
                        dimension_value=row[dim],
                        total_records=total,
                        field_name=field_name,
                        zero_count=zero_count,
                        zero_rate=zero_count / total if total > 0 else 0.0,
                    )
                )

    return results


def merge_bucket_list(buckets: list[AggregationBucket]) -> list[AggregationBucket]:
    """Deduplicate and merge buckets that share the same key.

    Key is ``(time_window, dimension, dimension_value)``.  For matching keys
    the counts are summed and rates recomputed from the new totals.

    Latency: uses weighted mean for _mean fields.  p50/p95 are dropped on
    merge (imprecise with pre-aggregated data).
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

            # Weighted-mean accumulation for latency
            for lat_field in ("pre_edge_latency_mean", "delivery_time_mean"):
                val = getattr(b, lat_field, None)
                if val is not None:
                    rec[f"{lat_field}_sum"] = rec.get(f"{lat_field}_sum", 0.0) + val * b.total
                    rec[f"{lat_field}_count"] = rec.get(f"{lat_field}_count", 0) + b.total
        else:
            rec = {
                "total": b.total,
                "delivered": b.delivered,
                "bounced": b.bounced,
                "deferred": b.deferred,
                "complained": b.complained,
            }
            for lat_field in ("pre_edge_latency_mean", "delivery_time_mean"):
                val = getattr(b, lat_field, None)
                if val is not None:
                    rec[f"{lat_field}_sum"] = val * b.total
                    rec[f"{lat_field}_count"] = b.total
            acc[key] = rec

    merged: list[AggregationBucket] = []
    for (tw, dim, dv), rec in acc.items():
        total = rec["total"]
        kwargs: dict = {
            "time_window": tw,
            "dimension": dim,
            "dimension_value": dv,
            "total": total,
            "delivered": rec["delivered"],
            "bounced": rec["bounced"],
            "deferred": rec["deferred"],
            "complained": rec["complained"],
            "delivery_rate": rec["delivered"] / total if total > 0 else 0.0,
            "bounce_rate": rec["bounced"] / total if total > 0 else 0.0,
            "deferral_rate": rec["deferred"] / total if total > 0 else 0.0,
            "complaint_rate": rec["complained"] / total if total > 0 else 0.0,
        }
        for lat_field in ("pre_edge_latency_mean", "delivery_time_mean"):
            cnt = rec.get(f"{lat_field}_count", 0)
            if cnt > 0:
                kwargs[lat_field] = rec[f"{lat_field}_sum"] / cnt
        merged.append(AggregationBucket(**kwargs))
    return merged


def merge_completeness(items: list[DataCompleteness]) -> list[DataCompleteness]:
    """Merge completeness records with the same key by summing counts."""
    if not items:
        return []

    acc: dict[tuple, dict] = {}
    for c in items:
        key = (c.time_window, c.dimension, c.dimension_value, c.field_name)
        if key in acc:
            rec = acc[key]
            rec["total_records"] += c.total_records
            rec["zero_count"] += c.zero_count
        else:
            acc[key] = {
                "total_records": c.total_records,
                "zero_count": c.zero_count,
            }

    merged: list[DataCompleteness] = []
    for (tw, dim, dv, fn), rec in acc.items():
        total = rec["total_records"]
        merged.append(
            DataCompleteness(
                time_window=tw,
                dimension=dim,
                dimension_value=dv,
                total_records=total,
                field_name=fn,
                zero_count=rec["zero_count"],
                zero_rate=rec["zero_count"] / total if total > 0 else 0.0,
            )
        )
    return merged


@dataclass
class FileAggregationResult:
    """Return type for aggregate_file — buckets + completeness + count."""

    buckets: list[AggregationBucket] = field(default_factory=list)
    completeness: list[DataCompleteness] = field(default_factory=list)
    event_count: int = 0


def aggregate_file(
    path: str | Path,
    chunk_size: int | None = None,
    window_hours: int | None = None,
    dimensions: list[str] | None = None,
    json_format: str | None = None,
) -> FileAggregationResult:
    """Stream a file and produce merged aggregation buckets + completeness.

    Reads the file in chunks via :func:`iter_event_chunks`, aggregates each
    chunk independently, and merges overlapping buckets.  Peak memory is
    bounded to one chunk of events + one Polars DataFrame.

    *json_format* is forwarded to :func:`iter_event_chunks` — ``"ndjson"``
    or ``"concatenated"``.
    """
    from llm_pipeline.email_analytics.loader import iter_event_chunks

    all_buckets: list[AggregationBucket] = []
    all_completeness: list[DataCompleteness] = []
    total_events = 0

    for events_chunk, classifications_chunk in iter_event_chunks(
        path, chunk_size=chunk_size, json_format=json_format
    ):
        total_events += len(events_chunk)
        df = events_to_dataframe(events_chunk, classifications_chunk)
        chunk_buckets = aggregate(df, window_hours=window_hours, dimensions=dimensions)
        all_buckets.extend(chunk_buckets)
        chunk_completeness = compute_data_completeness(df, window_hours=window_hours)
        all_completeness.extend(chunk_completeness)

    merged_buckets = merge_bucket_list(all_buckets)
    merged_completeness = merge_completeness(all_completeness)
    return FileAggregationResult(
        buckets=merged_buckets,
        completeness=merged_completeness,
        event_count=total_events,
    )
