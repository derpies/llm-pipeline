"""Tests for the Polars-based aggregation engine."""

import json
from datetime import UTC, datetime

from llm_pipeline.email_analytics.aggregator import (
    aggregate,
    aggregate_file,
    compute_data_completeness,
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
        assert "listid" in df.columns

    def test_basic_conversion(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        assert len(df) == 5
        assert "normalized_status" in df.columns
        assert "recipient_domain" in df.columns
        assert "listid" in df.columns
        assert "listid_type" in df.columns
        assert "engagement_segment" in df.columns
        assert "xmrid_account_id" in df.columns
        assert "compliance_status" in df.columns
        assert "pre_edge_latency" in df.columns
        assert "delivery_attempt_time" in df.columns


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

    def test_listid_dimension(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["listid"])

        listid_values = {b.dimension_value for b in buckets}
        assert "SEG_E_VH" in listid_values
        assert "SEG_E_H" in listid_values
        assert "SEG_E_M" in listid_values

    def test_engagement_segment_dimension(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["engagement_segment"])

        seg_values = {b.dimension_value for b in buckets}
        assert "VH" in seg_values
        assert "H" in seg_values
        assert "M" in seg_values

    def test_latency_fields(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["listid"])

        vh_buckets = [b for b in buckets if b.dimension_value == "SEG_E_VH"]
        assert len(vh_buckets) == 1
        # These events have injected_time and op_queue_time set
        assert vh_buckets[0].pre_edge_latency_mean is not None
        assert vh_buckets[0].delivery_time_mean is not None

    def test_latency_p99_and_max_fields(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        buckets = aggregate(df, window_hours=1, dimensions=["listid"])

        vh_buckets = [b for b in buckets if b.dimension_value == "SEG_E_VH"]
        assert len(vh_buckets) == 1
        b = vh_buckets[0]
        assert b.pre_edge_latency_p99 is not None
        assert b.pre_edge_latency_max is not None
        assert b.delivery_time_p99 is not None
        assert b.delivery_time_max is not None
        # max >= p99 >= p95
        assert b.delivery_time_max >= b.delivery_time_p99
        assert b.delivery_time_p99 >= b.delivery_time_p95

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


class TestComputeDataCompleteness:
    def test_completeness_basic(self, sample_events, sample_classifications):
        df = events_to_dataframe(sample_events, sample_classifications)
        results = compute_data_completeness(df, window_hours=1, dimensions=["listid"])
        assert len(results) > 0

        # Check that field_name is one of our tracked fields
        field_names = {r.field_name for r in results}
        assert "xmrid_account_id" in field_names

    def test_zero_cohort_completeness(self, zero_cohort_events):
        clf = [SmtpClassification(category=SmtpCategory.SUCCESS, confidence=0.9)]
        df = events_to_dataframe(zero_cohort_events, clf)
        results = compute_data_completeness(df, window_hours=1, dimensions=["listid"])

        # Zero-cohort events should have high zero rates for account/contact fields
        acct_results = [r for r in results if r.field_name == "xmrid_account_id"]
        assert len(acct_results) > 0
        # account_id is "0" → empty string in xmrid_account_id
        assert acct_results[0].zero_rate == 1.0

    def test_empty_dataframe(self):
        df = events_to_dataframe([], [])
        results = compute_data_completeness(df)
        assert results == []


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

    def test_latency_weighted_merge(self):
        buckets = [
            AggregationBucket(
                time_window=_ts(10), dimension="d", dimension_value="v",
                total=10, delivered=10, bounced=0, deferred=0, complained=0,
                delivery_rate=1.0, bounce_rate=0.0,
                deferral_rate=0.0, complaint_rate=0.0,
                pre_edge_latency_mean=2.0, delivery_time_mean=1.0,
            ),
            AggregationBucket(
                time_window=_ts(10), dimension="d", dimension_value="v",
                total=10, delivered=10, bounced=0, deferred=0, complained=0,
                delivery_rate=1.0, bounce_rate=0.0,
                deferral_rate=0.0, complaint_rate=0.0,
                pre_edge_latency_mean=4.0, delivery_time_mean=3.0,
            ),
        ]
        merged = merge_bucket_list(buckets)
        b = merged[0]
        assert b.pre_edge_latency_mean == 3.0  # weighted mean: (2*10 + 4*10) / 20
        assert b.delivery_time_mean == 2.0


class TestAggregateFile:
    def test_processes_file_end_to_end(self, tmp_path):
        events = [
            {
                "timestamp": "2025-01-01T10:00:00Z",
                "status": "delivered",
                "message": "250 OK",
                "recipient": "user@gmail.com",
                "outmtaid_ip": "10.0.0.1",
                "listid": "SEG_E_VH",
                "sendid": "SEG_E_VH260101",
            },
            {
                "timestamp": "2025-01-01T10:05:00Z",
                "status": "bounced",
                "message": "550 5.1.1 User unknown",
                "recipient": "bad@yahoo.com",
                "outmtaid_ip": "10.0.0.1",
                "listid": "SEG_E_H",
                "sendid": "SEG_E_H260101",
            },
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        result = aggregate_file(f, chunk_size=10, json_format="concatenated")
        assert result.event_count == 2
        assert len(result.buckets) > 0
        # Should have buckets for multiple dimensions
        dims = {b.dimension for b in result.buckets}
        assert "recipient_domain" in dims
        assert "listid" in dims

    def test_returns_correct_event_count(self, tmp_path):
        events = [
            {"timestamp": f"2025-01-01T10:{i:02d}:00Z", "status": "delivered", "message": "250 OK"}
            for i in range(15)
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        result = aggregate_file(f, chunk_size=4, json_format="concatenated")
        assert result.event_count == 15

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

        result = aggregate_file(
            f, chunk_size=2, dimensions=["recipient_domain"], json_format="concatenated"
        )
        assert result.event_count == 6
        gmail = [b for b in result.buckets if b.dimension_value == "gmail.com"]
        assert len(gmail) == 1
        assert gmail[0].total == 6

    def test_completeness_in_result(self, tmp_path):
        events = [
            {
                "timestamp": "2025-01-01T10:00:00Z",
                "status": "delivered",
                "message": "250 OK",
                "listid": "SEG_E_VH",
                "clicktrackingid": (
                    "0.266907.69781.478016969.1342.104.0"
                    ";1770154650;1755011403;1771487908;q;1"
                ),
            },
        ]
        f = tmp_path / "test.json"
        f.write_text("".join(json.dumps(e) for e in events))

        result = aggregate_file(f, chunk_size=10, json_format="concatenated")
        assert len(result.completeness) > 0
