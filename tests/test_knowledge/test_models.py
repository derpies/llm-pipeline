"""Tests for knowledge tier models — Pydantic and SQLAlchemy."""

from datetime import UTC, datetime

from llm_pipeline.agents.models import Finding, FindingStatus, Hypothesis
from llm_pipeline.knowledge.models import (
    DeprecationStatus,
    FindingEntry,
    GroundedEntry,
    HypothesisEntry,
    KnowledgeAuditRecord,
    KnowledgeScope,
    KnowledgeTier,
    TruthEntry,
    compute_confidence,
)


class TestConfidenceComputation:
    def test_hypothesis_confidence(self):
        assert compute_confidence(KnowledgeTier.HYPOTHESIS) == 0.1

    def test_finding_confirmed_base(self):
        c = compute_confidence(KnowledgeTier.FINDING, finding_status="confirmed", observation_count=1)
        assert 0.3 <= c <= 0.6

    def test_finding_confirmed_high_observations(self):
        c = compute_confidence(KnowledgeTier.FINDING, finding_status="confirmed", observation_count=100)
        assert c == 0.6  # capped

    def test_finding_disproven(self):
        assert compute_confidence(KnowledgeTier.FINDING, finding_status="disproven") == 0.0

    def test_truth_base(self):
        c = compute_confidence(KnowledgeTier.TRUTH, temporal_span_days=0)
        assert c == 0.7

    def test_truth_long_span(self):
        c = compute_confidence(KnowledgeTier.TRUTH, temporal_span_days=365)
        assert abs(c - 0.9) < 1e-9  # capped

    def test_grounded_always_one(self):
        assert compute_confidence(KnowledgeTier.GROUNDED) == 1.0


class TestKnowledgeEntryModels:
    def test_hypothesis_entry_construction(self):
        entry = HypothesisEntry(statement="Test hypothesis", topic="bounce_rate")
        assert entry.tier == KnowledgeTier.HYPOTHESIS
        assert entry.confidence == 0.0  # not yet computed
        entry.recompute_confidence()
        assert entry.confidence == 0.1
        assert entry.tenant_name == "community"

    def test_finding_entry_construction(self):
        entry = FindingEntry(
            statement="Delivery rate dropped",
            topic="delivery_rate",
            finding_status="confirmed",
            observation_count=5,
        )
        entry.recompute_confidence()
        assert 0.3 < entry.confidence <= 0.6

    def test_truth_entry_construction(self):
        entry = TruthEntry(
            statement="Confirmed truth",
            topic="compliance",
            temporal_span_days=180,
            human_reviewer="admin",
        )
        entry.recompute_confidence()
        assert 0.7 < entry.confidence <= 0.9

    def test_grounded_entry_construction(self):
        entry = GroundedEntry(
            statement="Domain fact",
            source_document="log-field-reference.md",
            source_section="listid",
        )
        entry.recompute_confidence()
        assert entry.confidence == 1.0

    def test_account_scope_tenant(self):
        entry = HypothesisEntry(
            statement="Per-account",
            scope=KnowledgeScope.ACCOUNT,
            account_id="12345",
        )
        assert entry.tenant_name == "12345"

    def test_community_scope_tenant(self):
        entry = FindingEntry(
            statement="Community finding",
            scope=KnowledgeScope.COMMUNITY,
            finding_status="confirmed",
        )
        assert entry.tenant_name == "community"

    def test_embedding_text_with_topic(self):
        entry = HypothesisEntry(statement="rate dropped", topic="bounce_rate")
        assert entry.embedding_text == "bounce_rate: rate dropped"

    def test_embedding_text_no_topic(self):
        entry = HypothesisEntry(statement="rate dropped")
        assert entry.embedding_text == "rate dropped"


class TestFromInvestigationModels:
    def test_from_investigation_finding(self):
        now = datetime.now(UTC)
        f = Finding(
            topic_title="Delivery Rate",
            statement="Delivery rate dropped 10% for VH segment",
            status=FindingStatus.CONFIRMED,
            evidence=["z-score=4.2", "baseline=0.95"],
            metrics_cited={"delivery_rate": 0.855},
            created_at=now,
            run_id="run-001",
        )
        entry = FindingEntry.from_investigation_finding(f)
        assert entry.tier == KnowledgeTier.FINDING
        assert entry.finding_status == "confirmed"
        assert entry.topic == "Delivery Rate"
        assert entry.statement == f.statement
        assert entry.evidence == ["z-score=4.2", "baseline=0.95"]
        assert entry.metrics_cited == {"delivery_rate": 0.855}
        assert entry.source_run_ids == ["run-001"]
        assert entry.confidence > 0.0

    def test_from_investigation_finding_disproven(self):
        f = Finding(
            topic_title="Test",
            statement="Disproven thing",
            status=FindingStatus.DISPROVEN,
            created_at=datetime.now(UTC),
        )
        entry = FindingEntry.from_investigation_finding(f)
        assert entry.confidence == 0.0
        assert entry.finding_status == "disproven"

    def test_from_investigation_hypothesis(self):
        now = datetime.now(UTC)
        h = Hypothesis(
            topic_title="Compliance Check",
            statement="Non-compliant senders may cause pool reputation drop",
            reasoning="Shared IP pools are affected by worst sender",
            created_at=now,
            run_id="run-002",
        )
        entry = HypothesisEntry.from_investigation_hypothesis(h)
        assert entry.tier == KnowledgeTier.HYPOTHESIS
        assert entry.reasoning == h.reasoning
        assert entry.source_run_ids == ["run-002"]
        assert entry.confidence == 0.1

    def test_from_investigation_with_account_scope(self):
        f = Finding(
            topic_title="Test",
            statement="Account-specific",
            status=FindingStatus.CONFIRMED,
            created_at=datetime.now(UTC),
            run_id="run-003",
        )
        entry = FindingEntry.from_investigation_finding(
            f, scope=KnowledgeScope.ACCOUNT, account_id="acct-99"
        )
        assert entry.scope == KnowledgeScope.ACCOUNT
        assert entry.account_id == "acct-99"
        assert entry.tenant_name == "acct-99"


class TestAuditRecord:
    def test_audit_record_creation(self):
        record = KnowledgeAuditRecord(
            entry_id="abc-123",
            action="created",
            from_tier=None,
            to_tier="hypothesis",
            actor="system",
            reason="Initial investigation",
        )
        assert record.entry_id == "abc-123"
        assert record.action == "created"
        assert record.to_tier == "hypothesis"
        assert record.__tablename__ == "knowledge_audit"
        assert record.__table_args__ == {"schema": "knowledge"}
