"""Knowledge store write operations — embed, store, audit, deduplicate.

Write path for the four-tier knowledge hierarchy. Entries go into Weaviate
(vector storage with multi-tenancy) and Postgres (audit trail).
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime

import weaviate
from sqlalchemy.orm import Session

from llm_pipeline.config import settings
from llm_pipeline.knowledge.models import (
    DeprecationStatus,
    FindingEntry,
    HypothesisEntry,
    KnowledgeAuditRecord,
    KnowledgeEntry,
    KnowledgeScope,
    KnowledgeTier,
    TruthEntry,
)
from llm_pipeline.knowledge.weaviate_schema import (
    TIER_COLLECTIONS,
    ensure_tenant,
    init_weaviate,
)

logger = logging.getLogger(__name__)

_weaviate_client: weaviate.WeaviateClient | None = None


def get_weaviate_client() -> weaviate.WeaviateClient:
    """Return a singleton Weaviate client, connecting lazily."""
    global _weaviate_client
    if _weaviate_client is None or not _weaviate_client.is_connected():
        _weaviate_client = weaviate.connect_to_custom(
            http_host=settings.weaviate_url.replace("http://", "").split(":")[0],
            http_port=int(settings.weaviate_url.split(":")[-1])
            if ":" in settings.weaviate_url.rsplit("//", 1)[-1]
            else 8080,
            http_secure=False,
            grpc_host=settings.weaviate_grpc_url.split(":")[0],
            grpc_port=int(settings.weaviate_grpc_url.split(":")[-1])
            if ":" in settings.weaviate_grpc_url
            else 50051,
            grpc_secure=False,
        )
        init_weaviate(_weaviate_client)
    return _weaviate_client


def _get_db_session() -> Session:
    """Create a new SQLAlchemy session for audit trail."""
    from llm_pipeline.models.db import get_engine

    return Session(get_engine())


def _embed(text: str) -> list[float]:
    """Compute embedding vector for text using configured embedding provider."""
    from llm_pipeline.rag.ingest import get_embeddings

    embeddings = get_embeddings()
    return embeddings.embed_query(text)


def _entry_to_properties(entry: KnowledgeEntry) -> dict:
    """Convert a KnowledgeEntry to Weaviate properties dict."""
    props = {
        "entry_id": entry.id,
        "statement": entry.statement,
        "topic": entry.topic,
        "dimension": entry.dimension,
        "dimension_value": entry.dimension_value,
        "scope": entry.scope.value,
        "account_id": entry.account_id,
        "status": entry.status.value,
        "confidence": entry.confidence,
        "observation_count": entry.observation_count,
        "first_observed": entry.first_observed.isoformat(),
        "last_observed": entry.last_observed.isoformat(),
        "temporal_span_days": entry.temporal_span_days,
        "source_run_ids": entry.source_run_ids,
        "created_at": entry.created_at.isoformat(),
    }
    if isinstance(entry, FindingEntry):
        props["finding_status"] = entry.finding_status
    return props


def _audit(
    session: Session,
    entry_id: str,
    action: str,
    from_tier: str | None = None,
    to_tier: str | None = None,
    actor: str = "system",
    reason: str = "",
    metadata: dict | None = None,
) -> None:
    """Write an audit record to Postgres."""
    record = KnowledgeAuditRecord(
        entry_id=entry_id,
        action=action,
        from_tier=from_tier,
        to_tier=to_tier,
        actor=actor,
        reason=reason,
        metadata_json=json.dumps(metadata or {}),
    )
    session.add(record)


def _find_duplicate(
    client: weaviate.WeaviateClient,
    entry: KnowledgeEntry,
    vector: list[float],
    threshold: float = 0.95,
) -> str | None:
    """Check for existing entry with high similarity in same tier/tenant.

    Returns entry_id of the duplicate if found, None otherwise.
    """
    collection_name = TIER_COLLECTIONS[entry.tier]
    collection = client.collections.get(collection_name).with_tenant(entry.tenant_name)

    try:
        results = collection.query.near_vector(
            near_vector=vector,
            limit=1,
            return_metadata=["distance"],
            return_properties=["entry_id", "topic", "dimension", "dimension_value"],
        )
    except Exception:
        # Collection may be empty or tenant doesn't exist yet
        return None

    if not results.objects:
        return None

    obj = results.objects[0]
    # Weaviate distance: 0 = identical, higher = more different
    # For cosine distance, similarity = 1 - distance
    distance = obj.metadata.distance if obj.metadata and obj.metadata.distance is not None else 1.0
    similarity = 1.0 - distance

    if similarity >= threshold:
        # Also check same topic+dimension+dimension_value
        props = obj.properties
        if (
            props.get("topic") == entry.topic
            and props.get("dimension") == entry.dimension
            and props.get("dimension_value") == entry.dimension_value
        ):
            return props.get("entry_id")

    return None


def store_entry(
    entry: KnowledgeEntry,
    client: weaviate.WeaviateClient | None = None,
    session: Session | None = None,
) -> tuple[str, bool]:
    """Store a knowledge entry. Returns (entry_id, was_merged).

    Checks for duplicates first — if a near-duplicate exists in the same
    tier/tenant, merges observations instead of creating a new entry.
    """
    t0 = time.monotonic()
    client = client or get_weaviate_client()
    own_session = session is None
    session = session or _get_db_session()

    try:
        collection_name = TIER_COLLECTIONS[entry.tier]
        ensure_tenant(client, collection_name, entry.tenant_name)

        vector = _embed(entry.embedding_text)

        # Check for dedup
        existing_id = _find_duplicate(client, entry, vector)
        if existing_id:
            merge_observation(
                entry_id=existing_id,
                tier=entry.tier,
                new_run_id=entry.source_run_ids[0] if entry.source_run_ids else "",
                new_evidence=entry.evidence,
                client=client,
                session=session,
            )
            if own_session:
                session.commit()
            logger.debug(
                "store_entry completed entry_id=%s tier=%s merged=True elapsed_s=%.2f",
                existing_id,
                entry.tier.value,
                time.monotonic() - t0,
            )
            return existing_id, True

        # Insert new
        collection = client.collections.get(collection_name).with_tenant(entry.tenant_name)
        collection.data.insert(
            properties=_entry_to_properties(entry),
            vector=vector,
            uuid=uuid.UUID(entry.id) if len(entry.id) == 36 else None,
        )

        _audit(
            session,
            entry.id,
            action="created",
            to_tier=entry.tier.value,
            reason=f"New {entry.tier.value} from investigation",
        )

        if own_session:
            session.commit()

        logger.debug(
            "store_entry completed entry_id=%s tier=%s merged=False elapsed_s=%.2f",
            entry.id,
            entry.tier.value,
            time.monotonic() - t0,
        )
        return entry.id, False

    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()


def store_hypothesis(
    entry: HypothesisEntry,
    client: weaviate.WeaviateClient | None = None,
) -> tuple[str, bool]:
    """Store a hypothesis entry. Returns (entry_id, was_merged)."""
    return store_entry(entry, client=client)


def store_finding(
    entry: FindingEntry,
    client: weaviate.WeaviateClient | None = None,
) -> tuple[str, bool]:
    """Store a finding entry. Returns (entry_id, was_merged)."""
    return store_entry(entry, client=client)


def promote_to_finding(
    hypothesis_id: str,
    finding: FindingEntry,
    client: weaviate.WeaviateClient | None = None,
) -> str:
    """Promote a hypothesis to a finding — deprecate hypothesis, store finding.

    Returns the new finding entry_id.
    """
    client = client or get_weaviate_client()
    session = _get_db_session()

    try:
        # Deprecate the hypothesis
        deprecate(
            hypothesis_id,
            tier=KnowledgeTier.HYPOTHESIS,
            reason=f"Promoted to finding {finding.id}",
            client=client,
            session=session,
        )

        # Store new finding with link
        finding.promoted_from = hypothesis_id
        collection_name = TIER_COLLECTIONS[KnowledgeTier.FINDING]
        ensure_tenant(client, collection_name, finding.tenant_name)

        vector = _embed(finding.embedding_text)
        collection = client.collections.get(collection_name).with_tenant(finding.tenant_name)
        collection.data.insert(
            properties=_entry_to_properties(finding),
            vector=vector,
            uuid=uuid.UUID(finding.id) if len(finding.id) == 36 else None,
        )

        _audit(
            session,
            finding.id,
            action="promoted",
            from_tier=KnowledgeTier.HYPOTHESIS.value,
            to_tier=KnowledgeTier.FINDING.value,
            reason=f"Promoted from hypothesis {hypothesis_id}",
            metadata={"promoted_from": hypothesis_id},
        )

        session.commit()
        return finding.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def promote_to_truth(
    finding_id: str,
    reviewer: str,
    notes: str = "",
    truth_entry: TruthEntry | None = None,
    client: weaviate.WeaviateClient | None = None,
) -> str:
    """Promote a finding to truth — human-gated.

    Phase 4 provides the review UI. This function exists now for the API.
    Returns the new truth entry_id.
    """
    client = client or get_weaviate_client()
    session = _get_db_session()

    try:
        # Load the finding from Weaviate to build truth entry if not provided
        if truth_entry is None:
            finding_coll = client.collections.get(TIER_COLLECTIONS[KnowledgeTier.FINDING])
            # Search by entry_id across tenants
            # For now, require truth_entry to be passed
            raise ValueError("truth_entry must be provided (finding lookup not yet implemented)")

        truth_entry.promoted_from = finding_id
        truth_entry.human_reviewer = reviewer
        truth_entry.review_notes = notes
        truth_entry.recompute_confidence()

        # Deprecate finding
        deprecate(
            finding_id,
            tier=KnowledgeTier.FINDING,
            reason=f"Promoted to truth {truth_entry.id}",
            client=client,
            session=session,
        )

        # Store truth
        collection_name = TIER_COLLECTIONS[KnowledgeTier.TRUTH]
        ensure_tenant(client, collection_name, truth_entry.tenant_name)

        vector = _embed(truth_entry.embedding_text)
        collection = client.collections.get(collection_name).with_tenant(truth_entry.tenant_name)
        collection.data.insert(
            properties=_entry_to_properties(truth_entry),
            vector=vector,
            uuid=uuid.UUID(truth_entry.id) if len(truth_entry.id) == 36 else None,
        )

        _audit(
            session,
            truth_entry.id,
            action="promoted",
            from_tier=KnowledgeTier.FINDING.value,
            to_tier=KnowledgeTier.TRUTH.value,
            actor=f"human:{reviewer}",
            reason=notes or f"Promoted from finding {finding_id}",
            metadata={"promoted_from": finding_id},
        )

        session.commit()
        return truth_entry.id

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def deprecate(
    entry_id: str,
    tier: KnowledgeTier,
    reason: str = "",
    client: weaviate.WeaviateClient | None = None,
    session: Session | None = None,
) -> None:
    """Mark an entry as deprecated (not deleted). Updates Weaviate + audit."""
    client = client or get_weaviate_client()
    own_session = session is None
    session = session or _get_db_session()

    try:
        collection_name = TIER_COLLECTIONS[tier]
        collection = client.collections.get(collection_name)

        # Find and update the object across tenants
        # For now, iterate known tenants — in practice this is fast
        # because we typically know the tenant from the entry
        _update_property_by_entry_id(
            client, collection_name, entry_id, "status", DeprecationStatus.DEPRECATED.value
        )

        _audit(
            session,
            entry_id,
            action="deprecated",
            from_tier=tier.value,
            actor="system",
            reason=reason,
        )

        if own_session:
            session.commit()

    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()


def merge_observation(
    entry_id: str,
    tier: KnowledgeTier,
    new_run_id: str = "",
    new_evidence: list[str] | None = None,
    client: weaviate.WeaviateClient | None = None,
    session: Session | None = None,
) -> None:
    """Merge a new observation into an existing entry.

    Increments observation_count, updates last_observed, appends evidence.
    """
    client = client or get_weaviate_client()
    own_session = session is None
    session = session or _get_db_session()

    try:
        collection_name = TIER_COLLECTIONS[tier]
        # Find the object
        obj = _find_object_by_entry_id(client, collection_name, entry_id)
        if obj is None:
            logger.warning("Cannot merge: entry %s not found in %s", entry_id, collection_name)
            return

        props = obj.properties
        new_count = (props.get("observation_count") or 1) + 1
        now_iso = datetime.now(UTC).isoformat()

        updates = {
            "observation_count": new_count,
            "last_observed": now_iso,
        }

        # Update source_run_ids
        existing_runs = props.get("source_run_ids") or []
        if new_run_id and new_run_id not in existing_runs:
            updates["source_run_ids"] = existing_runs + [new_run_id]

        # Update in Weaviate
        _update_object(client, collection_name, obj, updates)

        _audit(
            session,
            entry_id,
            action="merged",
            from_tier=tier.value,
            to_tier=tier.value,
            reason=f"Observation merged (count={new_count})",
            metadata={
                "new_run_id": new_run_id,
                "new_evidence": new_evidence or [],
            },
        )

        if own_session:
            session.commit()

    except Exception:
        if own_session:
            session.rollback()
        raise
    finally:
        if own_session:
            session.close()


def _find_object_by_entry_id(
    client: weaviate.WeaviateClient,
    collection_name: str,
    entry_id: str,
) -> object | None:
    """Find a Weaviate object by entry_id across tenants.

    Returns the first matching object or None.
    """
    collection_base = client.collections.get(collection_name)
    tenants = collection_base.tenants.get()

    for tenant_name in tenants:
        collection = collection_base.with_tenant(tenant_name)
        try:
            results = collection.query.fetch_objects(
                filters=weaviate.classes.query.Filter.by_property("entry_id").equal(entry_id),
                limit=1,
            )
            if results.objects:
                # Stash tenant info for later use
                results.objects[0]._tenant_name = tenant_name
                return results.objects[0]
        except Exception:
            continue
    return None


def _update_object(
    client: weaviate.WeaviateClient,
    collection_name: str,
    obj: object,
    updates: dict,
) -> None:
    """Update properties on a Weaviate object."""
    tenant_name = getattr(obj, "_tenant_name", "community")
    collection = client.collections.get(collection_name).with_tenant(tenant_name)
    collection.data.update(
        uuid=obj.uuid,
        properties=updates,
    )


def _update_property_by_entry_id(
    client: weaviate.WeaviateClient,
    collection_name: str,
    entry_id: str,
    prop_name: str,
    prop_value: str,
) -> None:
    """Update a single property on an object found by entry_id."""
    obj = _find_object_by_entry_id(client, collection_name, entry_id)
    if obj is not None:
        _update_object(client, collection_name, obj, {prop_name: prop_value})


# ---------------------------------------------------------------------------
# Quality filters — prevent junk from entering the knowledge store
# ---------------------------------------------------------------------------

# Phrases that indicate LLM meta-commentary, not analytical findings
_META_COMMENTARY_PHRASES = [
    "i need a run_id",
    "could you please provide",
    "i don't have",
    "can you provide",
    "please provide",
    "i need the",
    "could you provide",
    "let me check",
    "i would need",
    "i'll need",
]


def _should_store_finding(finding) -> tuple[bool, str]:
    """Check if a finding is worth storing. Returns (should_store, rejection_reason)."""
    # Reject tool-use failures (fallback path — investigator never called ML tools)
    if getattr(finding, "tool_use_failed", False):
        return False, "tool_use_failed"

    # Reject dry-run entries
    if getattr(finding, "run_id", "") == "dry-run" or finding.statement.startswith("DRY_RUN:"):
        return False, "dry_run"

    # Reject LLM meta-commentary
    statement_lower = finding.statement.lower()
    for phrase in _META_COMMENTARY_PHRASES:
        if phrase in statement_lower:
            return False, f"meta_commentary: '{phrase}'"

    return True, ""


def _should_store_hypothesis(hypothesis) -> tuple[bool, str]:
    """Check if a hypothesis is worth storing. Returns (should_store, rejection_reason)."""
    # Reject dry-run entries
    if getattr(hypothesis, "run_id", "") == "dry-run" or hypothesis.statement.startswith(
        "DRY_RUN:"
    ):
        return False, "dry_run"

    # Reject LLM meta-commentary
    statement_lower = hypothesis.statement.lower()
    for phrase in _META_COMMENTARY_PHRASES:
        if phrase in statement_lower:
            return False, f"meta_commentary: '{phrase}'"

    return True, ""


# ---------------------------------------------------------------------------
# High-level: convert investigation results to knowledge entries
# ---------------------------------------------------------------------------


def store_investigation_to_knowledge(
    findings: list,
    hypotheses: list,
    run_id: str = "",
    scope: KnowledgeScope = KnowledgeScope.COMMUNITY,
    account_id: str = "",
    client: weaviate.WeaviateClient | None = None,
) -> dict[str, int]:
    """Convert investigation findings/hypotheses to knowledge entries and store.

    Returns counts: {"stored": N, "merged": M, "filtered": F}.
    """
    logger.info(
        "store_to_knowledge started run_id=%s findings=%d hypotheses=%d",
        run_id,
        len(findings),
        len(hypotheses),
    )
    t0 = time.monotonic()
    client = client or get_weaviate_client()
    stored = 0
    merged = 0
    filtered = 0

    for f in findings:
        should_store, reason = _should_store_finding(f)
        if not should_store:
            logger.info(
                "Filtered finding from knowledge store: %s — reason: %s", f.statement[:80], reason
            )
            filtered += 1
            continue

        entry = FindingEntry.from_investigation_finding(f, scope=scope, account_id=account_id)
        if run_id:
            entry.source_run_ids = [run_id]
        try:
            _, was_merged = store_finding(entry, client=client)
            if was_merged:
                merged += 1
            else:
                stored += 1
        except Exception as e:
            logger.warning("Failed to store finding '%s': %s", f.statement[:50], e)

    for h in hypotheses:
        should_store, reason = _should_store_hypothesis(h)
        if not should_store:
            logger.info(
                "Filtered hypothesis from knowledge store: %s — reason: %s",
                h.statement[:80],
                reason,
            )
            filtered += 1
            continue

        entry = HypothesisEntry.from_investigation_hypothesis(h, scope=scope, account_id=account_id)
        if run_id:
            entry.source_run_ids = [run_id]
        try:
            _, was_merged = store_hypothesis(entry, client=client)
            if was_merged:
                merged += 1
            else:
                stored += 1
        except Exception as e:
            logger.warning("Failed to store hypothesis '%s': %s", h.statement[:50], e)

    elapsed = time.monotonic() - t0
    logger.info(
        "store_to_knowledge completed run_id=%s stored=%d merged=%d filtered=%d elapsed_s=%.2f",
        run_id,
        stored,
        merged,
        filtered,
        elapsed,
    )
    return {"stored": stored, "merged": merged, "filtered": filtered}
