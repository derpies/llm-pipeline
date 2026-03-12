"""Tests for the Polars-based HTTP aggregation engine."""

from datetime import UTC, datetime

from llm_pipeline.http_analytics.aggregator import (
    aggregate,
    compute_data_completeness,
    events_to_dataframe,
    merge_bucket_list,
    merge_completeness,
)
from llm_pipeline.http_analytics.models import (
    HttpAggregationBucket,
    HttpDataCompleteness,
)


def _ts(minute: int = 0) -> datetime:
    return datetime(2026, 3, 1, 10, minute, 0, tzinfo=UTC)


class TestEventsToDataframe:
    def test_empty_events(self):
        df = events_to_dataframe([])
        assert df.is_empty()
        assert "event_time" in df.columns
        assert "http_host" in df.columns
        assert "request_category" in df.columns

    def test_basic_conversion(self, sample_events):
        df = events_to_dataframe(sample_events)
        assert len(df) == 7
        assert "status_class" in df.columns
        assert "ua_category" in df.columns
        assert "tts_seconds" in df.columns
        assert "size_bytes" in df.columns


class TestAggregate:
    def test_empty_dataframe(self):
        df = events_to_dataframe([])
        buckets = aggregate(df)
        assert buckets == []

    def test_produces_buckets(self, sample_events):
        df = events_to_dataframe(sample_events)
        buckets = aggregate(df, window_minutes=1, dimensions=["request_category"])
        assert len(buckets) > 0

    def test_rate_computation(self, sample_events):
        df = events_to_dataframe(sample_events)
        buckets = aggregate(df, window_minutes=5, dimensions=["http_host"])
        # All events have the same host
        assert len(buckets) >= 1
        b = buckets[0]
        assert b.total > 0
        assert 0 <= b.success_rate <= 1
        assert 0 <= b.client_error_rate <= 1
        assert 0 <= b.server_error_rate <= 1

    def test_status_679_counted(self, sample_events):
        df = events_to_dataframe(sample_events)
        buckets = aggregate(df, window_minutes=5, dimensions=["http_host"])
        total_679 = sum(b.status_679 for b in buckets)
        assert total_679 == 1  # One 679 event in sample_events

    def test_tts_latency_populated(self, sample_events):
        df = events_to_dataframe(sample_events)
        buckets = aggregate(df, window_minutes=5, dimensions=["http_host"])
        b = buckets[0]
        assert b.tts_p50 is not None
        assert b.tts_p95 is not None
        assert b.tts_mean is not None
        assert b.tts_mean > 0

    def test_multiple_dimensions(self, sample_events):
        df = events_to_dataframe(sample_events)
        buckets = aggregate(
            df, window_minutes=5,
            dimensions=["request_category", "status_class"],
        )
        dims = {b.dimension for b in buckets}
        assert "request_category" in dims
        assert "status_class" in dims

    def test_completeness_counts(self, sample_events):
        df = events_to_dataframe(sample_events)
        buckets = aggregate(df, window_minutes=5, dimensions=["http_host"])
        # One event has empty useragent, one has empty upstream
        total_empty_ua = sum(b.empty_ua_count for b in buckets)
        assert total_empty_ua == 1
        total_empty_up = sum(b.empty_upstream_count for b in buckets)
        assert total_empty_up == 1


class TestComputeDataCompleteness:
    def test_empty_dataframe(self):
        df = events_to_dataframe([])
        result = compute_data_completeness(df)
        assert result == []

    def test_empty_rates(self, sample_events):
        df = events_to_dataframe(sample_events)
        results = compute_data_completeness(
            df, window_minutes=5, dimensions=["http_host"]
        )
        assert len(results) > 0
        # Find the useragent completeness entry
        ua_entries = [r for r in results if r.field_name == "useragent"]
        assert len(ua_entries) > 0
        total_empty = sum(r.empty_count for r in ua_entries)
        assert total_empty == 1  # One empty UA in sample data


class TestMergeBucketList:
    def test_empty(self):
        assert merge_bucket_list([]) == []

    def test_no_duplicates(self):
        b = HttpAggregationBucket(
            time_window=_ts(0), dimension="http_host",
            dimension_value="a.com", total=10, status_2xx=8,
            status_4xx=2, success_rate=0.8, client_error_rate=0.2,
            tts_mean=0.5,
        )
        merged = merge_bucket_list([b])
        assert len(merged) == 1
        assert merged[0].total == 10

    def test_merges_same_key(self):
        b1 = HttpAggregationBucket(
            time_window=_ts(0), dimension="http_host",
            dimension_value="a.com", total=10, status_2xx=8,
            status_4xx=2, success_rate=0.8, client_error_rate=0.2,
            tts_mean=0.5, total_bytes=100,
        )
        b2 = HttpAggregationBucket(
            time_window=_ts(0), dimension="http_host",
            dimension_value="a.com", total=10, status_2xx=6,
            status_4xx=4, success_rate=0.6, client_error_rate=0.4,
            tts_mean=1.0, total_bytes=200,
        )
        merged = merge_bucket_list([b1, b2])
        assert len(merged) == 1
        m = merged[0]
        assert m.total == 20
        assert m.status_2xx == 14
        assert m.status_4xx == 6
        assert m.success_rate == 14 / 20
        assert m.client_error_rate == 6 / 20
        assert m.total_bytes == 300
        # Weighted mean TTS: (0.5*10 + 1.0*10) / 20 = 0.75
        assert abs(m.tts_mean - 0.75) < 0.001

    def test_different_keys_kept(self):
        b1 = HttpAggregationBucket(
            time_window=_ts(0), dimension="http_host",
            dimension_value="a.com", total=10, status_2xx=10,
            success_rate=1.0,
        )
        b2 = HttpAggregationBucket(
            time_window=_ts(0), dimension="http_host",
            dimension_value="b.com", total=5, status_2xx=5,
            success_rate=1.0,
        )
        merged = merge_bucket_list([b1, b2])
        assert len(merged) == 2


class TestMergeCompleteness:
    def test_empty(self):
        assert merge_completeness([]) == []

    def test_merges_same_key(self):
        c1 = HttpDataCompleteness(
            time_window=_ts(0), dimension="http_host",
            dimension_value="a.com", total_records=100,
            field_name="useragent", empty_count=10, empty_rate=0.1,
        )
        c2 = HttpDataCompleteness(
            time_window=_ts(0), dimension="http_host",
            dimension_value="a.com", total_records=100,
            field_name="useragent", empty_count=20, empty_rate=0.2,
        )
        merged = merge_completeness([c1, c2])
        assert len(merged) == 1
        assert merged[0].total_records == 200
        assert merged[0].empty_count == 30
        assert abs(merged[0].empty_rate - 0.15) < 0.001
