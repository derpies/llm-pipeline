"""Tests for the FastAPI dashboard API."""

import json
from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from llm_pipeline.api.dependencies import get_db, get_weaviate
from llm_pipeline.models.db import Base

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_test_engine = None


def _get_test_engine():
    return _test_engine


def _override_get_db():
    engine = _get_test_engine()
    with Session(engine) as session:
        yield session


def _override_get_weaviate():
    return MagicMock()


@pytest.fixture(autouse=True)
def _setup_db():
    """Create tables fresh for each test using SQLite in-memory."""
    global _test_engine

    # StaticPool ensures all connections share the same in-memory DB
    _test_engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # Attach "knowledge" schema so knowledge_audit table can be created
    @event.listens_for(_test_engine, "connect")
    def _attach_knowledge(dbapi_conn, connection_record):
        dbapi_conn.execute("ATTACH DATABASE ':memory:' AS knowledge")

    # Import models so Base.metadata knows about them
    import llm_pipeline.agents.storage_models  # noqa: F401
    import llm_pipeline.email_analytics.models  # noqa: F401

    Base.metadata.create_all(_test_engine)
    yield
    Base.metadata.drop_all(_test_engine)
    _test_engine = None


@pytest.fixture()
def client():
    # Patch init_db to skip Postgres-specific migrations during lifespan
    with patch("llm_pipeline.api.main.init_db"):
        from llm_pipeline.api.main import app

        app.dependency_overrides[get_db] = _override_get_db
        app.dependency_overrides[get_weaviate] = _override_get_weaviate
        with TestClient(app) as c:
            yield c
        app.dependency_overrides.clear()


def _seed_ml_run(run_id="ml-001"):
    from llm_pipeline.email_analytics.models import AnalysisRunRecord

    engine = _get_test_engine()
    with Session(engine) as session:
        session.add(
            AnalysisRunRecord(
                run_id=run_id,
                started_at=datetime(2026, 3, 1, 12, 0, tzinfo=UTC),
                completed_at=datetime(2026, 3, 1, 12, 5, tzinfo=UTC),
                files_processed=2,
                events_parsed=1000,
                anomaly_count=3,
                trend_count=1,
                source_files=json.dumps(["file1.json", "file2.json"]),
            )
        )
        session.commit()


def _seed_investigation(run_id="inv-001"):
    from llm_pipeline.agents.storage_models import (
        InvestigationFindingRecord,
        InvestigationHypothesisRecord,
        InvestigationRunRecord,
    )

    engine = _get_test_engine()
    now = datetime(2026, 3, 1, 14, 0, tzinfo=UTC)
    with Session(engine) as session:
        session.add(
            InvestigationRunRecord(
                run_id=run_id,
                started_at=datetime(2026, 3, 1, 13, 0, tzinfo=UTC),
                completed_at=now,
                iteration_count=2,
                finding_count=1,
                hypothesis_count=1,
                checkpoint_digest="test digest",
                label="test-label",
                status="success",
                is_dry_run=False,
                ml_run_id="ml-001",
                quality_warnings="[]",
                source_files=json.dumps(["file1.json"]),
                created_at=now,
            )
        )
        session.add(
            InvestigationFindingRecord(
                run_id=run_id,
                topic_title="VH delivery drop",
                statement="Delivery rate dropped 15%",
                status="confirmed",
                evidence=json.dumps(["bounce rate 12%"]),
                metrics_cited=json.dumps({"delivery_rate": 0.85}),
                created_at=now,
            )
        )
        session.add(
            InvestigationHypothesisRecord(
                run_id=run_id,
                topic_title="VH delivery drop",
                statement="IP warming issue",
                reasoning="New IPs added",
                created_at=now,
            )
        )
        session.commit()


def _seed_aggregation(run_id="ml-001"):
    from llm_pipeline.email_analytics.models import AggregationRecord

    engine = _get_test_engine()
    with Session(engine) as session:
        session.add(
            AggregationRecord(
                run_id=run_id,
                time_window=datetime(2026, 3, 1, tzinfo=UTC),
                dimension="listid",
                dimension_value="VH-pool",
                total=1000,
                delivered=950,
                bounced=30,
                deferred=20,
                complained=0,
                delivery_rate=0.95,
                bounce_rate=0.03,
                deferral_rate=0.02,
                complaint_rate=0.0,
            )
        )
        session.commit()


# ---------------------------------------------------------------------------
# /api/meta
# ---------------------------------------------------------------------------


class TestMeta:
    def test_meta_returns_expected_structure(self, client):
        resp = client.get("/api/meta")
        assert resp.status_code == 200
        data = resp.json()
        assert "finding_statuses" in data
        assert "knowledge_tiers" in data
        assert "run_statuses" in data
        assert "commands" in data
        assert set(data["finding_statuses"]) == {"confirmed", "disproven", "inconclusive"}
        assert len(data["knowledge_tiers"]) == 4

    def test_meta_knowledge_tiers_have_weights(self, client):
        resp = client.get("/api/meta")
        tiers = resp.json()["knowledge_tiers"]
        for t in tiers:
            assert "name" in t
            assert "weight" in t
            assert "description" in t
            assert "color" in t


# ---------------------------------------------------------------------------
# /api/domains
# ---------------------------------------------------------------------------


class TestDomains:
    def test_domains_returns_email_delivery(self, client):
        resp = client.get("/api/domains")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) >= 1
        names = [d["name"] for d in data]
        assert "email_delivery" in names

    def test_domains_has_ml_data_types(self, client):
        resp = client.get("/api/domains")
        email = [d for d in resp.json() if d["name"] == "email_delivery"][0]
        mdt = email["ml_data_types"]
        assert "dimensions" in mdt
        assert "metrics" in mdt
        assert "anomaly_types" in mdt
        assert "listid" in mdt["dimensions"]

    def test_domains_has_roles(self, client):
        resp = client.get("/api/domains")
        email = [d for d in resp.json() if d["name"] == "email_delivery"][0]
        assert len(email["roles"]) > 0
        role_names = [r["name"] for r in email["roles"]]
        assert "reputation" in role_names


# ---------------------------------------------------------------------------
# /api/runs
# ---------------------------------------------------------------------------


class TestRuns:
    def test_runs_empty(self, client):
        resp = client.get("/api/runs")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 0
        assert data["runs"] == []

    def test_runs_returns_ml_run(self, client):
        _seed_ml_run()
        resp = client.get("/api/runs")
        data = resp.json()
        assert data["total"] == 1
        assert data["runs"][0]["run_id"] == "ml-001"
        assert data["runs"][0]["command"] == "analyze_email"

    def test_runs_returns_investigation(self, client):
        _seed_investigation()
        resp = client.get("/api/runs")
        data = resp.json()
        assert data["total"] == 1
        assert data["runs"][0]["command"] == "investigate"

    def test_runs_filter_by_command(self, client):
        _seed_ml_run()
        _seed_investigation()
        resp = client.get("/api/runs?command=analyze_email")
        assert resp.json()["total"] == 1
        assert resp.json()["runs"][0]["command"] == "analyze_email"

    def test_runs_pagination(self, client):
        _seed_ml_run("ml-001")
        _seed_ml_run("ml-002")
        resp = client.get("/api/runs?limit=1&offset=0")
        data = resp.json()
        assert data["total"] == 2
        assert len(data["runs"]) == 1

    def test_runs_search(self, client):
        _seed_ml_run("ml-001")
        _seed_ml_run("ml-002")
        resp = client.get("/api/runs?search=ml-002")
        assert resp.json()["total"] == 1


# ---------------------------------------------------------------------------
# /api/investigations/{run_id}
# ---------------------------------------------------------------------------


class TestInvestigations:
    def test_investigation_not_found(self, client):
        resp = client.get("/api/investigations/nonexistent")
        assert resp.status_code == 404

    def test_investigation_returns_data(self, client):
        _seed_investigation()
        resp = client.get("/api/investigations/inv-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "inv-001"
        assert len(data["findings"]) == 1
        assert len(data["hypotheses"]) == 1
        assert data["findings"][0]["status"] == "confirmed"
        assert data["iteration_count"] == 2

    def test_investigation_has_duration(self, client):
        _seed_investigation()
        resp = client.get("/api/investigations/inv-001")
        data = resp.json()
        assert data["duration_seconds"] == 3600.0  # 1 hour


# ---------------------------------------------------------------------------
# /api/investigations/{run_id}/report
# ---------------------------------------------------------------------------


class TestInvestigationReport:
    def test_report_not_found(self, client):
        resp = client.get("/api/investigations/nonexistent/report")
        assert resp.status_code == 404

    def test_report_json(self, client):
        from llm_pipeline.agents.storage_models import InvestigationReportRecord

        engine = _get_test_engine()
        with Session(engine) as session:
            session.add(
                InvestigationReportRecord(
                    run_id="inv-001",
                    report_json=json.dumps({"title": "Test Report"}),
                    report_markdown="# Test Report",
                )
            )
            session.commit()

        resp = client.get("/api/investigations/inv-001/report?format=json")
        assert resp.status_code == 200
        assert resp.json()["report"]["title"] == "Test Report"

    def test_report_markdown(self, client):
        from llm_pipeline.agents.storage_models import InvestigationReportRecord

        engine = _get_test_engine()
        with Session(engine) as session:
            session.add(
                InvestigationReportRecord(
                    run_id="inv-002",
                    report_json="{}",
                    report_markdown="# Test Report",
                )
            )
            session.commit()

        resp = client.get("/api/investigations/inv-002/report?format=markdown")
        assert resp.status_code == 200
        assert resp.json()["markdown"] == "# Test Report"


# ---------------------------------------------------------------------------
# /api/ml/{run_id}
# ---------------------------------------------------------------------------


class TestMl:
    def test_ml_run_not_found(self, client):
        resp = client.get("/api/ml/nonexistent")
        assert resp.status_code == 404

    def test_ml_run_summary(self, client):
        _seed_ml_run()
        resp = client.get("/api/ml/ml-001")
        assert resp.status_code == 200
        data = resp.json()
        assert data["run_id"] == "ml-001"
        assert data["files_processed"] == 2
        assert "counts" in data

    def test_ml_aggregations(self, client):
        _seed_ml_run()
        _seed_aggregation()
        resp = client.get("/api/ml/ml-001/aggregations")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert data["aggregations"][0]["dimension"] == "listid"

    def test_ml_aggregations_filter(self, client):
        _seed_ml_run()
        _seed_aggregation()
        resp = client.get("/api/ml/ml-001/aggregations?dimension=recipient_domain")
        assert resp.json()["total"] == 0

    def test_ml_anomalies_empty(self, client):
        _seed_ml_run()
        resp = client.get("/api/ml/ml-001/anomalies")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_ml_trends_empty(self, client):
        _seed_ml_run()
        resp = client.get("/api/ml/ml-001/trends")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_ml_completeness_empty(self, client):
        _seed_ml_run()
        resp = client.get("/api/ml/ml-001/completeness")
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ---------------------------------------------------------------------------
# /api/knowledge/search and /api/knowledge/stats
# ---------------------------------------------------------------------------


class TestKnowledge:
    def test_search_without_query_browse_mode(self, client):
        resp = client.get("/api/knowledge/search")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "results" in data

    @patch("llm_pipeline.api.routers.knowledge.retrieve_knowledge")
    def test_search_returns_results(self, mock_retrieve, client):
        from llm_pipeline.knowledge.models import KnowledgeTier
        from llm_pipeline.knowledge.retrieval import KnowledgeResult

        mock_retrieve.return_value = [
            KnowledgeResult(
                entry_id="e1",
                tier=KnowledgeTier.GROUNDED,
                statement="SPF alignment required",
                topic="compliance",
                similarity=0.92,
                weighted_score=0.92,
                confidence=1.0,
            )
        ]

        resp = client.get("/api/knowledge/search?q=SPF+compliance")
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) == 1
        assert results[0]["tier"] == "grounded"
        assert results[0]["statement"] == "SPF alignment required"

    @patch("llm_pipeline.api.routers.knowledge.retrieve_knowledge")
    def test_search_with_tier_filter(self, mock_retrieve, client):
        mock_retrieve.return_value = []
        resp = client.get("/api/knowledge/search?q=test&tier=finding")
        assert resp.status_code == 200
        # Verify tier filter was passed
        call_kwargs = mock_retrieve.call_args[1]
        assert call_kwargs["tiers"][0].value == "finding"

    def test_stats_returns_all_tiers(self, client):
        resp = client.get("/api/knowledge/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 4
        tier_names = [s["tier"] for s in data]
        assert "grounded" in tier_names
        assert "hypothesis" in tier_names
