"""Anomaly detection using modified z-score (MAD-based).

Email delivery data is heavy-tailed — standard z-score is inflated by
outliers. Modified z-score based on Median Absolute Deviation is robust
to this. Falls back to standard z-score when MAD=0.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np

from llm_pipeline.config import settings
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnomalyFinding,
    AnomalyType,
)

logger = logging.getLogger(__name__)

# Metrics where a drop is bad (lower = worse)
_POSITIVE_METRICS = {"delivery_rate"}

# Metrics where a spike is bad (higher = worse)
_NEGATIVE_METRICS = {"bounce_rate", "deferral_rate", "complaint_rate"}

_METRIC_TO_ANOMALY_HIGH: dict[str, AnomalyType] = {
    "bounce_rate": AnomalyType.BOUNCE_SPIKE,
    "deferral_rate": AnomalyType.DEFERRAL_SPIKE,
    "complaint_rate": AnomalyType.COMPLAINT_SPIKE,
    "delivery_rate": AnomalyType.RATE_SPIKE,
}
_METRIC_TO_ANOMALY_LOW: dict[str, AnomalyType] = {
    "delivery_rate": AnomalyType.RATE_DROP,
    "bounce_rate": AnomalyType.BOUNCE_SPIKE,
    "deferral_rate": AnomalyType.DEFERRAL_SPIKE,
    "complaint_rate": AnomalyType.COMPLAINT_SPIKE,
}

# Minimum number of historical data points needed for anomaly detection
MIN_SAMPLE_SIZE = 5


def _modified_z_score(value: float, values: np.ndarray) -> float:
    """Compute modified z-score using MAD (Median Absolute Deviation).

    Falls back to standard z-score when MAD=0 (all values identical).
    The constant 0.6745 is the 0.75 quantile of the standard normal,
    used to make MAD consistent with standard deviation.
    """
    median = np.median(values)
    mad = np.median(np.abs(values - median))

    if mad > 0:
        return 0.6745 * (value - median) / mad
    # Fallback: standard z-score
    std = np.std(values)
    if std > 0:
        return (value - np.mean(values)) / std
    return 0.0


def _severity_from_z(z: float) -> str:
    """Map z-score magnitude to severity label."""
    abs_z = abs(z)
    if abs_z >= 5.0:
        return "critical"
    if abs_z >= 4.0:
        return "high"
    if abs_z >= 3.0:
        return "medium"
    return "low"


def detect_anomalies(
    current: list[AggregationBucket],
    historical: list[AggregationBucket],
    threshold: float | None = None,
) -> list[AnomalyFinding]:
    """Detect anomalies in current aggregations against historical baselines.

    For each (dimension, dimension_value) group, computes modified z-scores
    for delivery metrics. Direction-aware: delivery_rate drops and
    bounce/deferral/complaint spikes are flagged.
    """
    threshold = threshold if threshold is not None else settings.email_anomaly_threshold
    metrics = ["delivery_rate", "bounce_rate", "deferral_rate", "complaint_rate"]

    # Build historical lookup: (dim, dim_value) → {metric: [values]}
    hist_map: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for bucket in historical:
        key = (bucket.dimension, bucket.dimension_value)
        for metric in metrics:
            hist_map[key][metric].append(getattr(bucket, metric))

    findings: list[AnomalyFinding] = []

    for bucket in current:
        key = (bucket.dimension, bucket.dimension_value)
        hist = hist_map.get(key)
        if not hist:
            continue

        for metric in metrics:
            hist_values = hist.get(metric, [])
            if len(hist_values) < MIN_SAMPLE_SIZE:
                continue

            current_value = getattr(bucket, metric)
            arr = np.array(hist_values, dtype=float)
            z = _modified_z_score(current_value, arr)

            # Direction-aware: only flag meaningful directions
            is_anomaly = False
            if metric in _POSITIVE_METRICS and z < -threshold:
                # Drop in a positive metric — bad
                is_anomaly = True
                anomaly_type = _METRIC_TO_ANOMALY_LOW[metric]
            elif metric in _NEGATIVE_METRICS and z > threshold:
                # Spike in a negative metric — bad
                is_anomaly = True
                anomaly_type = _METRIC_TO_ANOMALY_HIGH[metric]

            if is_anomaly:
                findings.append(
                    AnomalyFinding(
                        anomaly_type=anomaly_type,
                        dimension=bucket.dimension,
                        dimension_value=bucket.dimension_value,
                        metric=metric,
                        current_value=current_value,
                        baseline_mean=float(np.mean(arr)),
                        z_score=z,
                        severity=_severity_from_z(z),
                    )
                )

    return findings
