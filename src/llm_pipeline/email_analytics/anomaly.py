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

# Segment-aware baseline expectations.  When historical data is sparse
# (< MIN_SAMPLE_SIZE), these priors provide reasonable defaults so anomaly
# detection isn't skipped entirely for new segments.
# Keys are engagement segment codes; values are {metric: expected_value}.
_SEGMENT_BASELINES: dict[str, dict[str, float]] = {
    "VH": {
        "delivery_rate": 0.95, "bounce_rate": 0.02,
        "deferral_rate": 0.02, "complaint_rate": 0.001,
    },
    "H": {
        "delivery_rate": 0.93, "bounce_rate": 0.03,
        "deferral_rate": 0.03, "complaint_rate": 0.002,
    },
    "M": {
        "delivery_rate": 0.90, "bounce_rate": 0.04,
        "deferral_rate": 0.04, "complaint_rate": 0.003,
    },
    "L": {
        "delivery_rate": 0.85, "bounce_rate": 0.06,
        "deferral_rate": 0.06, "complaint_rate": 0.005,
    },
    "VL": {
        "delivery_rate": 0.75, "bounce_rate": 0.10,
        "deferral_rate": 0.10, "complaint_rate": 0.008,
    },
    "RO": {
        "delivery_rate": 0.65, "bounce_rate": 0.15,
        "deferral_rate": 0.12, "complaint_rate": 0.010,
    },
    "NM": {
        "delivery_rate": 0.55, "bounce_rate": 0.20,
        "deferral_rate": 0.15, "complaint_rate": 0.012,
    },
    "DS": {
        "delivery_rate": 0.40, "bounce_rate": 0.30,
        "deferral_rate": 0.18, "complaint_rate": 0.015,
    },
    "UK": {
        "delivery_rate": 0.88, "bounce_rate": 0.05,
        "deferral_rate": 0.05, "complaint_rate": 0.003,
    },
}


def _modified_z_score(value: float, values: np.ndarray) -> float:
    """Compute modified z-score using MAD (Median Absolute Deviation).

    Falls back to standard z-score when MAD=0 (all values identical).
    The constant 0.6745 is the 0.75 quantile of the standard normal,
    used to make MAD consistent with standard deviation.

    When all baseline values are identical and the current value differs,
    returns a large z-score (sign matches direction of deviation).
    """
    median = np.median(values)
    mad = np.median(np.abs(values - median))

    if mad > 0:
        return 0.6745 * (value - median) / mad
    # Fallback: standard z-score
    std = np.std(values)
    if std > 0:
        return (value - np.mean(values)) / std
    # All values identical — if current value differs, it's extreme
    if value != median:
        # Return a large z-score; sign indicates direction
        return 10.0 if value > median else -10.0
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

        for metric in metrics:
            hist_values = hist.get(metric, []) if hist else []
            n_hist = len(hist_values)

            if n_hist >= MIN_SAMPLE_SIZE:
                # Enough historical data — use it directly
                arr = np.array(hist_values, dtype=float)
            elif bucket.dimension == "engagement_segment":
                # Sparse history for a segment — use segment baseline as prior
                seg_baseline = _SEGMENT_BASELINES.get(bucket.dimension_value)
                if seg_baseline is None or metric not in seg_baseline:
                    continue
                baseline_val = seg_baseline[metric]
                # Blend: generate synthetic data points from segment baseline,
                # weighted so that as real history grows it dominates.
                synthetic_count = MIN_SAMPLE_SIZE - n_hist
                synthetic = [baseline_val] * synthetic_count
                arr = np.array(hist_values + synthetic, dtype=float)
            else:
                continue

            current_value = getattr(bucket, metric)
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
