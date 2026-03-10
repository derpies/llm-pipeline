# knowledge/

Knowledge store infrastructure — **not yet implemented** (Phase B).

This directory will hold the tiered knowledge storage and retrieval system.
It's a placeholder now, but the structure is defined in CLAUDE.md.

## Planned files

| File | Purpose |
|------|---------|
| `store.py` | Tier-aware write operations (store hypothesis, store finding, etc.) |
| `retrieval.py` | Tier-weighted vector search (truth > findings > hypotheses) |
| `models.py` | SQLAlchemy + Pydantic models for knowledge items, audit trail |
| `promotion.py` | Promotion/demotion logic (finding → truth, deprecation) |

## How it connects

```
tools/knowledge.py          <-- thin @tool wrappers (LLM-callable)
    └─ knowledge/store.py   <-- actual storage logic
    └─ knowledge/retrieval.py
        └─ Postgres (pgvector) + ChromaDB
```

`tools/knowledge.py` is what agents call. This directory is the
implementation those tools delegate to. The separation means you can
test and evolve the storage layer independently of the tool interface.
