"""Tests for anomaly detection."""

from datetime import UTC, datetime

from llm_pipeline.email_analytics.anomaly import detect_anomalies
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnomalyType,
)


def _ts(day: int = 1) -> datetime:
    return datetime(2025, 1, day, 10, 0, 0, tzinfo=UTC)


def _stable_history(
    n: int = 30, delivery_rate: float = 0.95, bounce_rate: float = 0.03,
    dimension: str = "recipient_domain", dimension_value: str = "gmail.com",
) -> list[AggregationBucket]:
    """Generate n days of stable historical aggregations."""
    return [
        AggregationBucket(
            time_window=_ts(day=d),
            dimension=dimension,
            dimension_value=dimension_value,
            total=100,
            delivered=int(delivery_rate * 100),
            bounced=int(bounce_rate * 100),
            deferred=2,
            complained=0,
            delivery_rate=delivery_rate,
            bounce_rate=bounce_rate,
            deferral_rate=0.02,
            complaint_rate=0.0,
        )
        for d in range(1, n + 1)
    ]


class TestDetectAnomalies:
    def test_no_anomalies_when_matching(self, historical_aggregations):
        """Current data matching historical baseline should produce no anomalies."""
        current = [
            AggregationBucket(
                time_window=_ts(day=31),
                dimension="recipient_domain",
                dimension_value="gmail.com",
                total=100,
                delivered=95,
                bounced=3,
                deferred=2,
                complained=0,
                delivery_rate=0.95,
                bounce_rate=0.03,
                deferral_rate=0.02,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, historical_aggregations, threshold=3.5)
        assert len(anomalies) == 0

    def test_delivery_rate_drop(self, historical_aggregations):
        """Sharp delivery rate drop should be detected."""
        current = [
            AggregationBucket(
                time_window=_ts(day=31),
                dimension="recipient_domain",
                dimension_value="gmail.com",
                total=100,
                delivered=40,
                bounced=50,
                deferred=10,
                complained=0,
                delivery_rate=0.40,
                bounce_rate=0.50,
                deferral_rate=0.10,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, historical_aggregations, threshold=3.5)
        assert len(anomalies) > 0

        rate_drops = [a for a in anomalies if a.anomaly_type == AnomalyType.RATE_DROP]
        assert len(rate_drops) > 0
        assert rate_drops[0].dimension_value == "gmail.com"

    def test_bounce_spike(self):
        """Bounce rate spike should be detected."""
        historical = _stable_history(30, delivery_rate=0.95, bounce_rate=0.03)
        current = [
            AggregationBucket(
                time_window=_ts(day=31),
                dimension="recipient_domain",
                dimension_value="gmail.com",
                total=100,
                delivered=50,
                bounced=45,
                deferred=5,
                complained=0,
                delivery_rate=0.50,
                bounce_rate=0.45,
                deferral_rate=0.05,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, historical, threshold=3.5)
        bounce_spikes = [a for a in anomalies if a.anomaly_type == AnomalyType.BOUNCE_SPIKE]
        assert len(bounce_spikes) > 0

    def test_min_sample_size(self):
        """Should not detect anomalies with insufficient historical data (non-segment)."""
        historical = _stable_history(3)  # Less than MIN_SAMPLE_SIZE
        current = [
            AggregationBucket(
                time_window=_ts(day=4),
                dimension="recipient_domain",
                dimension_value="gmail.com",
                total=100,
                delivered=10,
                bounced=90,
                deferred=0,
                complained=0,
                delivery_rate=0.10,
                bounce_rate=0.90,
                deferral_rate=0.0,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, historical, threshold=3.5)
        assert len(anomalies) == 0

    def test_no_historical_data(self):
        """No historical data should produce no anomalies."""
        current = [
            AggregationBucket(
                time_window=_ts(),
                dimension="recipient_domain",
                dimension_value="new-domain.com",
                total=100,
                delivered=10,
                bounced=90,
                deferred=0,
                complained=0,
                delivery_rate=0.10,
                bounce_rate=0.90,
                deferral_rate=0.0,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, [], threshold=3.5)
        assert len(anomalies) == 0


class TestSegmentAwareBaselines:
    def test_vh_segment_anomaly_with_no_history(self):
        """VH segment with terrible delivery should trigger anomaly even without history."""
        current = [
            AggregationBucket(
                time_window=_ts(day=1),
                dimension="engagement_segment",
                dimension_value="VH",
                total=100,
                delivered=10,
                bounced=80,
                deferred=10,
                complained=0,
                delivery_rate=0.10,
                bounce_rate=0.80,
                deferral_rate=0.10,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, [], threshold=3.5)
        # VH expects ~95% delivery; 10% should trigger anomaly
        rate_drops = [a for a in anomalies if a.anomaly_type == AnomalyType.RATE_DROP]
        assert len(rate_drops) > 0

    def test_ds_segment_low_delivery_not_anomalous(self):
        """DS segment with 40% delivery matches baseline — no anomaly."""
        current = [
            AggregationBucket(
                time_window=_ts(day=1),
                dimension="engagement_segment",
                dimension_value="DS",
                total=100,
                delivered=40,
                bounced=30,
                deferred=18,
                complained=0,
                delivery_rate=0.40,
                bounce_rate=0.30,
                deferral_rate=0.18,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, [], threshold=3.5)
        # DS baseline is ~40% delivery; this matches — should not flag
        rate_drops = [a for a in anomalies if a.anomaly_type == AnomalyType.RATE_DROP]
        assert len(rate_drops) == 0

    def test_segment_baseline_blends_with_history(self):
        """Sparse history + segment baseline should still detect anomalies."""
        # 3 data points (less than MIN_SAMPLE_SIZE) — segment baseline fills the rest
        historical = _stable_history(
            3, delivery_rate=0.94, bounce_rate=0.03,
            dimension="engagement_segment", dimension_value="VH",
        )
        current = [
            AggregationBucket(
                time_window=_ts(day=4),
                dimension="engagement_segment",
                dimension_value="VH",
                total=100,
                delivered=10,
                bounced=80,
                deferred=10,
                complained=0,
                delivery_rate=0.10,
                bounce_rate=0.80,
                deferral_rate=0.10,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, historical, threshold=3.5)
        rate_drops = [a for a in anomalies if a.anomaly_type == AnomalyType.RATE_DROP]
        assert len(rate_drops) > 0

    def test_non_segment_dimension_no_baseline_fallback(self):
        """Non-segment dimensions don't use segment baselines when history is sparse."""
        historical = _stable_history(3)  # sparse, dimension="recipient_domain"
        current = [
            AggregationBucket(
                time_window=_ts(day=4),
                dimension="recipient_domain",
                dimension_value="gmail.com",
                total=100,
                delivered=10,
                bounced=80,
                deferred=10,
                complained=0,
                delivery_rate=0.10,
                bounce_rate=0.80,
                deferral_rate=0.10,
                complaint_rate=0.0,
            )
        ]
        anomalies = detect_anomalies(current, historical, threshold=3.5)
        # Not engagement_segment dimension — no baseline fallback
        assert len(anomalies) == 0
