"""Tests for the Polars-based aggregation engine."""

import json
from datetime import UTC, datetime

from llm_pipeline.email_analytics.aggregator import (
    aggregate,
    aggregate_file,
    events_to_dataframe,
    merge_bucket_list,
)
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    DeliveryEvent,
    SmtpCategory,
    SmtpClassification,
)


def _ts(hour: int) -> datetime:
    return datetime(2025, 1, 1, hour, 0, 0, tzinfo=UTC)


class TestEventsToDataframe:
    def test_empty_events(self):
        df = events_to_dataframe([], [])
        assert df.is_empty()
        assert "timestamp" in df.columns

    def test_basic_conversion(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        assert len(df) == 5
        assert "normalized_status" in df.columns
        assert "recipient_domain" in df.columns


class TestAggregate:
    def test_empty_dataframe(self):
        df = events_to_dataframe([], [])
        buckets = aggregate(df)
        assert buckets == []

    def test_rate_computation(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["recipient_domain"])
        assert len(buckets) > 0

        # Find the gmail.com bucket at hour 10 (2 delivered out of 2)
        gmail_buckets = [b for b in buckets if b.dimension_value == "gmail.com"]
        assert len(gmail_buckets) == 1
        assert gmail_buckets[0].total == 2
        assert gmail_buckets[0].delivered == 2
        assert gmail_buckets[0].delivery_rate == 1.0

    def test_bounce_rate(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["recipient_domain"])

        yahoo_buckets = [b for b in buckets if b.dimension_value == "yahoo.com"]
        assert len(yahoo_buckets) > 0
        # yahoo.com has 1 bounce + 1 deferral across 2 time windows
        yahoo_h10 = [b for b in yahoo_buckets if b.time_window.hour == 10]
        if yahoo_h10:
            assert yahoo_h10[0].bounce_rate == 1.0  # 1 bounce out of 1

    def test_dimensional_slicing(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["outmtaid_ip"])

        ip_values = {b.dimension_value for b in buckets}
        assert "10.0.0.1" in ip_values
        assert "10.0.0.2" in ip_values

    def test_time_window_truncation(self):
        events = [
            DeliveryEvent(
                timestamp=datetime(2025, 1, 1, 10, 15, tzinfo=UTC),
                status="delivered",
            ),
            DeliveryEvent(
                timestamp=datetime(2025, 1, 1, 10, 45, tzinfo=UTC),
                status="delivered",
            ),
            DeliveryEvent(
                timestamp=datetime(2025, 1, 1, 11, 30, tzinfo=UTC),
                status="bounced",
            ),
        ]
        clf = [
            SmtpClassification(category=SmtpCategory.SUCCESS, confidence=0.9),
            SmtpClassification(category=SmtpCategory.SUCCESS, confidence=0.9),
            SmtpClassification(category=SmtpCategory.RECIPIENT_UNKNOWN, confidence=0.9),
        ]
        df = events_to_dataframe(events, clf)
        buckets = aggregate(df, window_hours=1, dimensions=["recipient_domain"])

        # Events at 10:15 and 10:45 should fall in the same 1-hour window
        windows = {b.time_window for b in buckets}
        assert len(windows) == 2  # hour 10 and hour 11


class TestMergeBucketList:
    def test_empty_input(self):
        assert merge_bucket_list([]) == []

    def test_non_overlapping_keys_pass_through(self):
        buckets = [
            AggregationBucket(
                time_window=_ts(10), dimension="recipient_domain",
                dimension_value="gmail.com", total=10, delivered=8,
                bounced=1, deferred=1, complained=0,
                delivery_rate=0.8, bounce_rate=0.1,
                deferral_rate=0.1, complaint_rate=0.0,
            ),
            AggregationBucket(
                time_window=_ts(10), dimension="recipient_domain",
                dimension_value="yahoo.com", total=5, delivered=4,
                bounced=1, deferred=0, complained=0,
                delivery_rate=0.8, bounce_rate=0.2,
                deferral_rate=0.0, complaint_rate=0.0,
            ),
        ]
        merged = merge_bucket_list(buckets)
        assert len(merged) == 2

    def test_overlapping_keys_sum_correctly(self):
        buckets = [
            AggregationBucket(
                time_window=_ts(10), dimension="recipient_domain",
                dimension_value="gmail.com", total=10, delivered=8,
                bounced=1, deferred=1, complained=0,
                delivery_rate=0.8, bounce_rate=0.1,
                deferral_rate=0.1, complaint_rate=0.0,
            ),
            AggregationBucket(
                time_window=_ts(10), dimension="recipient_domain",
                dimension_value="gmail.com", total=20, delivered=18,
                bounced=1, deferred=1, complained=0,
                delivery_rate=0.9, bounce_rate=0.05,
                deferral_rate=0.05, complaint_rate=0.0,
            ),
        ]
        merged = merge_bucket_list(buckets)
        assert len(merged) == 1
        b = merged[0]
        assert b.total == 30
        assert b.delivered == 26
        assert b.bounced == 2
        assert b.deferred == 2
        assert b.complained == 0

    def test_rates_recomputed_from_new_totals(self):
        buckets = [
            AggregationBucket(
                time_window=_ts(10), dimension="d", dimension_value="v",
                total=10, delivered=10, bounced=0, deferred=0, complained=0,
                delivery_rate=1.0, bounce_rate=0.0,
                deferral_rate=0.0, complaint_rate=0.0,
            ),
            AggregationBucket(
                time_window=_ts(10), dimension="d", dimension_value="v",
                total=10, delivered=0, bounced=10, deferred=0, complained=0,
                delivery_rate=0.0, bounce_rate=1.0,
                deferral_rate=0.0, complaint_rate=0.0,
            ),
        ]
        merged = merge_bucket_list(buckets)
        assert len(merged) == 1
        b = merged[0]
        assert b.total == 20
        assert b.delivered == 10
        assert b.bounced == 10
        assert b.delivery_rate == 0.5
        assert b.bounce_rate == 0.5


class TestAggregateFile:
    def test_processes_file_end_to_end(self, tmp_path):
        events = [
            {
                "timestamp": "2025-01-01T10:00:00Z",
                "status": "delivered",
                "message": "250 OK",
                "recipient": "user@gmail.com",
                "outmtaid_ip": "10.0.0.1",
                "sendid": "c1",
            },
            {
                "timestamp": "2025-01-01T10:05:00Z",
                "status": "bounced",
                "message": "550 5.1.1 User unknown",
                "recipient": "bad@yahoo.com",
                "outmtaid_ip": "10.0.0.1",
                "sendid": "c1",
            },
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        buckets, count = aggregate_file(f, chunk_size=10, json_format="concatenated")
        assert count == 2
        assert len(buckets) > 0
        # Should have buckets for multiple dimensions
        dims = {b.dimension for b in buckets}
        assert "recipient_domain" in dims

    def test_returns_correct_event_count(self, tmp_path):
        events = [
            {"timestamp": f"2025-01-01T10:{i:02d}:00Z", "status": "delivered", "message": "250 OK"}
            for i in range(15)
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        _, count = aggregate_file(f, chunk_size=4, json_format="concatenated")
        assert count == 15

    def test_multi_chunk_merge(self, tmp_path):
        """Buckets from multiple chunks with same keys should merge."""
        events = [
            {
                "timestamp": "2025-01-01T10:00:00Z",
                "status": "delivered",
                "message": "250 OK",
                "recipient": "user@gmail.com",
            }
            for _ in range(6)
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        buckets, count = aggregate_file(
            f, chunk_size=2, dimensions=["recipient_domain"], json_format="concatenated"
        )
        assert count == 6
        gmail = [b for b in buckets if b.dimension_value == "gmail.com"]
        assert len(gmail) == 1
        assert gmail[0].total == 6
