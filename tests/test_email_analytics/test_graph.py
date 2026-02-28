"""Tests for the email analytics LangGraph pipeline."""

import json
from unittest.mock import patch

import pytest

from llm_pipeline.email_analytics.graph import build_email_analytics_graph


_SAMPLE_EVENTS = [
    {
        "timestamp": "2025-01-01T10:00:00Z",
        "status": "delivered",
        "message": "250 OK",
        "sender": "sender@example.com",
        "recipient": "user1@gmail.com",
        "outmtaid_ip": "10.0.0.1",
        "sendid": "camp1",
    },
    {
        "timestamp": "2025-01-01T10:05:00Z",
        "status": "delivered",
        "message": "250 OK",
        "sender": "sender@example.com",
        "recipient": "user2@gmail.com",
        "outmtaid_ip": "10.0.0.1",
        "sendid": "camp1",
    },
    {
        "timestamp": "2025-01-01T10:10:00Z",
        "status": "bounced",
        "message": "550 5.1.1 User unknown",
        "sender": "sender@example.com",
        "recipient": "bad@yahoo.com",
        "outmtaid_ip": "10.0.0.1",
        "sendid": "camp1",
    },
]


@pytest.fixture
def sample_data_dir_concatenated(tmp_path):
    """Temp directory with concatenated JSON ({…}{…}{…})."""
    f = tmp_path / "events.json"
    f.write_text("".join(json.dumps(e) for e in _SAMPLE_EVENTS))
    return tmp_path


@pytest.fixture
def sample_data_dir_ndjson(tmp_path):
    """Temp directory with NDJSON (one object per line)."""
    f = tmp_path / "events.json"
    f.write_text("\n".join(json.dumps(e) for e in _SAMPLE_EVENTS) + "\n")
    return tmp_path


def _storage_patches():
    """Context managers to mock out Postgres storage."""
    return (
        patch("llm_pipeline.email_analytics.storage.get_engine"),
        patch("llm_pipeline.email_analytics.storage.init_db"),
        patch("llm_pipeline.email_analytics.storage.store_results"),
        patch(
            "llm_pipeline.email_analytics.storage.load_historical_aggregations",
            return_value=[],
        ),
    )


class TestEmailAnalyticsGraph:
    def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = build_email_analytics_graph()
        assert graph is not None

    def test_end_to_end_concatenated(self, sample_data_dir_concatenated):
        """Full pipeline run with concatenated JSON."""
        graph = build_email_analytics_graph()

        with _storage_patches()[0], _storage_patches()[1], _storage_patches()[2], _storage_patches()[3]:
            result = graph.invoke({
                "input_path": str(sample_data_dir_concatenated),
                "json_format": "concatenated",
            })

        report = result.get("report")
        assert report is not None
        assert report.files_processed == 1
        assert report.events_parsed == 3
        assert len(report.aggregations) > 0

    def test_end_to_end_ndjson(self, sample_data_dir_ndjson):
        """Full pipeline run with NDJSON."""
        graph = build_email_analytics_graph()

        with _storage_patches()[0], _storage_patches()[1], _storage_patches()[2], _storage_patches()[3]:
            result = graph.invoke({
                "input_path": str(sample_data_dir_ndjson),
                "json_format": "ndjson",
            })

        report = result.get("report")
        assert report is not None
        assert report.files_processed == 1
        assert report.events_parsed == 3
        assert len(report.aggregations) > 0

    def test_empty_directory(self, tmp_path):
        """Pipeline should handle empty directories gracefully."""
        graph = build_email_analytics_graph()

        with (
            patch("llm_pipeline.email_analytics.storage.init_db"),
            patch("llm_pipeline.email_analytics.storage.store_results"),
            patch(
                "llm_pipeline.email_analytics.storage.load_historical_aggregations",
                return_value=[],
            ),
        ):
            result = graph.invoke({"input_path": str(tmp_path)})

        report = result.get("report")
        assert report is not None
        assert report.events_parsed == 0
        assert report.aggregations == []
