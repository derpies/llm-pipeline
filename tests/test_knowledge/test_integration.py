"""End-to-end mock test: Finding -> knowledge entry -> store -> retrieve."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.knowledge.models import (
    FindingEntry,
    HypothesisEntry,
    KnowledgeScope,
    KnowledgeTier,
)
from llm_pipeline.knowledge.store import store_investigation_to_knowledge


class TestEndToEnd:
    @patch("llm_pipeline.knowledge.store.store_finding")
    @patch("llm_pipeline.knowledge.store.store_hypothesis")
    def test_investigation_to_knowledge_roundtrip(self, mock_store_hyp, mock_store_find):
        """Test the full path from investigation output to knowledge entries."""
        mock_store_find.return_value = ("find-001", False)
        mock_store_hyp.return_value = ("hyp-001", False)

        now = datetime.now(UTC)

        findings = [
            Finding(
                topic_title="Delivery Rate VH",
                statement="VH segment delivery rate dropped 8% on Feb 12",
                status=FindingStatus.CONFIRMED,
                evidence=["z-score=4.5", "baseline=0.96, actual=0.88"],
                metrics_cited={"delivery_rate": 0.88, "z_score": 4.5},
                created_at=now,
                run_id="run-test-001",
            ),
            Finding(
                topic_title="Bounce Investigation",
                statement="No significant bounce pattern found for gmail.com",
                status=FindingStatus.DISPROVEN,
                evidence=["bounce_rate=0.02, within normal range"],
                created_at=now,
                run_id="run-test-001",
            ),
        ]

        hypotheses = [
            Hypothesis(
                topic_title="Compliance Impact",
                statement="Non-compliant senders on shared pools may cause cascading reputation damage",
                reasoning="Shared IPs mean one bad sender affects all. Need to correlate accountid compliance with pool delivery rates.",
                created_at=now,
                run_id="run-test-001",
            ),
        ]

        counts = store_investigation_to_knowledge(
            findings=findings,
            hypotheses=hypotheses,
            run_id="run-test-001",
            client=MagicMock(),
        )

        assert counts["stored"] == 3
        assert counts["merged"] == 0

        # Verify FindingEntry was created correctly from first finding
        find_call = mock_store_find.call_args_list[0]
        entry = find_call.args[0]
        assert isinstance(entry, FindingEntry)
        assert entry.finding_status == "confirmed"
        assert entry.source_run_ids == ["run-test-001"]
        assert entry.confidence > 0.0

        # Verify disproven finding
        disproven_call = mock_store_find.call_args_list[1]
        disproven_entry = disproven_call.args[0]
        assert disproven_entry.finding_status == "disproven"
        assert disproven_entry.confidence == 0.0

        # Verify HypothesisEntry
        hyp_call = mock_store_hyp.call_args_list[0]
        hyp_entry = hyp_call.args[0]
        assert isinstance(hyp_entry, HypothesisEntry)
        assert hyp_entry.reasoning == hypotheses[0].reasoning
        assert hyp_entry.confidence == 0.1

    @patch("llm_pipeline.knowledge.store.store_finding")
    @patch("llm_pipeline.knowledge.store.store_hypothesis")
    def test_account_scoped_entries(self, mock_store_hyp, mock_store_find):
        """Test account-scoped knowledge entries."""
        mock_store_find.return_value = ("find-acct", False)

        now = datetime.now(UTC)
        findings = [
            Finding(
                topic_title="Account Test",
                statement="Account 12345 has low compliance",
                status=FindingStatus.CONFIRMED,
                created_at=now,
                run_id="run-acct",
            ),
        ]

        counts = store_investigation_to_knowledge(
            findings=findings,
            hypotheses=[],
            run_id="run-acct",
            scope=KnowledgeScope.ACCOUNT,
            account_id="12345",
            client=MagicMock(),
        )

        assert counts["stored"] == 1
        entry = mock_store_find.call_args_list[0].args[0]
        assert entry.scope == KnowledgeScope.ACCOUNT
        assert entry.account_id == "12345"
        assert entry.tenant_name == "12345"
