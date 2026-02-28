"""Shared fixtures for email analytics tests."""

from datetime import UTC, datetime

import pytest

from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    DeliveryEvent,
    SmtpCategory,
    SmtpClassification,
)


def _ts(hour: int, day: int = 1) -> datetime:
    """Helper to create a UTC datetime for 2025-01-{day}T{hour}:00:00."""
    return datetime(2025, 1, day, hour, 0, 0, tzinfo=UTC)


@pytest.fixture
def sample_events() -> list[DeliveryEvent]:
    """A small set of delivery events for testing."""
    return [
        DeliveryEvent(
            timestamp=_ts(10),
            status="delivered",
            message="250 OK",
            sender="sender@example.com",
            recipient="user1@gmail.com",
            outmtaid_ip="10.0.0.1",
            sendid="camp1",
        ),
        DeliveryEvent(
            timestamp=_ts(10),
            status="delivered",
            message="250 OK",
            sender="sender@example.com",
            recipient="user2@gmail.com",
            outmtaid_ip="10.0.0.1",
            sendid="camp1",
        ),
        DeliveryEvent(
            timestamp=_ts(10),
            status="bounced",
            message="550 5.1.1 User unknown",
            sender="sender@example.com",
            recipient="bad@yahoo.com",
            outmtaid_ip="10.0.0.1",
            sendid="camp1",
        ),
        DeliveryEvent(
            timestamp=_ts(11),
            status="deferred",
            message="421 Too many connections from your IP",
            sender="sender@example.com",
            recipient="user3@yahoo.com",
            outmtaid_ip="10.0.0.2",
            sendid="camp2",
        ),
        DeliveryEvent(
            timestamp=_ts(11),
            status="delivered",
            message="250 Queued",
            sender="sender@example.com",
            recipient="user4@outlook.com",
            outmtaid_ip="10.0.0.2",
            sendid="camp2",
        ),
    ]


@pytest.fixture
def sample_classifications() -> list[SmtpClassification]:
    """Classifications matching sample_events."""
    return [
        SmtpClassification(category=SmtpCategory.SUCCESS, confidence=0.95, smtp_code="250"),
        SmtpClassification(category=SmtpCategory.SUCCESS, confidence=0.95, smtp_code="250"),
        SmtpClassification(
            category=SmtpCategory.RECIPIENT_UNKNOWN, confidence=0.95, smtp_code="550"
        ),
        SmtpClassification(
            category=SmtpCategory.THROTTLING, confidence=0.95, smtp_code="421"
        ),
        SmtpClassification(category=SmtpCategory.SUCCESS, confidence=0.80, smtp_code="250"),
    ]


@pytest.fixture
def historical_aggregations() -> list[AggregationBucket]:
    """Historical baseline aggregations (30 days of stable data)."""
    buckets = []
    for day in range(1, 31):
        buckets.append(
            AggregationBucket(
                time_window=_ts(10, day=day),
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
        )
    return buckets
