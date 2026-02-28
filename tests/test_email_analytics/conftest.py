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
    """Helper: UTC datetime for 2025-01-{day}T{hour}:00:00."""
    return datetime(2025, 1, day, hour, 0, 0, tzinfo=UTC)


def _ctid(
    xmrid: str, last_active: int, contact_added: int,
    oqt: int, oqid: str, marketing: int,
) -> str:
    """Build a clicktrackingid string from components."""
    return f"{xmrid};{last_active};{contact_added};{oqt};{oqid};{marketing}"


@pytest.fixture
def sample_events() -> list[DeliveryEvent]:
    """A small set of delivery events with realistic composite fields."""
    oqt_10 = int(_ts(10).timestamp() - 3)
    oqt_10b = int(_ts(10).timestamp() - 4)
    oqt_10c = int(_ts(10).timestamp() - 2)
    oqt_11 = int(_ts(11).timestamp() - 10)
    oqt_11b = int(_ts(11).timestamp() - 2)

    xmrid_base = "0.266907.69781.478016969.1342.104.0"
    compliance = (
        "compliant-from:ex.com; compliant-mailfrom:mail.ex.com;"
    )
    return [
        DeliveryEvent(
            timestamp=_ts(10),
            status="delivered",
            message="250 OK",
            sender="sender@example.com",
            recipient="user1@gmail.com",
            outmtaid_ip="10.0.0.1",
            sendid="SEG_E_VH260101",
            listid="SEG_E_VH",
            injected_time=_ts(10).timestamp() - 1.5,
            clicktrackingid=_ctid(
                xmrid_base, 1770154650, 1755011403,
                oqt_10, "303835594.3662783", 1,
            ),
            headers={"x-op-mail-domains": compliance},
        ),
        DeliveryEvent(
            timestamp=_ts(10),
            status="delivered",
            message="250 OK",
            sender="sender@example.com",
            recipient="user2@gmail.com",
            outmtaid_ip="10.0.0.1",
            sendid="SEG_E_VH260101",
            listid="SEG_E_VH",
            injected_time=_ts(10).timestamp() - 2.0,
            clicktrackingid=_ctid(
                "0.266907.10001.478016970.1343.104.0",
                1770154650, 1755011403,
                oqt_10b, "303835595.1", 1,
            ),
            headers={"x-op-mail-domains": compliance},
        ),
        DeliveryEvent(
            timestamp=_ts(10),
            status="bounced",
            message="550 5.1.1 User unknown",
            sender="sender@example.com",
            recipient="bad@yahoo.com",
            outmtaid_ip="10.0.0.1",
            sendid="SEG_E_H260101",
            listid="SEG_E_H",
            injected_time=_ts(10).timestamp() - 1.0,
            clicktrackingid=_ctid(
                "0.300100.55555.478016971.1344.0.0",
                0, 1755011403,
                oqt_10c, "303835596.2", 0,
            ),
            headers={
                "x-op-mail-domains": (
                    "no-compliant-check: ontramail or opmailer"
                ),
            },
        ),
        DeliveryEvent(
            timestamp=_ts(11),
            status="deferred",
            message="421 Too many connections from your IP",
            sender="sender@example.com",
            recipient="user3@yahoo.com",
            outmtaid_ip="10.0.0.2",
            sendid="SEG_E_M260101",
            listid="SEG_E_M",
            injected_time=_ts(11).timestamp() - 5.0,
            clicktrackingid=_ctid(
                "0.300100.88888.478016972.1345.200.1",
                1770000000, 1755011403,
                oqt_11, "303835597.3", 1,
            ),
            headers={
                "x-op-mail-domains": (
                    "compliant-from:ex2.com;"
                    " compliant-mailfrom:mail.ex2.com;"
                ),
            },
        ),
        DeliveryEvent(
            timestamp=_ts(11),
            status="delivered",
            message="250 Queued",
            sender="sender@example.com",
            recipient="user4@outlook.com",
            outmtaid_ip="10.0.0.2",
            sendid="SEG_E_M260101",
            listid="SEG_E_M",
            injected_time=_ts(11).timestamp() - 0.8,
            clicktrackingid=_ctid(
                "0.266907.12345.478016973.1346.200.1",
                1770154650, 1755011403,
                oqt_11b, "303835598.4", 1,
            ),
            headers={"x-op-mail-domains": compliance},
        ),
    ]


@pytest.fixture
def zero_cohort_events() -> list[DeliveryEvent]:
    """Events with zero-value XMRID fields (system-generated)."""
    oqt = int(_ts(10).timestamp() - 2)
    return [
        DeliveryEvent(
            timestamp=_ts(10),
            status="delivered",
            message="250 OK",
            sender="sender@example.com",
            recipient="user@gmail.com",
            listid="SEG_E_UK",
            clicktrackingid=_ctid(
                "0.0.0.0.0.0.0", 0, 0, oqt, "q", 0,
            ),
        ),
    ]


@pytest.fixture
def sample_classifications() -> list[SmtpClassification]:
    """Classifications matching sample_events."""
    return [
        SmtpClassification(
            category=SmtpCategory.SUCCESS,
            confidence=0.95, smtp_code="250",
        ),
        SmtpClassification(
            category=SmtpCategory.SUCCESS,
            confidence=0.95, smtp_code="250",
        ),
        SmtpClassification(
            category=SmtpCategory.RECIPIENT_UNKNOWN,
            confidence=0.95, smtp_code="550",
        ),
        SmtpClassification(
            category=SmtpCategory.THROTTLING,
            confidence=0.95, smtp_code="421",
        ),
        SmtpClassification(
            category=SmtpCategory.SUCCESS,
            confidence=0.80, smtp_code="250",
        ),
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
