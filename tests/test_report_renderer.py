"""Tests for the report renderer (JSON + markdown)."""

from datetime import UTC, datetime

from llm_pipeline.agents.report_models import (
    CompletenessRow,
    ComplianceRow,
    ConfirmedIssue,
    InvestigationNotes,
    InvestigationReport,
    Observation,
    SegmentHealthRow,
    StructuredReport,
    TrendRow,
    TrendSummary,
)
from llm_pipeline.agents.report_renderer import render_json, render_markdown


def _ts() -> datetime:
    return datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC)


def _make_report(**overrides) -> InvestigationReport:
    sr_defaults = {
        "run_id": "test-run",
        "ml_run_id": "ml-run",
        "generated_at": _ts(),
        "segment_health": [
            SegmentHealthRow(
                segment="VH", total=100, delivery_rate=0.95,
                bounce_rate=0.03, deferral_rate=0.02, complaint_rate=0.0,
                delivery_time_mean=1.5, delivery_time_p50=1.2,
                delivery_time_p95=3.0, delivery_time_p99=5.0,
                delivery_time_max=8.0,
            ),
        ],
        "confirmed_issues": [
            ConfirmedIssue(
                dimension="listid", dimension_value="VH",
                metric="bounce_rate", magnitude="bounce_rate=0.12",
                evidence_summary="Bounce spike observed",
            ),
        ],
        "trend_summary": TrendSummary(
            degrading_count=1, improving_count=0, stable_count=2,
            top_movers=[
                TrendRow(
                    dimension="listid", dimension_value="VH",
                    metric="delivery_rate", direction="degrading",
                    slope=-0.01, start_value=0.95, end_value=0.85,
                ),
            ],
        ),
        "data_completeness": [
            CompletenessRow(
                field_name="xmrid_account_id", dimension="listid",
                dimension_value="VH", zero_rate=0.15,
                total_records=1000, flagged=True,
            ),
        ],
        "compliance": [
            ComplianceRow(
                account_id="compliant", compliance_status="compliant", total=500,
            ),
        ],
        "observations": [],
    }
    notes_defaults = {
        "run_id": "test-run",
        "generated_at": _ts(),
        "hypotheses": ["[T1] Maybe X — Because Y"],
        "unexpected_observations": ["[T2] DISPROVEN: H is fine"],
        "process_notes": ["[plan] Created 2 topics"],
    }
    sr_defaults.update(overrides.get("structured", {}))
    notes_defaults.update(overrides.get("notes", {}))
    return InvestigationReport(
        structured=StructuredReport(**sr_defaults),
        notes=InvestigationNotes(**notes_defaults),
    )


class TestRenderJson:
    def test_json_round_trip(self):
        report = _make_report()
        json_str = render_json(report)
        parsed = InvestigationReport.model_validate_json(json_str)
        json_str_2 = render_json(parsed)
        assert json_str == json_str_2

    def test_empty_report_round_trip(self):
        report = _make_report(
            structured={
                "segment_health": [],
                "confirmed_issues": [],
                "trend_summary": TrendSummary(),
                "data_completeness": [],
                "compliance": [],
                "observations": [],
            },
            notes={
                "hypotheses": [],
                "unexpected_observations": [],
                "process_notes": [],
            },
        )
        json_str = render_json(report)
        parsed = InvestigationReport.model_validate_json(json_str)
        assert parsed.structured.segment_health == []
        assert parsed.notes.hypotheses == []


class TestRenderMarkdown:
    def test_contains_expected_sections(self):
        report = _make_report()
        md = render_markdown(report)
        assert "# Structured Investigation Report" in md
        assert "## Segment Health" in md
        assert "## Confirmed Issues" in md
        assert "## Trend Summary" in md
        assert "## Data Completeness" in md
        assert "## Compliance" in md
        assert "# Investigation Notes" in md
        assert "## Untested Hypotheses" in md
        assert "## Unexpected Observations" in md
        assert "## Process Notes" in md

    def test_segment_health_table(self):
        report = _make_report()
        md = render_markdown(report)
        assert "| VH |" in md
        assert "95.00%" in md

    def test_confirmed_issues_content(self):
        report = _make_report()
        md = render_markdown(report)
        assert "Bounce spike observed" in md
        assert "bounce_rate" in md

    def test_trend_table(self):
        report = _make_report()
        md = render_markdown(report)
        assert "Degrading: 1" in md
        assert "-0.010000" in md

    def test_completeness_flagged(self):
        report = _make_report()
        md = render_markdown(report)
        assert "1 flagged" in md
        assert "xmrid_account_id" in md

    def test_empty_report_all_sections_present(self):
        report = _make_report(
            structured={
                "segment_health": [],
                "confirmed_issues": [],
                "trend_summary": TrendSummary(),
                "data_completeness": [],
                "compliance": [],
                "observations": [],
            },
            notes={
                "hypotheses": [],
                "unexpected_observations": [],
                "process_notes": [],
            },
        )
        md = render_markdown(report)
        assert "## Segment Health" in md
        assert "No segment health data available." in md
        assert "No confirmed issues." in md
        assert "No compliance data." in md
        assert "No investigation notes." in md

    def test_observations_rendered_when_present(self):
        report = _make_report(
            structured={
                "observations": [
                    Observation(section="Segment Health", note="VH looks normal"),
                ],
            },
        )
        md = render_markdown(report)
        assert "## Observations" in md
        assert "VH looks normal" in md
