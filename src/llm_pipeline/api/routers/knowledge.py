"""Knowledge store search and stats endpoints."""

import logging

from fastapi import APIRouter, Depends, Query

from llm_pipeline.api.dependencies import get_weaviate
from llm_pipeline.knowledge.models import KnowledgeTier
from llm_pipeline.knowledge.retrieval import TIER_WEIGHTS, retrieve_knowledge
from llm_pipeline.knowledge.weaviate_schema import TIER_COLLECTIONS

router = APIRouter(tags=["knowledge"])
logger = logging.getLogger(__name__)


@router.get("/knowledge/search")
def search_knowledge(
    q: str = Query(..., min_length=1),
    tier: str | None = Query(None),
    top_k: int = Query(10, ge=1, le=100),
    client=Depends(get_weaviate),
):
    """Search the knowledge store with tier-weighted scoring."""
    tiers = None
    if tier:
        try:
            tiers = [KnowledgeTier(tier)]
        except ValueError:
            return {"results": [], "error": f"Unknown tier: {tier}"}

    results = retrieve_knowledge(
        query=q,
        tiers=tiers,
        top_k=top_k,
        client=client,
    )

    return {
        "results": [
            {
                "entry_id": r.entry_id,
                "tier": r.tier.value,
                "statement": r.statement,
                "topic": r.topic,
                "dimension": r.dimension,
                "dimension_value": r.dimension_value,
                "scope": r.scope,
                "account_id": r.account_id,
                "confidence": r.confidence,
                "observation_count": r.observation_count,
                "similarity": r.similarity,
                "weighted_score": r.weighted_score,
                "finding_status": r.finding_status,
                "source_run_ids": r.source_run_ids,
            }
            for r in results
        ]
    }


@router.get("/knowledge/stats")
def knowledge_stats(client=Depends(get_weaviate)):
    """Get knowledge store entry counts by tier."""
    stats = []
    descriptions = {
        KnowledgeTier.GROUNDED: "Authoritative domain knowledge (read-only)",
        KnowledgeTier.TRUTH: "ML + LLM + human confirmed",
        KnowledgeTier.FINDING: "ML-tested, evidence attached",
        KnowledgeTier.HYPOTHESIS: "LLM-generated, untested",
    }

    for tier in KnowledgeTier:
        collection_name = TIER_COLLECTIONS[tier]
        count = 0
        try:
            collection = client.collections.get(collection_name).with_tenant("community")
            agg = collection.aggregate.over_all(total_count=True)
            count = agg.total_count or 0
        except Exception as e:
            logger.debug("Could not count %s: %s", collection_name, e)

        stats.append(
            {
                "tier": tier.value,
                "collection": collection_name,
                "count": count,
                "weight": TIER_WEIGHTS[tier],
                "description": descriptions[tier],
            }
        )

    return stats
