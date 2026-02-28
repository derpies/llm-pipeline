"""Tests for the email analytics LangGraph pipeline."""

import json
from unittest.mock import patch

import pytest

from llm_pipeline.email_analytics.graph import (
    build_email_analytics_graph,
)

_CTID_1 = (
    "0.266907.69781.478016969.1342.104.0"
    ";1770154650;1755011403;1735725600;q;1"
)
_CTID_2 = (
    "0.266907.10001.478016970.1343.104.0"
    ";1770154650;1755011403;1735725600;q;1"
)
_CTID_3 = (
    "0.300100.55555.478016971.1344.0.0"
    ";0;1755011403;1735725600;q;0"
)
_COMPLIANCE = (
    "compliant-from:ex.com; compliant-mailfrom:mail.ex.com;"
)

_SAMPLE_EVENTS = [
    {
        "timestamp": "2025-01-01T10:00:00Z",
        "status": "delivered",
        "message": "250 OK",
        "sender": "sender@example.com",
        "recipient": "user1@gmail.com",
        "outmtaid_ip": "10.0.0.1",
        "sendid": "SEG_E_VH260101",
        "listid": "SEG_E_VH",
        "clicktrackingid": _CTID_1,
        "headers": {"x-op-mail-domains": _COMPLIANCE},
    },
    {
        "timestamp": "2025-01-01T10:05:00Z",
        "status": "delivered",
        "message": "250 OK",
        "sender": "sender@example.com",
        "recipient": "user2@gmail.com",
        "outmtaid_ip": "10.0.0.1",
        "sendid": "SEG_E_VH260101",
        "listid": "SEG_E_VH",
        "clicktrackingid": _CTID_2,
        "headers": {"x-op-mail-domains": _COMPLIANCE},
    },
    {
        "timestamp": "2025-01-01T10:10:00Z",
        "status": "bounced",
        "message": "550 5.1.1 User unknown",
        "sender": "sender@example.com",
        "recipient": "bad@yahoo.com",
        "outmtaid_ip": "10.0.0.1",
        "sendid": "SEG_E_H260101",
        "listid": "SEG_E_H",
        "clicktrackingid": _CTID_3,
        "headers": {
            "x-op-mail-domains": (
                "no-compliant-check: ontramail or opmailer"
            ),
        },
    },
]


@pytest.fixture
def sample_data_dir_concatenated(tmp_path):
    """Temp dir with concatenated JSON ({...}{...}{...})."""
    f = tmp_path / "events.json"
    f.write_text("".join(json.dumps(e) for e in _SAMPLE_EVENTS))
    return tmp_path


@pytest.fixture
def sample_data_dir_ndjson(tmp_path):
    """Temp dir with NDJSON (one object per line)."""
    f = tmp_path / "events.json"
    lines = "\n".join(json.dumps(e) for e in _SAMPLE_EVENTS)
    f.write_text(lines + "\n")
    return tmp_path


def _mock_storage():
    """Combined context manager to mock out Postgres storage."""
    p0 = patch("llm_pipeline.email_analytics.storage.get_engine")
    p1 = patch("llm_pipeline.email_analytics.storage.init_db")
    p2 = patch(
        "llm_pipeline.email_analytics.storage.store_results",
    )
    p3 = patch(
        "llm_pipeline.email_analytics.storage"
        ".load_historical_aggregations",
        return_value=[],
    )
    return p0, p1, p2, p3


class TestEmailAnalyticsGraph:
    def test_graph_compiles(self):
        """Graph should compile without errors."""
        graph = build_email_analytics_graph()
        assert graph is not None

    def test_end_to_end_concatenated(
        self, sample_data_dir_concatenated,
    ):
        """Full pipeline run with concatenated JSON."""
        graph = build_email_analytics_graph()
        p0, p1, p2, p3 = _mock_storage()

        with p0, p1, p2, p3:
            result = graph.invoke({
                "input_path": str(sample_data_dir_concatenated),
                "json_format": "concatenated",
            })

        report = result.get("report")
        assert report is not None
        assert report.files_processed == 1
        assert report.events_parsed == 3
        assert len(report.aggregations) > 0

        # Verify new dimensions are present
        dims = {a.dimension for a in report.aggregations}
        assert "listid" in dims
        assert "engagement_segment" in dims

        # Verify completeness data is produced
        assert len(report.completeness) > 0

    def test_end_to_end_ndjson(self, sample_data_dir_ndjson):
        """Full pipeline run with NDJSON."""
        graph = build_email_analytics_graph()
        p0, p1, p2, p3 = _mock_storage()

        with p0, p1, p2, p3:
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
            patch(
                "llm_pipeline.email_analytics.storage.init_db",
            ),
            patch(
                "llm_pipeline.email_analytics.storage"
                ".store_results",
            ),
            patch(
                "llm_pipeline.email_analytics.storage"
                ".load_historical_aggregations",
                return_value=[],
            ),
        ):
            result = graph.invoke(
                {"input_path": str(tmp_path)},
            )

        report = result.get("report")
        assert report is not None
        assert report.events_parsed == 0
        assert report.aggregations == []
        assert report.completeness == []
