"""Trend analysis via linear regression over time-windowed metrics."""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np
from scipy import stats

from llm_pipeline.config import settings
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    TrendDirection,
    TrendFinding,
)

logger = logging.getLogger(__name__)

# Metrics where an upward slope is good
_POSITIVE_METRICS = {"delivery_rate"}
# Metrics where an upward slope is bad
_NEGATIVE_METRICS = {"bounce_rate", "deferral_rate", "complaint_rate"}


def detect_trends(
    aggregations: list[AggregationBucket],
    min_points: int | None = None,
    r_squared_min: float | None = None,
    slope_min: float | None = None,
) -> list[TrendFinding]:
    """Detect trends across time windows for each (dimension, dimension_value).

    Uses scipy.stats.linregress over the time-ordered metric values.
    Filters out results with low R-squared or negligible slope.
    """
    min_points = min_points if min_points is not None else settings.email_trend_min_points
    if r_squared_min is None:
        r_squared_min = settings.email_trend_r_squared_min
    slope_min = slope_min if slope_min is not None else settings.email_trend_slope_min

    metrics = ["delivery_rate", "bounce_rate", "deferral_rate", "complaint_rate"]

    # Group buckets by (dim, dim_value), sorted by time
    groups: dict[tuple[str, str], list[AggregationBucket]] = defaultdict(list)
    for bucket in aggregations:
        groups[(bucket.dimension, bucket.dimension_value)].append(bucket)

    findings: list[TrendFinding] = []

    for (dim, dim_val), buckets in groups.items():
        # Sort by time window
        buckets.sort(key=lambda b: b.time_window)

        if len(buckets) < min_points:
            continue

        # Use ordinal index as x-axis (evenly spaced time windows)
        x = np.arange(len(buckets), dtype=float)

        for metric in metrics:
            values = [getattr(b, metric) for b in buckets]
            y = np.array(values, dtype=float)

            # Skip if all values are identical (no variance)
            if np.std(y) == 0:
                continue

            result = stats.linregress(x, y)
            r_squared = result.rvalue ** 2

            if r_squared < r_squared_min:
                continue
            if abs(result.slope) < slope_min:
                continue

            # Determine direction based on metric type and slope
            if metric in _POSITIVE_METRICS:
                direction = (
                    TrendDirection.IMPROVING if result.slope > 0 else TrendDirection.DEGRADING
                )
            elif metric in _NEGATIVE_METRICS:
                direction = (
                    TrendDirection.DEGRADING if result.slope > 0 else TrendDirection.IMPROVING
                )
            else:
                direction = TrendDirection.STABLE

            findings.append(
                TrendFinding(
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
