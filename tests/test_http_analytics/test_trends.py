"""Tests for HTTP trend detection."""

from datetime import UTC, datetime

from llm_pipeline.email_analytics.models import TrendDirection
from llm_pipeline.http_analytics.models import HttpAggregationBucket
from llm_pipeline.http_analytics.trends import detect_trends


def _ts(minute: int) -> datetime:
    return datetime(2026, 3, 1, 10, minute, 0, tzinfo=UTC)


def _series(
    metric: str,
    values: list[float],
    dimension: str = "http_host",
    dimension_value: str = "app.ontraport.com",
) -> list[HttpAggregationBucket]:
    """Build a time-series of buckets with the given metric values."""
    buckets = []
    for i, val in enumerate(values):
        kwargs = {
            "time_window": _ts(i),
            "dimension": dimension,
            "dimension_value": dimension_value,
            "total": 1000,
            "status_2xx": 900,
            "success_rate": 0.90,
            "client_error_rate": 0.05,
            "server_error_rate": 0.01,
            "known_content_error_rate": 0.005,
            "tts_p95": 1.0,
        }
        kwargs[metric] = val
        buckets.append(HttpAggregationBucket(**kwargs))
    return buckets


class TestDetectTrends:
    def test_no_trends_constant_data(self):
        """Constant data should produce no trends."""
        data = _series("success_rate", [0.90] * 15)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        sr_trends = [t for t in trends if t.metric == "success_rate"]
        assert len(sr_trends) == 0

    def test_degrading_success_rate(self):
        """Steadily declining success rate should be detected as degrading."""
        values = [0.95 - 0.03 * i for i in range(15)]  # 0.95 → 0.53
        data = _series("success_rate", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        sr_trends = [t for t in trends if t.metric == "success_rate"]
        assert len(sr_trends) == 1
        assert sr_trends[0].direction == TrendDirection.DEGRADING
        assert sr_trends[0].slope < 0
        assert sr_trends[0].r_squared > 0.9

    def test_improving_success_rate(self):
        """Steadily rising success rate should be detected as improving."""
        values = [0.50 + 0.03 * i for i in range(15)]  # 0.50 → 0.92
        data = _series("success_rate", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        sr_trends = [t for t in trends if t.metric == "success_rate"]
        assert len(sr_trends) == 1
        assert sr_trends[0].direction == TrendDirection.IMPROVING

    def test_degrading_error_rate(self):
        """Rising error rate should be degrading for a negative metric."""
        values = [0.01 + 0.02 * i for i in range(15)]  # 0.01 → 0.29
        data = _series("client_error_rate", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        er_trends = [t for t in trends if t.metric == "client_error_rate"]
        assert len(er_trends) == 1
        assert er_trends[0].direction == TrendDirection.DEGRADING

    def test_improving_error_rate(self):
        """Falling error rate should be improving for a negative metric."""
        values = [0.30 - 0.02 * i for i in range(15)]  # 0.30 → 0.02
        data = _series("client_error_rate", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        er_trends = [t for t in trends if t.metric == "client_error_rate"]
        assert len(er_trends) == 1
        assert er_trends[0].direction == TrendDirection.IMPROVING

    def test_latency_trend(self):
        """Rising p95 latency should be degrading."""
        values = [0.5 + 0.3 * i for i in range(15)]  # 0.5 → 4.7
        data = _series("tts_p95", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        lat_trends = [t for t in trends if t.metric == "tts_p95"]
        assert len(lat_trends) == 1
        assert lat_trends[0].direction == TrendDirection.DEGRADING

    def test_insufficient_points_skipped(self):
        """Fewer than min_points should produce no trends."""
        data = _series("success_rate", [0.95 - 0.03 * i for i in range(5)])
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        assert len(trends) == 0

    def test_low_r_squared_filtered(self):
        """Noisy data with low R² should be filtered out."""
        import random
        random.seed(42)
        values = [random.uniform(0.4, 0.9) for _ in range(15)]
        data = _series("success_rate", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.9, slope_min=0.001)
        sr_trends = [t for t in trends if t.metric == "success_rate"]
        assert len(sr_trends) == 0

    def test_start_end_values(self):
        """Verify start_value and end_value are correct."""
        values = [0.95 - 0.03 * i for i in range(15)]
        data = _series("success_rate", values)
        trends = detect_trends(data, min_points=10, r_squared_min=0.5, slope_min=0.001)
        sr_trends = [t for t in trends if t.metric == "success_rate"]
        assert len(sr_trends) == 1
        assert abs(sr_trends[0].start_value - 0.95) < 0.001
        assert abs(sr_trends[0].end_value - values[-1]) < 0.001
