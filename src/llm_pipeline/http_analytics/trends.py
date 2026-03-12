"""Trend analysis via linear regression over time-windowed HTTP metrics."""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np
from scipy import stats

from llm_pipeline.email_analytics.models import TrendDirection
from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpTrendFinding,
)

logger = logging.getLogger(__name__)

# Metrics where an upward slope is good
_POSITIVE_METRICS = {"success_rate"}
# Metrics where an upward slope is bad
_NEGATIVE_METRICS = {
    "client_error_rate",
    "server_error_rate",
    "known_content_error_rate",
    "tts_p95",
}


def detect_trends(
    aggregations: list[HttpAggregationBucket],
    min_points: int | None = None,
    r_squared_min: float | None = None,
    slope_min: float | None = None,
) -> list[HttpTrendFinding]:
    """Detect trends across time windows for each (dimension, dimension_value).

    Uses scipy.stats.linregress over the time-ordered metric values.
    """
    from llm_pipeline.config import settings

    min_points = min_points if min_points is not None else getattr(
        settings, "http_trend_min_points", 10
    )
    if r_squared_min is None:
        r_squared_min = getattr(settings, "http_trend_r_squared_min", 0.5)
    slope_min = slope_min if slope_min is not None else getattr(
        settings, "http_trend_slope_min", 0.001
    )

    metrics = [
        "success_rate",
        "client_error_rate",
        "server_error_rate",
        "known_content_error_rate",
        "tts_p95",
    ]

    # Group buckets by (dim, dim_value), sorted by time
    groups: dict[tuple[str, str], list[HttpAggregationBucket]] = defaultdict(list)
    for bucket in aggregations:
        groups[(bucket.dimension, bucket.dimension_value)].append(bucket)

    findings: list[HttpTrendFinding] = []

    for (dim, dim_val), buckets in groups.items():
        buckets.sort(key=lambda b: b.time_window)

        if len(buckets) < min_points:
            continue

        x = np.arange(len(buckets), dtype=float)

        for metric in metrics:
            values = [getattr(b, metric, None) for b in buckets]
            # Skip if any values are None
            if any(v is None for v in values):
                continue
            y = np.array(values, dtype=float)

            if np.std(y) == 0:
                continue

            result = stats.linregress(x, y)
            r_squared = result.rvalue ** 2

            if r_squared < r_squared_min:
                continue
            if abs(result.slope) < slope_min:
                continue

            if metric in _POSITIVE_METRICS:
                direction = (
                    TrendDirection.IMPROVING
                    if result.slope > 0
                    else TrendDirection.DEGRADING
                )
            elif metric in _NEGATIVE_METRICS:
                direction = (
                    TrendDirection.DEGRADING
                    if result.slope > 0
                    else TrendDirection.IMPROVING
                )
            else:
                direction = TrendDirection.STABLE

            findings.append(
                HttpTrendFinding(
                    direction=direction,
                    dimension=dim,
                    dimension_value=dim_val,
                    metric=metric,
                    slope=float(result.slope),
                    r_squared=r_squared,
                    num_points=len(buckets),
                    start_value=float(y[0]),
                    end_value=float(y[-1]),
                )
            )

    return findings
