"""Tests for HTTP anomaly detection."""

from datetime import UTC, datetime

from llm_pipeline.http_analytics.anomaly import detect_anomalies
from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpAnomalyType,
)


def _ts(day: int = 1) -> datetime:
    return datetime(2026, 3, day, 10, 0, 0, tzinfo=UTC)


def _stable_history(
    n: int = 30,
    success_rate: float = 0.90,
    client_error_rate: float = 0.05,
    server_error_rate: float = 0.01,
    known_content_error_rate: float = 0.005,
    tts_p95: float = 1.0,
    dimension: str = "http_host",
    dimension_value: str = "app.ontraport.com",
) -> list[HttpAggregationBucket]:
    """Generate n days of stable historical HTTP aggregations."""
    return [
        HttpAggregationBucket(
            time_window=_ts(day=d),
            dimension=dimension,
            dimension_value=dimension_value,
            total=1000,
            status_2xx=int(success_rate * 1000),
            status_4xx=int(client_error_rate * 1000),
            status_5xx=int(server_error_rate * 1000),
            status_679=int(known_content_error_rate * 1000),
            success_rate=success_rate,
            client_error_rate=client_error_rate,
            server_error_rate=server_error_rate,
            known_content_error_rate=known_content_error_rate,
            tts_p95=tts_p95,
        )
        for d in range(1, n + 1)
    ]


class TestDetectAnomalies:
    def test_no_anomalies_when_matching(self, historical_http_buckets):
        """Current data matching historical baseline should produce no anomalies."""
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=31),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=900,
                status_4xx=50,
                status_5xx=10,
                status_679=5,
                success_rate=0.90,
                client_error_rate=0.05,
                server_error_rate=0.01,
                known_content_error_rate=0.005,
                tts_p95=1.0,
            )
        ]
        anomalies = detect_anomalies(
            current, historical_http_buckets, threshold=3.5
        )
        assert len(anomalies) == 0

    def test_success_rate_drop_detected(self):
        """A large success rate drop should trigger an anomaly."""
        history = _stable_history(success_rate=0.90)
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=31),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=200,
                status_4xx=500,
                status_5xx=300,
                success_rate=0.20,  # Huge drop from 0.90
                client_error_rate=0.50,
                server_error_rate=0.30,
                tts_p95=1.0,
            )
        ]
        anomalies = detect_anomalies(current, history, threshold=3.5)
        # Should detect success_rate drop AND error rate spikes
        assert len(anomalies) > 0
        types = {a.anomaly_type for a in anomalies}
        assert HttpAnomalyType.ERROR_RATE_SPIKE in types

    def test_latency_spike_detected(self):
        """A large TTS p95 spike should trigger a latency anomaly."""
        history = _stable_history(tts_p95=1.0)
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=31),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=900,
                success_rate=0.90,
                client_error_rate=0.05,
                server_error_rate=0.01,
                known_content_error_rate=0.005,
                tts_p95=50.0,  # Massive spike from 1.0
            )
        ]
        anomalies = detect_anomalies(current, history, threshold=3.5)
        latency_anomalies = [
            a for a in anomalies if a.anomaly_type == HttpAnomalyType.LATENCY_SPIKE
        ]
        assert len(latency_anomalies) > 0
        assert latency_anomalies[0].metric == "tts_p95"

    def test_status_679_spike_detected(self):
        """A spike in known_content_error_rate should trigger a 679 anomaly."""
        history = _stable_history(known_content_error_rate=0.005)
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=31),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=900,
                success_rate=0.90,
                client_error_rate=0.05,
                server_error_rate=0.01,
                known_content_error_rate=0.50,  # Huge spike from 0.005
                tts_p95=1.0,
            )
        ]
        anomalies = detect_anomalies(current, history, threshold=3.5)
        s679 = [a for a in anomalies if a.anomaly_type == HttpAnomalyType.STATUS_679_SPIKE]
        assert len(s679) > 0

    def test_insufficient_history_skipped(self):
        """With fewer than MIN_SAMPLE_SIZE historical points, skip detection."""
        history = _stable_history(n=3)  # Only 3, need 5
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=4),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=100,
                success_rate=0.10,  # Terrible, but not enough history
                client_error_rate=0.50,
                server_error_rate=0.40,
                tts_p95=1.0,
            )
        ]
        anomalies = detect_anomalies(current, history, threshold=3.5)
        assert len(anomalies) == 0

    def test_category_baseline_fallback(self):
        """When history is sparse, category baselines should be used for request_category dimension."""
        # Only 2 historical points — normally skipped, but request_category
        # dimension should fill with category baselines
        history = [
            HttpAggregationBucket(
                time_window=_ts(day=d),
                dimension="request_category",
                dimension_value="page_load",
                total=1000,
                success_rate=0.98,
                client_error_rate=0.01,
                server_error_rate=0.005,
                known_content_error_rate=0.005,
                tts_p95=2.0,
            )
            for d in range(1, 3)
        ]
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=3),
                dimension="request_category",
                dimension_value="page_load",
                total=1000,
                success_rate=0.10,  # Severe drop from baseline of 0.98
                client_error_rate=0.50,
                server_error_rate=0.40,
                tts_p95=2.0,
            )
        ]
        anomalies = detect_anomalies(current, history, threshold=3.5)
        # With baseline filling, should detect success_rate drop
        assert len(anomalies) > 0

    def test_anomaly_severity_levels(self):
        """Verify severity mapping based on z-score magnitude."""
        history = _stable_history(success_rate=0.90)
        current = [
            HttpAggregationBucket(
                time_window=_ts(day=31),
                dimension="http_host",
                dimension_value="app.ontraport.com",
                total=1000,
                status_2xx=100,
                success_rate=0.10,
                client_error_rate=0.05,
                server_error_rate=0.01,
                known_content_error_rate=0.005,
                tts_p95=1.0,
            )
        ]
        anomalies = detect_anomalies(current, history, threshold=3.5)
        assert len(anomalies) > 0
        # With such a big deviation, should be high or critical
        assert anomalies[0].severity in ("high", "critical")
