"""Tests for regenerate-report CLI command and list_investigations."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_finding(**overrides) -> Finding:
    defaults = {
        "topic_title": "VH delivery drop",
        "statement": "Delivery rate dropped 15%",
        "status": FindingStatus.CONFIRMED,
        "evidence": ["bounce rate 12%", "z-score 4.2"],
        "metrics_cited": {"delivery_rate": 0.85, "bounce_rate": 0.12},
        "created_at": datetime(2026, 3, 1, tzinfo=UTC),
        "run_id": "run-001",
    }
    defaults.update(overrides)
    return Finding(**defaults)


def _make_hypothesis(**overrides) -> Hypothesis:
    defaults = {
        "topic_title": "VH delivery drop",
        "statement": "IP warming issue on pool VH-1",
        "reasoning": "New IPs added recently",
        "created_at": datetime(2026, 3, 1, tzinfo=UTC),
        "run_id": "run-001",
    }
    defaults.update(overrides)
    return Hypothesis(**defaults)


def _make_investigation(run_id="run-001", label="", ml_run_id=None):
    return {
        "run_id": run_id,
        "started_at": datetime(2026, 3, 1, tzinfo=UTC),
        "completed_at": datetime(2026, 3, 1, 0, 5, tzinfo=UTC),
        "iteration_count": 2,
        "findings": [_make_finding(run_id=run_id)],
        "hypotheses": [_make_hypothesis(run_id=run_id)],
        "checkpoint_digest": "Test digest line 1\nTest digest line 2",
        "label": label,
        "status": "success",
        "is_dry_run": False,
        "ml_run_id": ml_run_id or run_id,
        "quality_warnings": [],
    }


# ---------------------------------------------------------------------------
# list_investigations
# ---------------------------------------------------------------------------


class TestListInvestigations:
    @patch("llm_pipeline.agents.storage.get_engine")
    def test_returns_correct_structure(self, mock_get_engine):
        from llm_pipeline.agents.storage import list_investigations
        from llm_pipeline.email_analytics.models import InvestigationRunRecord

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_row = MagicMock(spec=InvestigationRunRecord)
        mock_row.run_id = "run-001"
        mock_row.label = "baseline"
        mock_row.status = "success"
        mock_row.is_dry_run = False
        mock_row.ml_run_id = "run-001"
        mock_row.finding_count = 5
        mock_row.hypothesis_count = 3
        mock_row.iteration_count = 2
        mock_row.created_at = datetime(2026, 3, 1, tzinfo=UTC)

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            mock_session.execute.return_value.scalars.return_value.all.return_value = [mock_row]

            result = list_investigations("run-001")

        assert len(result) == 1
        r = result[0]
        assert r["run_id"] == "run-001"
        assert r["label"] == "baseline"
        assert r["finding_count"] == 5
        assert r["hypothesis_count"] == 3
        assert r["iteration_count"] == 2

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_returns_empty_list_when_no_runs(self, mock_get_engine):
        from llm_pipeline.agents.storage import list_investigations

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            mock_session.execute.return_value.scalars.return_value.all.return_value = []

            result = list_investigations()

        assert result == []


# ---------------------------------------------------------------------------
# write_investigation_report_files — label parameter
# ---------------------------------------------------------------------------


class TestWriteReportFilesLabel:
    @patch("llm_pipeline.agents.report_renderer.render_json", return_value='{"test": true}')
    @patch("llm_pipeline.agents.report_renderer.render_markdown", return_value="# Test")
    def test_file_naming_without_label(self, mock_md, mock_json, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_report_files

        report = MagicMock()
        json_path, md_path = write_investigation_report_files(
            "run-001", report, output_dir=tmp_path
        )

        assert json_path.name == "run-001-report.json"
        assert md_path.name == "run-001-report.md"
        assert json_path.exists()
        assert md_path.exists()

    @patch("llm_pipeline.agents.report_renderer.render_json", return_value='{"test": true}')
    @patch("llm_pipeline.agents.report_renderer.render_markdown", return_value="# Test")
    def test_file_naming_with_label(self, mock_md, mock_json, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_report_files

        report = MagicMock()
        json_path, md_path = write_investigation_report_files(
            "run-001", report, output_dir=tmp_path, label="baseline"
        )

        assert json_path.name == "run-001-baseline-report.json"
        assert md_path.name == "run-001-baseline-report.md"

    @patch("llm_pipeline.agents.report_renderer.render_json", return_value='{"test": true}')
    @patch("llm_pipeline.agents.report_renderer.render_markdown", return_value="# Test")
    def test_empty_label_same_as_no_label(self, mock_md, mock_json, tmp_path):
        from llm_pipeline.agents.storage import write_investigation_report_files

        report = MagicMock()
        json_path, _ = write_investigation_report_files(
            "run-001", report, output_dir=tmp_path, label=""
        )

        assert json_path.name == "run-001-report.json"


# ---------------------------------------------------------------------------
# regenerate_report CLI flow
# ---------------------------------------------------------------------------


class TestRegenerateReportFlow:
    @patch("llm_pipeline.agents.storage.store_investigation_report")
    @patch("llm_pipeline.agents.storage.write_investigation_report_files")
    @patch("llm_pipeline.agents.report_builder.assemble_full_report")
    @patch("llm_pipeline.email_analytics.storage.load_report")
    @patch("llm_pipeline.agents.storage.load_investigation")
    @patch("llm_pipeline.email_analytics.storage.init_db")
    def test_single_run_regeneration(
        self,
        mock_init_db,
        mock_load_inv,
        mock_load_report,
        mock_assemble,
        mock_write,
        mock_store_report,
    ):
        from typer.testing import CliRunner

        from llm_pipeline.cli import app

        inv = _make_investigation()
        mock_load_inv.return_value = inv
        mock_load_report.return_value = MagicMock()
        mock_report = MagicMock()
        mock_assemble.return_value = mock_report
        mock_write.return_value = (Path("/tmp/test.json"), Path("/tmp/test.md"))

        runner = CliRunner()
        result = runner.invoke(app, ["regenerate-report", "run-001"])

        assert result.exit_code == 0
        mock_load_inv.assert_called_once_with("run-001", label=None)
        mock_assemble.assert_called_once()
        mock_write.assert_called_once()

    @patch("llm_pipeline.agents.storage.store_investigation_report")
    @patch("llm_pipeline.agents.storage.write_investigation_report_files")
    @patch("llm_pipeline.agents.report_builder.assemble_full_report")
    @patch("llm_pipeline.email_analytics.storage.load_report")
    @patch("llm_pipeline.agents.storage.load_investigation")
    @patch("llm_pipeline.agents.storage.list_investigations")
    @patch("llm_pipeline.email_analytics.storage.init_db")
    def test_all_labels_regeneration(
        self,
        mock_init_db,
        mock_list_inv,
        mock_load_inv,
        mock_load_report,
        mock_assemble,
        mock_write,
        mock_store_report,
    ):
        from typer.testing import CliRunner

        from llm_pipeline.cli import app

        mock_list_inv.return_value = [
            {"run_id": "run-001", "label": "baseline", "status": "success"},
            {"run_id": "run-001", "label": "no-knowledge", "status": "success"},
        ]
        mock_load_inv.side_effect = [
            _make_investigation(label="baseline"),
            _make_investigation(label="no-knowledge"),
        ]
        mock_load_report.return_value = MagicMock()
        mock_assemble.return_value = MagicMock()
        mock_write.return_value = (Path("/tmp/test.json"), Path("/tmp/test.md"))

        runner = CliRunner()
        result = runner.invoke(app, ["regenerate-report", "run-001", "--all-labels"])

        assert result.exit_code == 0
        assert mock_assemble.call_count == 2
        assert "2 report(s) regenerated" in result.output

    @patch("llm_pipeline.agents.storage.load_investigation")
    @patch("llm_pipeline.email_analytics.storage.init_db")
    def test_missing_run_id_exits_with_error(self, mock_init_db, mock_load_inv):
        from typer.testing import CliRunner

        from llm_pipeline.cli import app

        mock_load_inv.return_value = None

        runner = CliRunner()
        result = runner.invoke(app, ["regenerate-report", "nonexistent"])

        assert result.exit_code == 1
        assert "No investigation found" in result.output

    @patch("llm_pipeline.agents.storage.store_investigation_report")
    @patch("llm_pipeline.agents.storage.write_investigation_report_files")
    @patch("llm_pipeline.agents.report_builder.assemble_full_report")
    @patch("llm_pipeline.email_analytics.storage.load_report")
    @patch("llm_pipeline.agents.storage.load_investigation")
    @patch("llm_pipeline.email_analytics.storage.init_db")
    def test_missing_ml_report_skips(
        self,
        mock_init_db,
        mock_load_inv,
        mock_load_report,
        mock_assemble,
        mock_write,
        mock_store_report,
    ):
        from typer.testing import CliRunner

        from llm_pipeline.cli import app

        mock_load_inv.return_value = _make_investigation()
        mock_load_report.return_value = None  # ML report not found

        runner = CliRunner()
        result = runner.invoke(app, ["regenerate-report", "run-001"])

        assert result.exit_code == 0
        assert "ML report" in result.output
        assert "not found" in result.output
        mock_assemble.assert_not_called()

    @patch("llm_pipeline.agents.storage.store_investigation_report")
    @patch("llm_pipeline.agents.storage.write_investigation_report_files")
    @patch("llm_pipeline.agents.report_builder.assemble_full_report")
    @patch("llm_pipeline.email_analytics.storage.load_report")
    @patch("llm_pipeline.agents.storage.load_investigation")
    @patch("llm_pipeline.email_analytics.storage.init_db")
    def test_label_flag_passes_to_load(
        self,
        mock_init_db,
        mock_load_inv,
        mock_load_report,
        mock_assemble,
        mock_write,
        mock_store_report,
    ):
        from typer.testing import CliRunner

        from llm_pipeline.cli import app

        mock_load_inv.return_value = _make_investigation(label="baseline")
        mock_load_report.return_value = MagicMock()
        mock_assemble.return_value = MagicMock()
        mock_write.return_value = (Path("/tmp/test.json"), Path("/tmp/test.md"))

        runner = CliRunner()
        result = runner.invoke(app, ["regenerate-report", "run-001", "--label", "baseline"])

        assert result.exit_code == 0
        mock_load_inv.assert_called_once_with("run-001", label="baseline")
