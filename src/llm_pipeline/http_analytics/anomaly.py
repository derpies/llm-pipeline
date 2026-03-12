"""Anomaly detection for HTTP metrics using modified z-score (MAD-based).

Same robust algorithm as email analytics, adapted for HTTP status-rate and
latency metrics with category-aware baselines.
"""

from __future__ import annotations

import logging
from collections import defaultdict

import numpy as np

from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpAnomalyFinding,
    HttpAnomalyType,
)

logger = logging.getLogger(__name__)

# Metrics where a drop is bad (lower = worse)
_POSITIVE_METRICS = {"success_rate"}

# Metrics where a spike is bad (higher = worse)
_NEGATIVE_METRICS = {
    "client_error_rate",
    "server_error_rate",
    "known_content_error_rate",
    "tts_p95",
}

_METRIC_TO_ANOMALY_HIGH: dict[str, HttpAnomalyType] = {
    "client_error_rate": HttpAnomalyType.ERROR_RATE_SPIKE,
    "server_error_rate": HttpAnomalyType.ERROR_RATE_SPIKE,
    "known_content_error_rate": HttpAnomalyType.STATUS_679_SPIKE,
    "tts_p95": HttpAnomalyType.LATENCY_SPIKE,
    "success_rate": HttpAnomalyType.ERROR_RATE_SPIKE,
}
_METRIC_TO_ANOMALY_LOW: dict[str, HttpAnomalyType] = {
    "success_rate": HttpAnomalyType.ERROR_RATE_SPIKE,
}

# Minimum data points needed for anomaly detection
MIN_SAMPLE_SIZE = 5

# Category-aware baseline expectations for request categories.
# Used as priors when historical data is sparse.
_CATEGORY_BASELINES: dict[str, dict[str, float]] = {
    "php_probe": {
        "success_rate": 0.0,
        "client_error_rate": 1.0,
        "server_error_rate": 0.0,
        "known_content_error_rate": 0.0,
        "tts_p95": 0.1,
    },
    "tracking_pixel": {
        "success_rate": 0.95,
        "client_error_rate": 0.02,
        "server_error_rate": 0.01,
        "known_content_error_rate": 0.01,
        "tts_p95": 0.5,
    },
    "click_tracking": {
        "success_rate": 0.92,
        "client_error_rate": 0.05,
        "server_error_rate": 0.01,
        "known_content_error_rate": 0.01,
        "tts_p95": 0.5,
    },
    "page_load": {
        "success_rate": 0.98,
        "client_error_rate": 0.01,
        "server_error_rate": 0.005,
        "known_content_error_rate": 0.005,
        "tts_p95": 2.0,
    },
    "static_asset": {
        "success_rate": 0.99,
        "client_error_rate": 0.005,
        "server_error_rate": 0.002,
        "known_content_error_rate": 0.002,
        "tts_p95": 0.3,
    },
    "api_call": {
        "success_rate": 0.97,
        "client_error_rate": 0.02,
        "server_error_rate": 0.005,
        "known_content_error_rate": 0.0,
        "tts_p95": 1.0,
    },
}


def _modified_z_score(value: float, values: np.ndarray) -> float:
    """Compute modified z-score using MAD.

    Falls back to standard z-score when MAD=0.
    """
    median = np.median(values)
    mad = np.median(np.abs(values - median))

    if mad > 0:
        return 0.6745 * (value - median) / mad
    std = np.std(values)
    if std > 0:
        return (value - np.mean(values)) / std
    if value != median:
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
    current: list[HttpAggregationBucket],
    historical: list[HttpAggregationBucket],
    threshold: float | None = None,
) -> list[HttpAnomalyFinding]:
    """Detect anomalies in current HTTP aggregations against historical baselines.

    Direction-aware: success_rate drops and error/latency spikes are flagged.
    """
    from llm_pipeline.config import settings

    threshold = threshold if threshold is not None else getattr(
        settings, "http_anomaly_threshold", 3.5
    )
    metrics = [
        "success_rate",
        "client_error_rate",
        "server_error_rate",
        "known_content_error_rate",
        "tts_p95",
    ]

    # Build historical lookup: (dim, dim_value) → {metric: [values]}
    hist_map: dict[tuple[str, str], dict[str, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for bucket in historical:
        key = (bucket.dimension, bucket.dimension_value)
        for metric in metrics:
            val = getattr(bucket, metric, None)
            if val is not None:
                hist_map[key][metric].append(val)

    findings: list[HttpAnomalyFinding] = []

    for bucket in current:
        key = (bucket.dimension, bucket.dimension_value)
        hist = hist_map.get(key)

        for metric in metrics:
            current_value = getattr(bucket, metric, None)
            if current_value is None:
                continue

            hist_values = hist.get(metric, []) if hist else []
            n_hist = len(hist_values)

            if n_hist >= MIN_SAMPLE_SIZE:
                arr = np.array(hist_values, dtype=float)
            elif bucket.dimension == "request_category":
                # Sparse history — use category baseline as prior
                cat_baseline = _CATEGORY_BASELINES.get(bucket.dimension_value)
                if cat_baseline is None or metric not in cat_baseline:
                    continue
                baseline_val = cat_baseline[metric]
                synthetic_count = MIN_SAMPLE_SIZE - n_hist
                synthetic = [baseline_val] * synthetic_count
                arr = np.array(hist_values + synthetic, dtype=float)
            else:
                continue

            z = _modified_z_score(current_value, arr)

            is_anomaly = False
            if metric in _POSITIVE_METRICS and z < -threshold:
                is_anomaly = True
                anomaly_type = _METRIC_TO_ANOMALY_LOW[metric]
            elif metric in _NEGATIVE_METRICS and z > threshold:
                is_anomaly = True
                anomaly_type = _METRIC_TO_ANOMALY_HIGH[metric]

            if is_anomaly:
                findings.append(
                    HttpAnomalyFinding(
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
