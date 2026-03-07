"""Tests for compare_runs CLI formatting (cli.py _format_comparison)."""

from datetime import UTC, datetime

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.cli import _format_comparison


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run(run_id, label="", findings=None, hypotheses=None, iteration_count=1):
    return {
        "run_id": run_id,
        "label": label,
        "started_at": datetime(2026, 3, 1, tzinfo=UTC),
        "completed_at": datetime(2026, 3, 1, 1, 0, tzinfo=UTC),
        "iteration_count": iteration_count,
        "findings": findings or [],
        "hypotheses": hypotheses or [],
        "checkpoint_digest": "",
    }


def _make_finding(topic, statement="test", status=FindingStatus.CONFIRMED):
    return Finding(
        topic_title=topic,
        statement=statement,
        status=status,
        evidence=[],
        created_at=datetime(2026, 3, 1, tzinfo=UTC),
        run_id="run-001",
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFormatComparison:
    def test_basic_output_structure(self):
        a = _make_run("run-a", label="baseline")
        b = _make_run("run-b", label="with-grounding")
        output = _format_comparison(a, b)

        assert "INVESTIGATION RUN COMPARISON" in output
        assert "baseline" in output
        assert "with-grounding" in output
        assert "FINDING COUNTS" in output
        assert "HYPOTHESIS COUNTS" in output

    def test_matched_findings(self):
        fa = _make_finding("VH delivery", "Drop in delivery rate", FindingStatus.CONFIRMED)
        fb = _make_finding("VH delivery", "Delivery rate dropped due to blocklist", FindingStatus.CONFIRMED)

        a = _make_run("run-a", findings=[fa])
        b = _make_run("run-b", findings=[fb])
        output = _format_comparison(a, b)

        assert "MATCHED FINDINGS" in output
        assert "VH delivery" in output
        assert "Drop in delivery rate" in output
        assert "blocklist" in output

    def test_unique_findings(self):
        fa = _make_finding("Only in A", "A-only finding")
        fb = _make_finding("Only in B", "B-only finding")

        a = _make_run("run-a", findings=[fa])
        b = _make_run("run-b", findings=[fb])
        output = _format_comparison(a, b)

        assert "FINDINGS UNIQUE TO A" in output
        assert "Only in A" in output
        assert "FINDINGS UNIQUE TO B" in output
        assert "Only in B" in output

    def test_empty_runs(self):
        a = _make_run("run-a")
        b = _make_run("run-b")
        output = _format_comparison(a, b)

        assert "A=  0  B=  0" in output

    def test_finding_counts_by_status(self):
        findings = [
            _make_finding("t1", status=FindingStatus.CONFIRMED),
            _make_finding("t2", status=FindingStatus.CONFIRMED),
            _make_finding("t3", status=FindingStatus.DISPROVEN),
        ]
        a = _make_run("run-a", findings=findings)
        b = _make_run("run-b")
        output = _format_comparison(a, b)

        assert "confirmed" in output
        assert "disproven" in output

    def test_no_label_shows_placeholder(self):
        a = _make_run("run-a")
        output = _format_comparison(a, _make_run("run-b"))
        assert "(no label)" in output
