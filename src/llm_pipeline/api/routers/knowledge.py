"""Knowledge store search, stats, and write endpoints."""

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from llm_pipeline.api.dependencies import get_db, get_weaviate
from llm_pipeline.knowledge.models import (
    KnowledgeAnnotationRecord,
    KnowledgeAuditRecord,
    KnowledgeTier,
)
from llm_pipeline.knowledge.retrieval import TIER_WEIGHTS, retrieve_knowledge
from llm_pipeline.knowledge.weaviate_schema import TIER_COLLECTIONS, ensure_tenant

router = APIRouter(tags=["knowledge"])
logger = logging.getLogger(__name__)


@router.get("/knowledge/search")
def search_knowledge(
    q: str = Query(""),
    tier: str | None = Query(None),
    domain: str | None = Query(None),
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
        return _browse_entries(tier_list, offset, limit, client, domain_name=domain or "")

    fetch_k = max(offset + limit, top_k)
    fetch_k = min(fetch_k, 500)

    results = retrieve_knowledge(
        query=q,
        tiers=tier_list,
        top_k=fetch_k,
        domain_name=domain or "",
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
                "domain_name": r.domain_name or None,
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
    domain_name: str = "",
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
            browse_props = _BROWSE_PROPS + ["domain_name"] + (["finding_status"] if t == KnowledgeTier.FINDING else [])

            for obj in collection.iterator(return_properties=browse_props):
                obj_props = obj.properties
                # Filter by domain if specified
                if domain_name and (obj_props.get("domain_name", "") or "") != domain_name:
                    continue
                confidence = float(obj_props.get("confidence", 0.0) or 0.0)
                all_entries.append({
                    "entry_id": obj_props.get("entry_id", ""),
                    "tier": t.value,
                    "statement": obj_props.get("statement", ""),
                    "topic": obj_props.get("topic", ""),
                    "dimension": obj_props.get("dimension") or None,
                    "dimension_value": obj_props.get("dimension_value") or None,
                    "scope": obj_props.get("scope", "community"),
                    "account_id": obj_props.get("account_id") or None,
                    "confidence": confidence,
                    "observation_count": int(obj_props.get("observation_count", 1) or 1),
                    "similarity": 0.0,
                    "weighted_score": confidence * tier_weight,
                    "finding_status": obj_props.get("finding_status") or None,
                    "domain_name": obj_props.get("domain_name") or None,
                    "source_run_ids": obj_props.get("source_run_ids", []) or [],
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


# ---------------------------------------------------------------------------
# Write endpoints — promote, deprecate, annotate, history
# ---------------------------------------------------------------------------


class PromoteRequest(BaseModel):
    entry_id: str
    reviewer: str
    notes: str = ""


class DeprecateRequest(BaseModel):
    entry_id: str
    tier: str
    reason: str = ""
    actor: str = "human"


class AnnotateRequest(BaseModel):
    actor: str
    text: str


@router.post("/knowledge/promote")
def promote_finding_to_truth(
    body: PromoteRequest,
    client=Depends(get_weaviate),
):
    """Promote a finding to truth tier (human-gated)."""
    from llm_pipeline.knowledge.store import promote_to_truth

    try:
        truth_id = promote_to_truth(
            finding_id=body.entry_id,
            reviewer=body.reviewer,
            notes=body.notes,
            client=client,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error("promote_to_truth failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"truth_entry_id": truth_id, "promoted_from": body.entry_id}


@router.post("/knowledge/deprecate")
def deprecate_entry(
    body: DeprecateRequest,
    client=Depends(get_weaviate),
):
    """Deprecate a knowledge entry (any tier)."""
    from llm_pipeline.knowledge.store import deprecate

    try:
        tier = KnowledgeTier(body.tier)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Unknown tier: {body.tier}")

    try:
        deprecate(
            entry_id=body.entry_id,
            tier=tier,
            reason=body.reason,
            client=client,
        )
    except Exception as e:
        logger.error("deprecate failed: %s", e)
        raise HTTPException(status_code=500, detail=str(e))

    return {"entry_id": body.entry_id, "status": "deprecated"}


@router.post("/knowledge/{entry_id}/annotate")
def annotate_entry(
    entry_id: str,
    body: AnnotateRequest,
    db: Session = Depends(get_db),
):
    """Add a human annotation to a knowledge entry."""
    record = KnowledgeAnnotationRecord(
        entry_id=entry_id,
        actor=body.actor,
        text=body.text,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    return {"annotation_id": record.id}


@router.get("/knowledge/{entry_id}/history")
def entry_history(
    entry_id: str,
    db: Session = Depends(get_db),
):
    """Get combined audit + annotation timeline for a knowledge entry."""
    # Audit records
    audit_rows = (
        db.execute(
            select(KnowledgeAuditRecord)
            .where(KnowledgeAuditRecord.entry_id == entry_id)
            .order_by(KnowledgeAuditRecord.created_at)
        )
        .scalars()
        .all()
    )

    # Annotation records
    annotation_rows = (
        db.execute(
            select(KnowledgeAnnotationRecord)
            .where(KnowledgeAnnotationRecord.entry_id == entry_id)
            .order_by(KnowledgeAnnotationRecord.created_at)
        )
        .scalars()
        .all()
    )

    events = []
    for a in audit_rows:
        events.append({
            "type": "audit",
            "action": a.action,
            "from_tier": a.from_tier,
            "to_tier": a.to_tier,
            "actor": a.actor,
            "reason": a.reason,
            "created_at": a.created_at,
        })
    for n in annotation_rows:
        events.append({
            "type": "annotation",
            "actor": n.actor,
            "text": n.text,
            "created_at": n.created_at,
        })

    # Sort combined timeline by created_at
    events.sort(key=lambda e: e["created_at"] or "")

    return {"entry_id": entry_id, "events": events}
