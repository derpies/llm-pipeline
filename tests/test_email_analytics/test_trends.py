"""Tests for trend analysis."""

from datetime import UTC, datetime

from llm_pipeline.email_analytics.models import AggregationBucket, TrendDirection
from llm_pipeline.email_analytics.trends import detect_trends


def _ts(day: int) -> datetime:
    return datetime(2025, 1, day, 10, 0, 0, tzinfo=UTC)


def _make_buckets(
    values: list[float], metric: str = "delivery_rate"
) -> list[AggregationBucket]:
    """Create aggregation buckets with a single metric varying."""
    buckets = []
    for i, val in enumerate(values):
        kwargs = {
            "time_window": _ts(day=i + 1),
            "dimension": "recipient_domain",
            "dimension_value": "gmail.com",
            "total": 100,
            "delivered": 95,
            "bounced": 3,
            "deferred": 2,
            "complained": 0,
            "delivery_rate": 0.95,
            "bounce_rate": 0.03,
            "deferral_rate": 0.02,
            "complaint_rate": 0.0,
        }
        kwargs[metric] = val
        buckets.append(AggregationBucket(**kwargs))
    return buckets


class TestDetectTrends:
    def test_flat_data_no_trends(self):
        """Flat data should produce no trends."""
        buckets = _make_buckets([0.95] * 10)
        trends = detect_trends(buckets, min_points=5, r_squared_min=0.5, slope_min=0.01)
        # delivery_rate is flat → no trend
        delivery_trends = [t for t in trends if t.metric == "delivery_rate"]
        assert len(delivery_trends) == 0

    def test_clear_improving_trend(self):
        """Linearly improving delivery rate should be detected."""
        values = [0.80 + 0.02 * i for i in range(10)]  # 0.80 → 0.98
        buckets = _make_buckets(values)
        trends = detect_trends(buckets, min_points=5, r_squared_min=0.5, slope_min=0.005)
        delivery_trends = [t for t in trends if t.metric == "delivery_rate"]
        assert len(delivery_trends) == 1
        assert delivery_trends[0].direction == TrendDirection.IMPROVING
        assert delivery_trends[0].r_squared > 0.9

    def test_degrading_delivery_rate(self):
        """Linearly degrading delivery rate should be detected."""
        values = [0.98 - 0.02 * i for i in range(10)]  # 0.98 → 0.80
        buckets = _make_buckets(values)
        trends = detect_trends(buckets, min_points=5, r_squared_min=0.5, slope_min=0.005)
        delivery_trends = [t for t in trends if t.metric == "delivery_rate"]
        assert len(delivery_trends) == 1
        assert delivery_trends[0].direction == TrendDirection.DEGRADING

    def test_bounce_rate_increasing_is_degrading(self):
        """Increasing bounce rate should be flagged as degrading."""
        values = [0.01 + 0.01 * i for i in range(10)]  # 0.01 → 0.10
        buckets = _make_buckets(values, metric="bounce_rate")
        trends = detect_trends(buckets, min_points=5, r_squared_min=0.5, slope_min=0.005)
        bounce_trends = [t for t in trends if t.metric == "bounce_rate"]
        assert len(bounce_trends) == 1
        assert bounce_trends[0].direction == TrendDirection.DEGRADING

    def test_insufficient_data_skipped(self):
        """Fewer than min_points should produce no trends."""
        buckets = _make_buckets([0.80, 0.85, 0.90])
        trends = detect_trends(buckets, min_points=5, r_squared_min=0.5, slope_min=0.01)
        assert len(trends) == 0

    def test_noisy_data_filtered(self):
        """Noisy data with low R-squared should be filtered out."""
        import random

        random.seed(42)
        values = [random.uniform(0.4, 0.6) for _ in range(10)]
        buckets = _make_buckets(values)
        trends = detect_trends(buckets, min_points=5, r_squared_min=0.8, slope_min=0.01)
        delivery_trends = [t for t in trends if t.metric == "delivery_rate"]
        assert len(delivery_trends) == 0
