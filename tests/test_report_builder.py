"""Tests for the deterministic report builder."""

from datetime import UTC, datetime

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.agents.report_builder import (
    assemble_full_report,
    assemble_structured_report,
    build_compliance,
    build_confirmed_issues,
    build_data_completeness,
    build_segment_health,
    build_trend_summary,
)
from llm_pipeline.email_analytics.models import (
    AggregationBucket,
    AnalysisReport,
    DataCompleteness,
    TrendDirection,
    TrendFinding,
)


def _ts(hour: int = 10, day: int = 1) -> datetime:
    return datetime(2025, 1, day, hour, 0, 0, tzinfo=UTC)


def _make_seg_bucket(segment: str, **overrides) -> AggregationBucket:
    defaults = {
        "time_window": _ts(10),
        "dimension": "engagement_segment",
        "dimension_value": segment,
        "total": 100,
        "delivered": 95,
        "bounced": 3,
        "deferred": 2,
        "complained": 0,
        "delivery_rate": 0.95,
        "bounce_rate": 0.03,
        "deferral_rate": 0.02,
        "complaint_rate": 0.0,
        "delivery_time_mean": 1.5,
        "delivery_time_p50": 1.2,
        "delivery_time_p95": 3.0,
        "delivery_time_p99": 5.0,
        "delivery_time_max": 8.0,
        "pre_edge_latency_mean": 0.5,
        "pre_edge_latency_p50": 0.4,
        "pre_edge_latency_p95": 1.0,
        "pre_edge_latency_p99": 2.0,
        "pre_edge_latency_max": 3.0,
    }
    defaults.update(overrides)
    return AggregationBucket(**defaults)


class TestBuildSegmentHealth:
    def test_basic_segment_health(self):
        buckets = [_make_seg_bucket("VH"), _make_seg_bucket("H", total=50, delivered=45)]
        rows = build_segment_health(buckets)
        assert len(rows) == 2
        assert rows[0].segment == "H"  # sorted alphabetically
        assert rows[1].segment == "VH"
        assert rows[1].total == 100
        assert rows[1].delivery_time_p99 == 5.0

    def test_uses_most_recent_time_window(self):
        old = _make_seg_bucket("VH", time_window=_ts(10, day=1), total=50)
        new = _make_seg_bucket("VH", time_window=_ts(10, day=2), total=200)
        rows = build_segment_health([old, new])
        assert len(rows) == 1
        assert rows[0].total == 200

    def test_empty_input(self):
        assert build_segment_health([]) == []

    def test_ignores_non_segment_dimensions(self):
        bucket = AggregationBucket(
            time_window=_ts(10),
            dimension="recipient_domain",
            dimension_value="gmail.com",
            total=100,
            delivered=95,
        )
        assert build_segment_health([bucket]) == []


class TestBuildConfirmedIssues:
    def test_extracts_confirmed_findings(self):
        findings = [
            Finding(
                topic_title="VH delivery drop",
                statement="Bounce spike in VH segment",
                status=FindingStatus.CONFIRMED,
                evidence=["bounce rate 12%", "z-score 4.2"],
                metrics_cited={"bounce_rate": 0.12, "delivery_rate": 0.85},
                created_at=_ts(),
            ),
            Finding(
                topic_title="H stable",
                statement="H segment is fine",
                status=FindingStatus.DISPROVEN,
                evidence=[],
                created_at=_ts(),
            ),
        ]
        issues = build_confirmed_issues(findings)
        assert len(issues) == 1
        assert "bounce rate 12%" in issues[0].evidence_summary
        assert "bounce_rate=0.12" in issues[0].magnitude

    def test_empty_findings(self):
        assert build_confirmed_issues([]) == []

    def test_no_confirmed(self):
        findings = [
            Finding(
                topic_title="T",
                statement="S",
                status=FindingStatus.INCONCLUSIVE,
                created_at=_ts(),
            ),
        ]
        assert build_confirmed_issues(findings) == []


class TestBuildTrendSummary:
    def test_counts_directions(self):
        trends = [
            TrendFinding(
                direction=TrendDirection.DEGRADING,
                dimension="listid", dimension_value="VH",
                metric="delivery_rate", slope=-0.01,
                r_squared=0.85, num_points=10,
                start_value=0.95, end_value=0.85,
            ),
            TrendFinding(
                direction=TrendDirection.IMPROVING,
                dimension="listid", dimension_value="H",
                metric="delivery_rate", slope=0.005,
                r_squared=0.7, num_points=10,
                start_value=0.90, end_value=0.95,
            ),
            TrendFinding(
                direction=TrendDirection.STABLE,
                dimension="listid", dimension_value="M",
                metric="delivery_rate", slope=0.0001,
                r_squared=0.1, num_points=10,
                start_value=0.92, end_value=0.92,
            ),
        ]
        summary = build_trend_summary(trends)
        assert summary.degrading_count == 1
        assert summary.improving_count == 1
        assert summary.stable_count == 1
        assert len(summary.top_movers) == 3
        # Top mover should be the one with highest abs(slope)
        assert summary.top_movers[0].slope == -0.01

    def test_empty_trends(self):
        summary = build_trend_summary([])
        assert summary.degrading_count == 0
        assert summary.top_movers == []


class TestBuildDataCompleteness:
    def test_flags_high_zero_rates(self):
        completeness = [
            DataCompleteness(
                time_window=_ts(),
                dimension="listid",
                dimension_value="VH",
                total_records=1000,
                field_name="xmrid_account_id",
                zero_count=150,
                zero_rate=0.15,
            ),
            DataCompleteness(
                time_window=_ts(),
                dimension="listid",
                dimension_value="H",
                total_records=1000,
                field_name="xmrid_account_id",
                zero_count=50,
                zero_rate=0.05,
            ),
        ]
        rows = build_data_completeness(completeness)
        assert len(rows) == 2
        assert rows[0].flagged is True   # 15% > 10%
        assert rows[1].flagged is False  # 5% < 10%

    def test_empty_input(self):
        assert build_data_completeness([]) == []


class TestBuildCompliance:
    def test_compliance_rows(self):
        buckets = [
            AggregationBucket(
                time_window=_ts(10),
                dimension="compliance_status",
                dimension_value="compliant",
                total=500,
                delivered=480,
            ),
            AggregationBucket(
                time_window=_ts(10),
                dimension="compliance_status",
                dimension_value="non_compliant",
                total=50,
                delivered=30,
            ),
        ]
        rows = build_compliance(buckets)
        assert len(rows) == 2
        assert rows[0].compliance_status == "compliant"
        assert rows[0].total == 500

    def test_empty_input(self):
        assert build_compliance([]) == []


class TestAssembleStructuredReport:
    def _make_report(self) -> AnalysisReport:
        return AnalysisReport(
            run_id="ml-run-001",
            started_at=_ts(),
            events_parsed=5000,
            aggregations=[
                _make_seg_bucket("VH"),
                _make_seg_bucket("H"),
            ],
            completeness=[
                DataCompleteness(
                    time_window=_ts(),
                    dimension="listid",
                    dimension_value="VH",
                    total_records=100,
                    field_name="xmrid_account_id",
                    zero_count=15,
                    zero_rate=0.15,
                ),
            ],
            trends=[
                TrendFinding(
                    direction=TrendDirection.DEGRADING,
                    dimension="listid", dimension_value="VH",
                    metric="delivery_rate", slope=-0.01,
                    r_squared=0.85, num_points=10,
                    start_value=0.95, end_value=0.85,
                ),
            ],
        )

    def test_assembles_all_sections(self):
        ml_report = self._make_report()
        findings = [
            Finding(
                topic_title="VH drop",
                statement="Bounce spike",
                status=FindingStatus.CONFIRMED,
                evidence=["ev1"],
                metrics_cited={"bounce_rate": 0.12},
                created_at=_ts(),
            ),
        ]
        report = assemble_structured_report(
            run_id="inv-001",
            ml_run_id="ml-run-001",
            ml_report=ml_report,
            findings=findings,
        )
        assert report.run_id == "inv-001"
        assert len(report.segment_health) == 2
        assert len(report.confirmed_issues) == 1
        assert report.trend_summary.degrading_count == 1
        assert len(report.data_completeness) == 1
        assert report.observations == []

    def test_empty_ml_report(self):
        ml_report = AnalysisReport(
            run_id="empty", started_at=_ts(), events_parsed=0,
        )
        report = assemble_structured_report(
            run_id="inv-002",
            ml_run_id="empty",
            ml_report=ml_report,
            findings=[],
        )
        assert report.segment_health == []
        assert report.confirmed_issues == []
        assert report.trend_summary.degrading_count == 0


class TestAssembleFullReport:
    def test_full_report_has_both_documents(self):
        ml_report = AnalysisReport(
            run_id="ml-001", started_at=_ts(), events_parsed=100,
            aggregations=[_make_seg_bucket("VH")],
        )
        findings = [
            Finding(
                topic_title="T1",
                statement="Confirmed thing",
                status=FindingStatus.CONFIRMED,
                evidence=["ev"],
                created_at=_ts(),
            ),
            Finding(
                topic_title="T2",
                statement="Disproven thing",
                status=FindingStatus.DISPROVEN,
                created_at=_ts(),
            ),
        ]
        hypotheses = [
            Hypothesis(
                topic_title="T1",
                statement="Maybe X",
                reasoning="Because Y",
                created_at=_ts(),
            ),
        ]
        report = assemble_full_report(
            run_id="inv-001",
            ml_run_id="ml-001",
            ml_report=ml_report,
            findings=findings,
            hypotheses=hypotheses,
            digest_lines=["[plan] Created 1 topic"],
        )
        assert report.structured.run_id == "inv-001"
        assert len(report.structured.segment_health) == 1
        assert len(report.structured.confirmed_issues) == 1
        assert len(report.notes.hypotheses) == 1
        assert len(report.notes.unexpected_observations) == 1  # disproven
        assert len(report.notes.process_notes) == 1
