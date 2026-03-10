"""Tests for investigation result persistence (agents/storage.py)."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.agents.storage_models import InvestigationFindingRecord  # noqa: I001

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


# ---------------------------------------------------------------------------
# store_investigation_results
# ---------------------------------------------------------------------------


class TestStoreInvestigationResults:
    """Tests for store_investigation_results."""

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_store_creates_correct_record_count(self, mock_get_engine):
        from llm_pipeline.agents.storage import store_investigation_results

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine
        mock_session = MagicMock()
        mock_engine.__enter__ = MagicMock(return_value=mock_session)

        # Patch Session to return our mock
        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            findings = [_make_finding(), _make_finding(statement="Second finding")]
            hypotheses = [_make_hypothesis()]

            store_investigation_results(
                run_id="run-001",
                findings=findings,
                hypotheses=hypotheses,
                checkpoint_digest="Test digest",
                iteration_count=2,
                started_at=datetime(2026, 3, 1, tzinfo=UTC),
            )

            # 1 run + 2 findings + 1 hypothesis = 4 session.add calls
            assert mock_session.add.call_count == 4
            mock_session.commit.assert_called_once()

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_store_serializes_evidence_and_metrics(self, mock_get_engine):
        from llm_pipeline.agents.storage import store_investigation_results

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        added_objects = []

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            mock_session.add.side_effect = lambda obj: added_objects.append(obj)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            findings = [_make_finding()]

            store_investigation_results(
                run_id="run-001",
                findings=findings,
                hypotheses=[],
                checkpoint_digest="",
                iteration_count=1,
                started_at=datetime(2026, 3, 1, tzinfo=UTC),
            )

            finding_records = [
                o for o in added_objects if isinstance(o, InvestigationFindingRecord)
            ]
            assert len(finding_records) == 1
            rec = finding_records[0]
            assert rec.evidence == '["bounce rate 12%", "z-score 4.2"]'
            assert rec.metrics_cited == '{"delivery_rate": 0.85, "bounce_rate": 0.12}'
            assert rec.status == "confirmed"


# ---------------------------------------------------------------------------
# load_investigation
# ---------------------------------------------------------------------------


class TestLoadInvestigation:
    """Tests for load_investigation."""

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_load_returns_none_for_missing_run(self, mock_get_engine):
        from llm_pipeline.agents.storage import load_investigation

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            # scalar_one_or_none returns None
            mock_session.execute.return_value.scalar_one_or_none.return_value = None
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            result = load_investigation("nonexistent-run")
            assert result is None

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_load_reconstructs_finding_objects(self, mock_get_engine):
        from llm_pipeline.agents.storage import load_investigation

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        # Build mock rows
        mock_run = MagicMock()
        mock_run.run_id = "run-001"
        mock_run.started_at = datetime(2026, 3, 1, tzinfo=UTC)
        mock_run.completed_at = datetime(2026, 3, 1, 1, 0, tzinfo=UTC)
        mock_run.iteration_count = 2
        mock_run.checkpoint_digest = "digest text"

        mock_finding = MagicMock()
        mock_finding.topic_title = "VH delivery drop"
        mock_finding.statement = "Delivery dropped 15%"
        mock_finding.status = "confirmed"
        mock_finding.evidence = '["bounce rate 12%"]'
        mock_finding.metrics_cited = '{"delivery_rate": 0.85}'
        mock_finding.created_at = datetime(2026, 3, 1, tzinfo=UTC)

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()

            # First execute → run record, second → findings, third → hypotheses
            calls = [
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_finding])))),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
            ]
            mock_session.execute = MagicMock(side_effect=calls)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            result = load_investigation("run-001")

            assert result is not None
            assert result["run_id"] == "run-001"
            assert result["iteration_count"] == 2
            assert result["checkpoint_digest"] == "digest text"
            assert len(result["findings"]) == 1
            assert len(result["hypotheses"]) == 0

            f = result["findings"][0]
            assert isinstance(f, Finding)
            assert f.status == FindingStatus.CONFIRMED
            assert f.evidence == ["bounce rate 12%"]
            assert f.metrics_cited == {"delivery_rate": 0.85}

    @patch("llm_pipeline.agents.storage.get_engine")
    def test_load_reconstructs_hypothesis_objects(self, mock_get_engine):
        from llm_pipeline.agents.storage import load_investigation

        mock_engine = MagicMock()
        mock_get_engine.return_value = mock_engine

        mock_run = MagicMock()
        mock_run.run_id = "run-002"
        mock_run.started_at = datetime(2026, 3, 1, tzinfo=UTC)
        mock_run.completed_at = datetime(2026, 3, 1, 1, 0, tzinfo=UTC)
        mock_run.iteration_count = 1
        mock_run.checkpoint_digest = ""

        mock_hyp = MagicMock()
        mock_hyp.topic_title = "IP warming"
        mock_hyp.statement = "New IPs may be throttled"
        mock_hyp.reasoning = "Pool rotated last week"
        mock_hyp.created_at = datetime(2026, 3, 1, tzinfo=UTC)

        with patch("llm_pipeline.agents.storage.Session") as mock_session_cls:
            mock_session = MagicMock()
            calls = [
                MagicMock(scalar_one_or_none=MagicMock(return_value=mock_run)),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))),
                MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_hyp])))),
            ]
            mock_session.execute = MagicMock(side_effect=calls)
            ctx = MagicMock()
            ctx.__enter__ = MagicMock(return_value=mock_session)
            ctx.__exit__ = MagicMock(return_value=False)
            mock_session_cls.return_value = ctx

            result = load_investigation("run-002")

            assert result is not None
            assert len(result["hypotheses"]) == 1

            h = result["hypotheses"][0]
            assert isinstance(h, Hypothesis)
            assert h.topic_title == "IP warming"
            assert h.statement == "New IPs may be throttled"
            assert h.reasoning == "Pool rotated last week"
