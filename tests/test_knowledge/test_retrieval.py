"""Tests for knowledge store retrieval — tier-weighted search."""

from unittest.mock import MagicMock, patch

from llm_pipeline.knowledge.models import KnowledgeScope, KnowledgeTier
from llm_pipeline.knowledge.retrieval import (
    TIER_WEIGHTS,
    KnowledgeResult,
    retrieve_for_account,
    retrieve_knowledge,
)


def _mock_weaviate_result(entry_id, statement, topic, tier, confidence, distance, status="active", finding_status=""):
    """Create a mock Weaviate query result object."""
    obj = MagicMock()
    obj.properties = {
        "entry_id": entry_id,
        "statement": statement,
        "topic": topic,
        "dimension": "",
        "dimension_value": "",
        "scope": "community",
        "account_id": "",
        "confidence": confidence,
        "observation_count": 1,
        "status": status,
        "source_run_ids": [],
    }
    if finding_status:
        obj.properties["finding_status"] = finding_status
    obj.metadata = MagicMock()
    obj.metadata.distance = distance
    return obj


def _setup_client(results_by_collection: dict[str, list]):
    """Create a mock client that returns specified results per collection."""
    client = MagicMock()

    def get_collection(name):
        collection = MagicMock()
        tenant_coll = MagicMock()
        collection.with_tenant.return_value = tenant_coll
        collection.tenants.get.return_value = {"community": MagicMock()}

        result_mock = MagicMock()
        result_mock.objects = results_by_collection.get(name, [])
        tenant_coll.query.near_vector.return_value = result_mock
        return collection

    client.collections.get.side_effect = get_collection
    client.collections.exists.return_value = True
    return client


class TestRetrieveKnowledge:
    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_returns_weighted_results(self, mock_ensure, mock_embed):
        # Truth result with high confidence, moderate similarity
        truth_obj = _mock_weaviate_result(
            "truth-1", "Confirmed pattern", "delivery_rate",
            KnowledgeTier.TRUTH, confidence=0.85, distance=0.2
        )
        # Hypothesis result with low confidence, high similarity
        hyp_obj = _mock_weaviate_result(
            "hyp-1", "Maybe this pattern", "bounce_rate",
            KnowledgeTier.HYPOTHESIS, confidence=0.1, distance=0.05
        )

        client = _setup_client({
            "Truth": [truth_obj],
            "Hypothesis": [hyp_obj],
            "Finding": [],
            "Grounded": [],
        })

        results = retrieve_knowledge("delivery drop", client=client)

        assert len(results) == 2
        # Truth should rank higher due to tier weight + confidence
        assert results[0].entry_id == "truth-1"
        assert results[0].tier == KnowledgeTier.TRUTH
        assert results[1].entry_id == "hyp-1"
        assert results[1].tier == KnowledgeTier.HYPOTHESIS

    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_filters_deprecated(self, mock_ensure, mock_embed):
        active_obj = _mock_weaviate_result(
            "active-1", "Active finding", "test",
            KnowledgeTier.FINDING, confidence=0.5, distance=0.1
        )
        deprecated_obj = _mock_weaviate_result(
            "dep-1", "Deprecated finding", "test",
            KnowledgeTier.FINDING, confidence=0.5, distance=0.1,
            status="deprecated"
        )

        client = _setup_client({"Finding": [active_obj, deprecated_obj], "Truth": [], "Hypothesis": [], "Grounded": []})

        results = retrieve_knowledge("test", active_only=True, client=client)
        assert len(results) == 1
        assert results[0].entry_id == "active-1"

    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_includes_deprecated_when_disabled(self, mock_ensure, mock_embed):
        deprecated_obj = _mock_weaviate_result(
            "dep-1", "Deprecated", "test",
            KnowledgeTier.FINDING, confidence=0.5, distance=0.1,
            status="deprecated"
        )

        client = _setup_client({"Finding": [deprecated_obj], "Truth": [], "Hypothesis": [], "Grounded": []})

        results = retrieve_knowledge("test", active_only=False, client=client)
        assert len(results) == 1

    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_min_confidence_filter(self, mock_ensure, mock_embed):
        low_conf = _mock_weaviate_result(
            "low-1", "Low confidence", "test",
            KnowledgeTier.FINDING, confidence=0.2, distance=0.1
        )
        high_conf = _mock_weaviate_result(
            "high-1", "High confidence", "test",
            KnowledgeTier.FINDING, confidence=0.8, distance=0.1
        )

        client = _setup_client({"Finding": [low_conf, high_conf], "Truth": [], "Hypothesis": [], "Grounded": []})

        results = retrieve_knowledge("test", min_confidence=0.5, client=client)
        assert len(results) == 1
        assert results[0].entry_id == "high-1"

    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_respects_top_k(self, mock_ensure, mock_embed):
        objs = [
            _mock_weaviate_result(
                f"entry-{i}", f"Statement {i}", "test",
                KnowledgeTier.FINDING, confidence=0.5, distance=0.1 * i
            )
            for i in range(5)
        ]

        client = _setup_client({"Finding": objs, "Truth": [], "Hypothesis": [], "Grounded": []})

        results = retrieve_knowledge("test", top_k=2, client=client)
        assert len(results) == 2

    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_searches_only_requested_tiers(self, mock_ensure, mock_embed):
        truth_obj = _mock_weaviate_result(
            "truth-1", "Truth", "test",
            KnowledgeTier.TRUTH, confidence=0.8, distance=0.1
        )
        finding_obj = _mock_weaviate_result(
            "find-1", "Finding", "test",
            KnowledgeTier.FINDING, confidence=0.5, distance=0.1
        )

        client = _setup_client({"Truth": [truth_obj], "Finding": [finding_obj], "Hypothesis": [], "Grounded": []})

        results = retrieve_knowledge(
            "test",
            tiers=[KnowledgeTier.TRUTH],
            client=client,
        )

        # Should only have truth results
        assert all(r.tier == KnowledgeTier.TRUTH for r in results)


class TestRetrieveForAccount:
    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_returns_dual_scope(self, mock_ensure, mock_embed):
        obj = _mock_weaviate_result(
            "entry-1", "Test", "test",
            KnowledgeTier.FINDING, confidence=0.5, distance=0.1
        )

        client = _setup_client({"Finding": [obj], "Truth": [], "Hypothesis": [], "Grounded": []})

        result = retrieve_for_account("test", account_id="acct-123", client=client)

        assert "account" in result
        assert "community" in result
        assert isinstance(result["account"], list)
        assert isinstance(result["community"], list)


class TestWeightedScoring:
    def test_tier_weight_ordering(self):
        """Verify tier weights are in correct order."""
        assert TIER_WEIGHTS[KnowledgeTier.GROUNDED] > TIER_WEIGHTS[KnowledgeTier.TRUTH]
        assert TIER_WEIGHTS[KnowledgeTier.TRUTH] > TIER_WEIGHTS[KnowledgeTier.FINDING]
        assert TIER_WEIGHTS[KnowledgeTier.FINDING] > TIER_WEIGHTS[KnowledgeTier.HYPOTHESIS]

    @patch("llm_pipeline.knowledge.retrieval._embed", return_value=[0.1] * 384)
    @patch("llm_pipeline.knowledge.retrieval.ensure_tenant")
    def test_grounded_outranks_hypothesis(self, mock_ensure, mock_embed):
        """Even with same similarity, grounded should outrank hypothesis."""
        grounded_obj = _mock_weaviate_result(
            "grounded-1", "Domain fact", "test",
            KnowledgeTier.GROUNDED, confidence=1.0, distance=0.3
        )
        hyp_obj = _mock_weaviate_result(
            "hyp-1", "Just a guess", "test",
            KnowledgeTier.HYPOTHESIS, confidence=0.1, distance=0.3
        )

        client = _setup_client({
            "Grounded": [grounded_obj],
            "Hypothesis": [hyp_obj],
            "Finding": [],
            "Truth": [],
        })

        results = retrieve_knowledge("test", client=client)
        assert results[0].tier == KnowledgeTier.GROUNDED
