# knowledge/

Four-tier knowledge store backed by Weaviate (vectors) and Postgres (audit trail). Stores, deduplicates, promotes, and retrieves investigation findings across confidence tiers.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `models.py` | Pydantic + SQLAlchemy models: KnowledgeTier, KnowledgeScope, KnowledgeEntry subclasses, confidence computation, Postgres audit record |
| `weaviate_schema.py` | Collection definitions (4 tiers + SummarizationDocument + RagDocument), multi-tenant config, lazy client init |
| `store.py` | Write path: store_entry with cosine-similarity dedup, promote_to_finding/truth, deprecate, Postgres audit trail |
| `retrieval.py` | Read path: tier-weighted retrieval (Grounded 1.0x > Truth 0.85x > Finding 0.6x > Hypothesis 0.3x), dual-scope queries |
| `import_grounded.py` | Import grounding corpus (markdown files) into Weaviate Grounded tier, splitting on ## headings |

## Key Concepts

**Tier hierarchy** — hypothesis < finding < truth < grounded. Knowledge promotes upward through evidence accumulation and human review. Lower tiers are rebuildable; grounded tier is read-only (external corpus).

**Scopes** — `community` (aggregate, cross-account patterns) and `account` (per-account isolation). Implemented via Weaviate multi-tenancy: tenant = account_id or "community".

**Deduplication** — On write, cosine similarity > 0.95 with matching topic/dimension triggers merge_observation (update existing entry) rather than creating a duplicate.

**Confidence scoring** — `weighted_score = similarity * tier_weight * confidence`. Tier weight ensures grounded knowledge outranks hypotheses even at equal vector similarity. Confidence incorporates observation count and temporal span.

## Contracts

- **Imports from**: `email_analytics.models` (SQLAlchemy Base for audit table), `config` (Weaviate/Postgres URLs)
- **Exports**: `store_entry`, `promote_to_finding`, `promote_to_truth`, `deprecate`, `retrieve_knowledge`, `retrieve_for_account`, knowledge model classes
- **Consumed by**: `agents/storage.py` (investigation → knowledge conversion), `tools/knowledge/` (LLM-callable retrieval), `cli.py` (knowledge search/stats commands)
