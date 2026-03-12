"""Knowledge store search and stats endpoints."""

import logging

from fastapi import APIRouter, Depends, Query

from llm_pipeline.api.dependencies import get_weaviate
from llm_pipeline.knowledge.models import KnowledgeTier
from llm_pipeline.knowledge.retrieval import TIER_WEIGHTS, retrieve_knowledge
from llm_pipeline.knowledge.weaviate_schema import TIER_COLLECTIONS, ensure_tenant

router = APIRouter(tags=["knowledge"])
logger = logging.getLogger(__name__)


@router.get("/knowledge/search")
def search_knowledge(
    q: str = Query(""),
    tier: str | None = Query(None),
    top_k: int = Query(10, ge=1, le=500),
    offset: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    client=Depends(get_weaviate),
):
    """Search the knowledge store with tier-weighted scoring and pagination."""
    tier_list = None
    if tier:
        try:
            tier_list = [KnowledgeTier(tier)]
        except ValueError:
            return {"total": 0, "results": [], "error": f"Unknown tier: {tier}"}

    # No query → browse mode: fetch entries without vector search
    if not q.strip():
        return _browse_entries(tier_list, offset, limit, client)

    fetch_k = max(offset + limit, top_k)
    fetch_k = min(fetch_k, 500)

    results = retrieve_knowledge(
        query=q,
        tiers=tier_list,
        top_k=fetch_k,
        client=client,
    )

    total = len(results)
    paginated = results[offset : offset + limit]

    return {
        "total": total,
        "results": [
            {
                "entry_id": r.entry_id,
                "tier": r.tier.value,
                "statement": r.statement,
                "topic": r.topic,
                "dimension": r.dimension or None,
                "dimension_value": r.dimension_value or None,
                "scope": r.scope,
                "account_id": r.account_id or None,
                "confidence": r.confidence,
                "observation_count": r.observation_count,
                "similarity": r.similarity,
                "weighted_score": r.weighted_score,
                "finding_status": r.finding_status or None,
                "source_run_ids": r.source_run_ids,
            }
            for r in paginated
        ],
    }


_BROWSE_PROPS = [
    "entry_id", "statement", "topic", "dimension", "dimension_value",
    "scope", "account_id", "confidence", "observation_count",
    "status", "source_run_ids",
]


def _browse_entries(
    tiers: list[KnowledgeTier] | None,
    offset: int,
    limit: int,
    client,
) -> dict:
    """List knowledge entries without a vector query (browse mode)."""
    tiers = tiers or list(KnowledgeTier)
    all_entries = []

    for t in tiers:
        collection_name = TIER_COLLECTIONS[t]
        try:
            ensure_tenant(client, collection_name, "community")
            collection = client.collections.get(collection_name).with_tenant("community")
            tier_weight = TIER_WEIGHTS[t]
            props = _BROWSE_PROPS + (["finding_status"] if t == KnowledgeTier.FINDING else [])

            for obj in collection.iterator(return_properties=props):
                props = obj.properties
                confidence = float(props.get("confidence", 0.0) or 0.0)
                all_entries.append({
                    "entry_id": props.get("entry_id", ""),
                    "tier": t.value,
                    "statement": props.get("statement", ""),
                    "topic": props.get("topic", ""),
                    "dimension": props.get("dimension") or None,
                    "dimension_value": props.get("dimension_value") or None,
                    "scope": props.get("scope", "community"),
                    "account_id": props.get("account_id") or None,
                    "confidence": confidence,
                    "observation_count": int(props.get("observation_count", 1) or 1),
                    "similarity": 0.0,
                    "weighted_score": confidence * tier_weight,
                    "finding_status": props.get("finding_status") or None,
                    "source_run_ids": props.get("source_run_ids", []) or [],
                })
        except Exception as e:
            logger.warning("Could not browse %s: %s", collection_name, e)

    all_entries.sort(key=lambda e: e["weighted_score"], reverse=True)
    total = len(all_entries)
    paginated = all_entries[offset : offset + limit]

    return {"total": total, "results": paginated}


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
