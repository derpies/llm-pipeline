"""Tests for knowledge store write operations."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

import pytest

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.knowledge.models import (
    DeprecationStatus,
    FindingEntry,
    HypothesisEntry,
    KnowledgeScope,
    KnowledgeTier,
    TruthEntry,
)
from llm_pipeline.knowledge.store import (
    _audit,
    _entry_to_properties,
    deprecate,
    merge_observation,
    promote_to_finding,
    store_entry,
    store_investigation_to_knowledge,
)


def _mock_weaviate_client():
    """Create a mock Weaviate client with common setup."""
    client = MagicMock()
    collection = MagicMock()
    tenant_collection = MagicMock()

    client.collections.get.return_value = collection
    client.collections.exists.return_value = True
    client.is_connected.return_value = True
    collection.with_tenant.return_value = tenant_collection
    collection.tenants.get.return_value = {"community": MagicMock()}

    # Default: no duplicate found
    tenant_collection.query.near_vector.return_value = MagicMock(objects=[])
    tenant_collection.data.insert.return_value = None

    return client, collection, tenant_collection


def _mock_session():
    """Create a mock SQLAlchemy session."""
    session = MagicMock()
    return session


class TestEntryToProperties:
    def test_hypothesis_properties(self):
        entry = HypothesisEntry(
            id="test-id",
            statement="Test statement",
            topic="bounce_rate",
            scope=KnowledgeScope.COMMUNITY,
        )
        props = _entry_to_properties(entry)
        assert props["entry_id"] == "test-id"
        assert props["statement"] == "Test statement"
        assert props["topic"] == "bounce_rate"
        assert props["scope"] == "community"
        assert "finding_status" not in props

    def test_finding_properties(self):
        entry = FindingEntry(
            statement="Test finding",
            finding_status="confirmed",
        )
        props = _entry_to_properties(entry)
        assert props["finding_status"] == "confirmed"


class TestStoreEntry:
    @patch("llm_pipeline.knowledge.store._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store.ensure_tenant")
    def test_store_new_hypothesis(self, mock_ensure, mock_get_session, mock_embed):
        client, _, tenant_coll = _mock_weaviate_client()
        session = _mock_session()
        mock_get_session.return_value = session

        entry = HypothesisEntry(
            statement="Pool reputation may drop",
            topic="reputation",
        )
        entry.recompute_confidence()

        entry_id, was_merged = store_entry(entry, client=client)

        assert entry_id == entry.id
        assert was_merged is False
        tenant_coll.data.insert.assert_called_once()
        session.add.assert_called_once()  # audit record
        session.commit.assert_called_once()

    @patch("llm_pipeline.knowledge.store._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store.ensure_tenant")
    @patch("llm_pipeline.knowledge.store._find_duplicate", return_value="existing-id")
    @patch("llm_pipeline.knowledge.store.merge_observation")
    def test_store_deduplicates(
        self, mock_merge, mock_find_dup, mock_ensure, mock_get_session, mock_embed
    ):
        client, _, _ = _mock_weaviate_client()
        session = _mock_session()
        mock_get_session.return_value = session

        entry = HypothesisEntry(
            statement="Duplicate entry",
            topic="reputation",
            source_run_ids=["run-002"],
        )

        entry_id, was_merged = store_entry(entry, client=client)

        assert entry_id == "existing-id"
        assert was_merged is True
        mock_merge.assert_called_once()

    @patch("llm_pipeline.knowledge.store._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store.ensure_tenant")
    def test_store_finding(self, mock_ensure, mock_get_session, mock_embed):
        client, _, tenant_coll = _mock_weaviate_client()
        session = _mock_session()
        mock_get_session.return_value = session

        entry = FindingEntry(
            statement="Delivery rate dropped",
            topic="delivery_rate",
            finding_status="confirmed",
        )
        entry.recompute_confidence()

        entry_id, was_merged = store_entry(entry, client=client)
        assert was_merged is False

        # Verify the properties passed to Weaviate include finding_status
        insert_call = tenant_coll.data.insert.call_args
        assert insert_call.kwargs["properties"]["finding_status"] == "confirmed"


class TestPromoteToFinding:
    @patch("llm_pipeline.knowledge.store._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store.ensure_tenant")
    @patch("llm_pipeline.knowledge.store.deprecate")
    def test_promote_creates_finding_and_deprecates_hypothesis(
        self, mock_deprecate, mock_ensure, mock_get_session, mock_embed
    ):
        client, _, tenant_coll = _mock_weaviate_client()
        session = _mock_session()
        mock_get_session.return_value = session

        finding = FindingEntry(
            statement="Confirmed pattern",
            finding_status="confirmed",
        )

        result_id = promote_to_finding("hyp-123", finding, client=client)

        assert result_id == finding.id
        assert finding.promoted_from == "hyp-123"
        mock_deprecate.assert_called_once()
        tenant_coll.data.insert.assert_called_once()
        # Two audit calls: deprecation + promotion
        assert session.add.call_count >= 1
        session.commit.assert_called_once()


class TestMergeObservation:
    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store._find_object_by_entry_id")
    @patch("llm_pipeline.knowledge.store._update_object")
    def test_merge_increments_count(self, mock_update, mock_find, mock_get_session):
        session = _mock_session()
        mock_get_session.return_value = session

        mock_obj = MagicMock()
        mock_obj.properties = {
            "observation_count": 3,
            "source_run_ids": ["run-001"],
        }
        mock_find.return_value = mock_obj

        client = MagicMock()
        merge_observation(
            entry_id="entry-123",
            tier=KnowledgeTier.FINDING,
            new_run_id="run-002",
            new_evidence=["new evidence"],
            client=client,
        )

        mock_update.assert_called_once()
        update_args = mock_update.call_args
        updates = update_args.args[3] if len(update_args.args) > 3 else update_args.kwargs.get("updates", {})
        # Check properties dict passed to update
        assert updates["observation_count"] == 4
        assert "run-002" in updates["source_run_ids"]

    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store._find_object_by_entry_id", return_value=None)
    def test_merge_warns_on_missing_entry(self, mock_find, mock_get_session):
        session = _mock_session()
        mock_get_session.return_value = session
        client = MagicMock()

        # Should not raise
        merge_observation(
            entry_id="nonexistent",
            tier=KnowledgeTier.HYPOTHESIS,
            client=client,
        )


class TestDeprecate:
    @patch("llm_pipeline.knowledge.store._get_db_session")
    @patch("llm_pipeline.knowledge.store._update_property_by_entry_id")
    def test_deprecate_updates_status(self, mock_update_prop, mock_get_session):
        session = _mock_session()
        mock_get_session.return_value = session
        client = MagicMock()

        deprecate(
            entry_id="entry-456",
            tier=KnowledgeTier.HYPOTHESIS,
            reason="Promoted to finding",
            client=client,
        )

        mock_update_prop.assert_called_once_with(
            client, "Hypothesis", "entry-456", "status", "deprecated"
        )
        session.add.assert_called_once()  # audit record
        session.commit.assert_called_once()


class TestStoreInvestigationToKnowledge:
    @patch("llm_pipeline.knowledge.store.store_finding")
    @patch("llm_pipeline.knowledge.store.store_hypothesis")
    def test_converts_and_stores(self, mock_store_hyp, mock_store_find):
        mock_store_find.return_value = ("find-id", False)
        mock_store_hyp.return_value = ("hyp-id", False)

        now = datetime.now(UTC)
        findings = [
            Finding(
                topic_title="Test",
                statement="Test finding",
                status=FindingStatus.CONFIRMED,
                created_at=now,
                run_id="run-001",
            )
        ]
        hypotheses = [
            Hypothesis(
                topic_title="Test",
                statement="Test hypothesis",
                reasoning="Because reasons",
                created_at=now,
                run_id="run-001",
            )
        ]

        counts = store_investigation_to_knowledge(
            findings=findings,
            hypotheses=hypotheses,
            run_id="run-001",
            client=MagicMock(),
        )

        assert counts["stored"] == 2
        assert counts["merged"] == 0
        mock_store_find.assert_called_once()
        mock_store_hyp.assert_called_once()

    @patch("llm_pipeline.knowledge.store.store_finding")
    @patch("llm_pipeline.knowledge.store.store_hypothesis")
    def test_counts_merges(self, mock_store_hyp, mock_store_find):
        mock_store_find.return_value = ("find-id", True)  # merged
        mock_store_hyp.return_value = ("hyp-id", False)  # stored

        now = datetime.now(UTC)
        findings = [
            Finding(
                topic_title="T",
                statement="S",
                status=FindingStatus.CONFIRMED,
                created_at=now,
            )
        ]
        hypotheses = [
            Hypothesis(topic_title="T", statement="S", reasoning="R", created_at=now)
        ]

        counts = store_investigation_to_knowledge(
            findings=findings, hypotheses=hypotheses, client=MagicMock()
        )
        assert counts["stored"] == 1
        assert counts["merged"] == 1
