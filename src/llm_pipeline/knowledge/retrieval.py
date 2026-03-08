"""Knowledge store read path — tier-weighted retrieval.

Searches Weaviate across knowledge tiers with confidence-weighted scoring.
Higher tiers (truth, grounded) are weighted more heavily than lower tiers.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import weaviate.classes.query as wq

from llm_pipeline.knowledge.models import (
    DeprecationStatus,
    KnowledgeScope,
    KnowledgeTier,
)
from llm_pipeline.knowledge.weaviate_schema import TIER_COLLECTIONS, ensure_tenant

logger = logging.getLogger(__name__)

# Tier-based score weighting — higher tiers contribute more
TIER_WEIGHTS: dict[KnowledgeTier, float] = {
    KnowledgeTier.GROUNDED: 1.0,
    KnowledgeTier.TRUTH: 0.85,
    KnowledgeTier.FINDING: 0.6,
    KnowledgeTier.HYPOTHESIS: 0.3,
}


@dataclass
class KnowledgeResult:
    """A single result from knowledge retrieval."""

    entry_id: str
    tier: KnowledgeTier
    statement: str
    topic: str = ""
    dimension: str = ""
    dimension_value: str = ""
    scope: str = ""
    account_id: str = ""
    confidence: float = 0.0
    observation_count: int = 1
    similarity: float = 0.0
    weighted_score: float = 0.0
    finding_status: str = ""
    source_run_ids: list[str] = field(default_factory=list)


def _embed(text: str) -> list[float]:
    """Compute embedding vector for query text."""
    from llm_pipeline.rag.ingest import get_embeddings

    return get_embeddings().embed_query(text)


def retrieve_knowledge(
    query: str,
    scope: KnowledgeScope = KnowledgeScope.COMMUNITY,
    account_id: str = "",
    tiers: list[KnowledgeTier] | None = None,
    top_k: int = 10,
    min_confidence: float = 0.0,
    active_only: bool = True,
    client: "weaviate.WeaviateClient | None" = None,
) -> list[KnowledgeResult]:
    """Search knowledge store with tier-weighted scoring.

    Searches each requested tier separately, applies tier-based weighting,
    merges and re-sorts by weighted score. Returns top_k results.
    """
    logger.debug(
        "retrieve_knowledge started query=%.80s scope=%s top_k=%d", query, scope.value, top_k
    )
    t0 = time.monotonic()
    if client is None:
        from llm_pipeline.knowledge.store import get_weaviate_client

        client = get_weaviate_client()

    tiers = tiers or list(KnowledgeTier)
    vector = _embed(query)
    tenant_name = account_id if (scope == KnowledgeScope.ACCOUNT and account_id) else "community"

    all_results: list[KnowledgeResult] = []

    for tier in tiers:
        collection_name = TIER_COLLECTIONS[tier]

        try:
            ensure_tenant(client, collection_name, tenant_name)
            collection = client.collections.get(collection_name).with_tenant(tenant_name)

            results = collection.query.near_vector(
                near_vector=vector,
                limit=top_k,
                return_metadata=["distance"],
                return_properties=[
                    "entry_id",
                    "statement",
                    "topic",
                    "dimension",
                    "dimension_value",
                    "scope",
                    "account_id",
                    "confidence",
                    "observation_count",
                    "status",
                    "source_run_ids",
                ]
                + (["finding_status"] if tier == KnowledgeTier.FINDING else []),
            )

            tier_weight = TIER_WEIGHTS[tier]

            for obj in results.objects:
                props = obj.properties
                distance = (
                    obj.metadata.distance
                    if obj.metadata and obj.metadata.distance is not None
                    else 1.0
                )
                similarity = max(0.0, 1.0 - distance)

                # Filter by status
                status = props.get("status", "active")
                if active_only and status != DeprecationStatus.ACTIVE.value:
                    continue

                confidence = props.get("confidence", 0.0) or 0.0

                # Filter by min_confidence
                if confidence < min_confidence:
                    continue

                weighted_score = similarity * tier_weight * max(confidence, 0.01)

                all_results.append(
                    KnowledgeResult(
                        entry_id=props.get("entry_id", ""),
                        tier=tier,
                        statement=props.get("statement", ""),
                        topic=props.get("topic", ""),
                        dimension=props.get("dimension", ""),
                        dimension_value=props.get("dimension_value", ""),
                        scope=props.get("scope", ""),
                        account_id=props.get("account_id", ""),
                        confidence=confidence,
                        observation_count=props.get("observation_count", 1) or 1,
                        similarity=similarity,
                        weighted_score=weighted_score,
                        finding_status=props.get("finding_status", ""),
                        source_run_ids=props.get("source_run_ids") or [],
                    )
                )

        except Exception as e:
            logger.debug("Error searching tier %s: %s", tier.value, e)
            continue

    # Sort by weighted score descending
    all_results.sort(key=lambda r: r.weighted_score, reverse=True)
    final = all_results[:top_k]
    logger.debug(
        "retrieve_knowledge completed results=%d elapsed_s=%.2f", len(final), time.monotonic() - t0
    )
    return final


def retrieve_for_account(
    query: str,
    account_id: str,
    tiers: list[KnowledgeTier] | None = None,
    top_k: int = 10,
    min_confidence: float = 0.0,
    active_only: bool = True,
    client: "weaviate.WeaviateClient | None" = None,
) -> dict[str, list[KnowledgeResult]]:
    """Retrieve knowledge for both account and community scopes.

    Returns {"account": [...], "community": [...]}.
    Enables comparison: "Account X has this finding, community baseline says Y".
    """
    account_results = retrieve_knowledge(
        query=query,
        scope=KnowledgeScope.ACCOUNT,
        account_id=account_id,
        tiers=tiers,
        top_k=top_k,
        min_confidence=min_confidence,
        active_only=active_only,
        client=client,
    )

    community_results = retrieve_knowledge(
        query=query,
        scope=KnowledgeScope.COMMUNITY,
        tiers=tiers,
        top_k=top_k,
        min_confidence=min_confidence,
        active_only=active_only,
        client=client,
    )

    return {
        "account": account_results,
        "community": community_results,
    }
