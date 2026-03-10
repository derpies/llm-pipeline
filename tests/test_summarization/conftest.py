"""Shared fixtures for summarization tests."""

from datetime import UTC, datetime

import pytest

from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnalysisReport,
    AnomalyFinding,
    AnomalyType,
    TrendDirection,
    TrendFinding,
)


def _ts(hour: int, day: int = 11) -> datetime:
    """Helper to create a UTC datetime for 2026-02-{day}T{hour}:00:00."""
    return datetime(2026, 2, day, hour, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_report() -> AnalysisReport:
    """A realistic AnalysisReport for testing summarization."""
    buckets = []
    # gmail.com — high volume
    for hour in range(0, 24):
        buckets.append(
            AggregationBucket(
                time_window=_ts(hour),
                dimension="recipient_domain",
                dimension_value="gmail.com",
                total=500,
                delivered=475,
                bounced=15,
                deferred=8,
                complained=2,
                delivery_rate=0.95,
                bounce_rate=0.03,
                deferral_rate=0.016,
                complaint_rate=0.004,
            )
        )
    # yahoo.com — medium volume
    for hour in range(0, 24):
        buckets.append(
            AggregationBucket(
                time_window=_ts(hour),
                dimension="recipient_domain",
                dimension_value="yahoo.com",
                total=200,
                delivered=180,
                bounced=10,
                deferred=8,
                complained=2,
                delivery_rate=0.90,
                bounce_rate=0.05,
                deferral_rate=0.04,
                complaint_rate=0.01,
            )
        )
    # comcast.net — lower volume, has anomaly
    for hour in range(0, 12):
        buckets.append(
            AggregationBucket(
                time_window=_ts(hour),
                dimension="recipient_domain",
                dimension_value="comcast.net",
                total=50,
                delivered=47,
                bounced=1,
                deferred=2,
                complained=0,
                delivery_rate=0.94,
                bounce_rate=0.02,
                deferral_rate=0.04,
                complaint_rate=0.0,
            )
        )
    # comcast.net spike hours
    for hour in range(12, 24):
        buckets.append(
            AggregationBucket(
                time_window=_ts(hour),
                dimension="recipient_domain",
                dimension_value="comcast.net",
                total=50,
                delivered=40,
                bounced=8,
                deferred=2,
                complained=0,
                delivery_rate=0.80,
                bounce_rate=0.16,
                deferral_rate=0.04,
                complaint_rate=0.0,
            )
        )

    anomalies = [
        AnomalyFinding(
            anomaly_type=AnomalyType.BOUNCE_SPIKE,
            dimension="recipient_domain",
            dimension_value="comcast.net",
            metric="bounce_rate",
            current_value=0.16,
            baseline_mean=0.02,
            z_score=4.27,
            severity="high",
        ),
        AnomalyFinding(
            anomaly_type=AnomalyType.RATE_DROP,
            dimension="recipient_domain",
            dimension_value="yahoo.com",
            metric="delivery_rate",
            current_value=0.85,
            baseline_mean=0.94,
            z_score=-3.8,
            severity="medium",
        ),
        AnomalyFinding(
            anomaly_type=AnomalyType.DEFERRAL_SPIKE,
            dimension="recipient_domain",
            dimension_value="yahoo.com",
            metric="deferral_rate",
            current_value=0.06,
            baseline_mean=0.02,
            z_score=3.5,
            severity="medium",
        ),
        AnomalyFinding(
            anomaly_type=AnomalyType.COMPLAINT_SPIKE,
            dimension="recipient_domain",
            dimension_value="gmail.com",
            metric="complaint_rate",
            current_value=0.008,
            baseline_mean=0.002,
            z_score=3.6,
            severity="medium",
        ),
        AnomalyFinding(
            anomaly_type=AnomalyType.BOUNCE_SPIKE,
            dimension="recipient_domain",
            dimension_value="gmail.com",
            metric="bounce_rate",
            current_value=0.04,
            baseline_mean=0.015,
            z_score=3.55,
            severity="low",
        ),
    ]

    trends = [
        TrendFinding(
            direction=TrendDirection.DEGRADING,
            dimension="recipient_domain",
            dimension_value="comcast.net",
            metric="bounce_rate",
            slope=0.012,
            r_squared=0.85,
            num_points=24,
            start_value=0.02,
            end_value=0.16,
        ),
        TrendFinding(
            direction=TrendDirection.IMPROVING,
            dimension="recipient_domain",
            dimension_value="gmail.com",
            metric="delivery_rate",
            slope=0.001,
            r_squared=0.62,
            num_points=24,
            start_value=0.94,
            end_value=0.96,
        ),
        TrendFinding(
            direction=TrendDirection.DEGRADING,
            dimension="recipient_domain",
            dimension_value="yahoo.com",
            metric="deferral_rate",
            slope=0.002,
            r_squared=0.72,
            num_points=24,
            start_value=0.02,
            end_value=0.06,
        ),
    ]

    return AnalysisReport(
        run_id="test-run-001",
        started_at=_ts(0),
        completed_at=_ts(23),
        files_processed=1,
        events_parsed=24000,
        aggregations=buckets,
        anomalies=anomalies,
        trends=trends,
    )
