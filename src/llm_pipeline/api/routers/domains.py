"""Domain metadata and application enum endpoints."""

from fastapi import APIRouter

from llm_pipeline.agents.domain_registry import get_all_domains
from llm_pipeline.agents.models import FindingStatus, ReviewAction, ReviewAssessment
from llm_pipeline.agents.storage_models import InvestigationRunStatus
from llm_pipeline.knowledge.models import KnowledgeTier
from llm_pipeline.knowledge.retrieval import TIER_WEIGHTS

router = APIRouter(tags=["domains"])


@router.get("/domains")
def list_domains():
    """Return all registered domains with their ML data type schemas."""
    domains = get_all_domains()
    result = []

    for name, manifest in domains.items():
        roles = [{"name": r.name, "prompt_supplement": r.prompt_supplement} for r in manifest.roles]

        # Build ML data types schema — domain-specific
        ml_data_types = {}
        if name == "email_delivery":
            from llm_pipeline.email_analytics.models import (
                AnomalyType,
                DeliveryStatus,
                SmtpCategory,
                TrendDirection,
            )

            ml_data_types = {
                "dimensions": [
                    "listid",
                    "recipient_domain",
                    "outmtaid",
                    "engagement_segment",
                    "listid_type",
                    "compliance_status",
                    "xmrid_account_id",
                    "smtp_category",
                ],
                "metrics": [
                    "delivery_rate",
                    "bounce_rate",
                    "deferral_rate",
                    "complaint_rate",
                    "pre_edge_latency_mean",
                    "delivery_time_mean",
                ],
                "delivery_statuses": [s.value for s in DeliveryStatus],
                "smtp_categories": [s.value for s in SmtpCategory],
                "anomaly_types": [a.value for a in AnomalyType],
                "trend_directions": [d.value for d in TrendDirection],
                "completeness_fields": [
                    "clicktrackingid",
                    "xmrid_account_id",
                    "xmrid_contact_id",
                    "last_active_ts",
                    "contact_added_ts",
                    "op_queue_time_parsed",
                ],
                "segment_thresholds": {
                    "VH": 0.95,
                    "H": 0.90,
                    "M": 0.85,
                    "L": 0.75,
                    "VL": 0.60,
                },
            }

        result.append(
            {
                "name": name,
                "description": manifest.description,
                "roles": roles,
                "ml_data_types": ml_data_types,
            }
        )

    return result


@router.get("/meta")
def get_meta():
    """Return application enums and static metadata."""
    return {
        "finding_statuses": [s.value for s in FindingStatus],
        "review_assessments": [a.value for a in ReviewAssessment],
        "review_actions": [a.value for a in ReviewAction],
        "knowledge_tiers": [
            {
                "name": t.value,
                "weight": TIER_WEIGHTS[t],
                "description": {
                    KnowledgeTier.GROUNDED: "Authoritative domain knowledge (read-only)",
                    KnowledgeTier.TRUTH: "ML + LLM + human confirmed",
                    KnowledgeTier.FINDING: "ML-tested, evidence attached",
                    KnowledgeTier.HYPOTHESIS: "LLM-generated, untested",
                }[t],
                "color": {
                    KnowledgeTier.GROUNDED: "emerald",
                    KnowledgeTier.TRUTH: "blue",
                    KnowledgeTier.FINDING: "amber",
                    KnowledgeTier.HYPOTHESIS: "gray",
                }[t],
            }
            for t in KnowledgeTier
        ],
        "run_statuses": [s.value for s in InvestigationRunStatus],
        "commands": ["analyze_email", "investigate"],
    }
