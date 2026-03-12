"""Weaviate collection schema for the four-tier knowledge hierarchy.

Each tier gets its own collection with multi-tenancy enabled.
Tenants = account_id for account-scoped entries, "community" for community scope.
Embeddings are computed client-side via get_embeddings() — Weaviate stores raw vectors.
"""

from __future__ import annotations

import logging

import weaviate
import weaviate.classes.config as wvc
from weaviate.classes.tenants import Tenant, TenantActivityStatus

from llm_pipeline.knowledge.models import KnowledgeTier

logger = logging.getLogger(__name__)

# Collection names by tier
TIER_COLLECTIONS: dict[KnowledgeTier, str] = {
    KnowledgeTier.HYPOTHESIS: "Hypothesis",
    KnowledgeTier.FINDING: "Finding",
    KnowledgeTier.TRUTH: "Truth",
    KnowledgeTier.GROUNDED: "Grounded",
}

# Also a collection for summarization documents (outside knowledge hierarchy)
SUMMARIZATION_COLLECTION = "SummarizationDocument"

# Also a collection for RAG documents
RAG_COLLECTION = "RagDocument"

# Base properties shared by all knowledge tier collections
_BASE_PROPERTIES = [
    wvc.Property(name="entry_id", data_type=wvc.DataType.TEXT),
    wvc.Property(name="statement", data_type=wvc.DataType.TEXT),
    wvc.Property(name="topic", data_type=wvc.DataType.TEXT),
    wvc.Property(name="dimension", data_type=wvc.DataType.TEXT),
    wvc.Property(name="dimension_value", data_type=wvc.DataType.TEXT),
    wvc.Property(name="scope", data_type=wvc.DataType.TEXT),
    wvc.Property(name="account_id", data_type=wvc.DataType.TEXT),
    wvc.Property(name="status", data_type=wvc.DataType.TEXT),
    wvc.Property(name="confidence", data_type=wvc.DataType.NUMBER),
    wvc.Property(name="observation_count", data_type=wvc.DataType.INT),
    wvc.Property(name="first_observed", data_type=wvc.DataType.TEXT),
    wvc.Property(name="last_observed", data_type=wvc.DataType.TEXT),
    wvc.Property(name="temporal_span_days", data_type=wvc.DataType.INT),
    wvc.Property(name="source_run_ids", data_type=wvc.DataType.TEXT_ARRAY),
    wvc.Property(name="created_at", data_type=wvc.DataType.TEXT),
    wvc.Property(name="domain_name", data_type=wvc.DataType.TEXT),
]

# Extra properties for Finding collection
_FINDING_EXTRA = [
    wvc.Property(name="finding_status", data_type=wvc.DataType.TEXT),
]


def _create_collection(
    client: weaviate.WeaviateClient,
    name: str,
    extra_properties: list[wvc.Property] | None = None,
) -> None:
    """Create a single multi-tenant collection (idempotent)."""
    if client.collections.exists(name):
        logger.debug("Collection %s already exists, skipping", name)
        return

    properties = list(_BASE_PROPERTIES)
    if extra_properties:
        properties.extend(extra_properties)

    client.collections.create(
        name=name,
        multi_tenancy_config=wvc.Configure.multi_tenancy(
            enabled=True,
            auto_tenant_creation=True,
            auto_tenant_activation=True,
        ),
        vectorizer_config=wvc.Configure.Vectorizer.none(),
        properties=properties,
    )
    logger.info("Created Weaviate collection: %s", name)


def init_weaviate(client: weaviate.WeaviateClient) -> None:
    """Create all knowledge tier collections (idempotent).

    Call on startup to ensure schema exists.
    """
    for tier, name in TIER_COLLECTIONS.items():
        extra = _FINDING_EXTRA if tier == KnowledgeTier.FINDING else None
        _create_collection(client, name, extra)

    # Summarization document collection (flat, no tier hierarchy)
    _create_collection(
        client,
        SUMMARIZATION_COLLECTION,
        extra_properties=[
            wvc.Property(name="title", data_type=wvc.DataType.TEXT),
            wvc.Property(name="document_type", data_type=wvc.DataType.TEXT),
            wvc.Property(name="run_id", data_type=wvc.DataType.TEXT),
            wvc.Property(name="chunk_index", data_type=wvc.DataType.INT),
            wvc.Property(name="chunk_total", data_type=wvc.DataType.INT),
        ],
    )

    # RAG document collection
    _create_collection(
        client,
        RAG_COLLECTION,
        extra_properties=[
            wvc.Property(name="source", data_type=wvc.DataType.TEXT),
            wvc.Property(name="chunk_index", data_type=wvc.DataType.INT),
            wvc.Property(name="chunk_total", data_type=wvc.DataType.INT),
        ],
    )

    logger.info("Weaviate schema initialized (%d knowledge + 2 utility collections)", len(TIER_COLLECTIONS))


def ensure_tenant(client: weaviate.WeaviateClient, collection_name: str, tenant_name: str) -> None:
    """Ensure a tenant exists on a collection (idempotent hot-add)."""
    collection = client.collections.get(collection_name)
    existing = collection.tenants.get()
    if tenant_name in existing:
        # Ensure active
        tenant = existing[tenant_name]
        if tenant.activity_status != TenantActivityStatus.ACTIVE:
            collection.tenants.update([Tenant(name=tenant_name, activity_status=TenantActivityStatus.ACTIVE)])
        return
    collection.tenants.create([Tenant(name=tenant_name)])
    logger.debug("Created tenant %s on collection %s", tenant_name, collection_name)
