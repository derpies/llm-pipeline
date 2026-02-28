"""Tests for summarization serializers — pure function tests."""

from llm_pipeline.summarization.serializers import (
    filter_buckets,
    get_top_dimensions,
    serialize_anomaly_context,
    serialize_dimension_context,
    serialize_executive_digest,
    serialize_trend_context,
)


class TestFilterBuckets:
    def test_filters_correctly(self, sample_report):
        gmail_buckets = filter_buckets(
            sample_report.aggregations, "recipient_domain", "gmail.com"
        )
        assert len(gmail_buckets) == 24
        assert all(b.dimension_value == "gmail.com" for b in gmail_buckets)

    def test_empty_for_nonexistent(self, sample_report):
        result = filter_buckets(
            sample_report.aggregations, "recipient_domain", "nonexistent.com"
        )
        assert result == []


class TestGetTopDimensions:
    def test_returns_sorted_by_volume(self, sample_report):
        top = get_top_dimensions(sample_report, top_n=3)
        assert len(top) == 3
        # gmail has highest volume (500*24=12000), yahoo next (200*24=4800), comcast (50*24=1200)
        assert top[0] == ("recipient_domain", "gmail.com")
        assert top[1] == ("recipient_domain", "yahoo.com")
        assert top[2] == ("recipient_domain", "comcast.net")

    def test_respects_top_n(self, sample_report):
        top = get_top_dimensions(sample_report, top_n=1)
        assert len(top) == 1


class TestSerializeExecutiveDigest:
    def test_contains_volume_info(self, sample_report):
        result = serialize_executive_digest(sample_report)
        assert "VOLUME OVERVIEW" in result
        assert "gmail.com" in result

    def test_contains_anomalies(self, sample_report):
        result = serialize_executive_digest(sample_report)
        assert "ANOMALIES" in result
        assert "comcast.net" in result
        assert "bounce_rate" in result

    def test_contains_trends(self, sample_report):
        result = serialize_executive_digest(sample_report)
        assert "TRENDS" in result
        assert "degrading" in result


class TestSerializeAnomalyContext:
    def test_contains_anomaly_details(self, sample_report):
        anomaly = sample_report.anomalies[0]  # comcast bounce spike
        result = serialize_anomaly_context(anomaly, sample_report.aggregations)
        assert "bounce_spike" in result
        assert "comcast.net" in result
        assert "4.27" in result
        assert "RELATED AGGREGATION DATA" in result

    def test_includes_related_buckets(self, sample_report):
        anomaly = sample_report.anomalies[0]
        result = serialize_anomaly_context(anomaly, sample_report.aggregations)
        # Should have comcast.net bucket data lines
        assert "comcast.net" in result
        assert "delivery=" in result


class TestSerializeTrendContext:
    def test_contains_trend_details(self, sample_report):
        trend = sample_report.trends[0]  # comcast bounce degrading
        result = serialize_trend_context(trend, sample_report.aggregations)
        assert "degrading" in result
        assert "comcast.net" in result
        assert "0.85" in result  # r_squared
        assert "TIME-SERIES DATA" in result


class TestSerializeDimensionContext:
    def test_contains_dimension_overview(self, sample_report):
        result = serialize_dimension_context(
            "recipient_domain",
            "gmail.com",
            sample_report.aggregations,
            sample_report.anomalies,
            sample_report.trends,
        )
        assert "gmail.com" in result
        assert "DIMENSION" in result

    def test_includes_anomalies_for_dimension(self, sample_report):
        result = serialize_dimension_context(
            "recipient_domain",
            "gmail.com",
            sample_report.aggregations,
            sample_report.anomalies,
            sample_report.trends,
        )
        assert "ANOMALIES" in result
        assert "complaint_rate" in result

    def test_includes_trends_for_dimension(self, sample_report):
        result = serialize_dimension_context(
            "recipient_domain",
            "gmail.com",
            sample_report.aggregations,
            sample_report.anomalies,
            sample_report.trends,
        )
        assert "TRENDS" in result
        assert "improving" in result

    def test_dimension_with_no_findings(self, sample_report):
        """A dimension with buckets but no anomalies/trends should still work."""
        result = serialize_dimension_context(
            "recipient_domain",
            "comcast.net",
            sample_report.aggregations,
            [],  # no anomalies
            [],  # no trends
        )
        assert "comcast.net" in result
        assert "AGGREGATION DATA" in result
        assert "ANOMALIES" not in result
