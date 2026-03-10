# email_analytics/

ML pipeline for email delivery log analysis. Parses raw delivery events, aggregates by multiple dimensions, detects anomalies and trends, classifies SMTP responses, and tracks data completeness — all without buffering raw events in memory.

## Files

| File | Purpose |
|------|---------|
| `__init__.py` | Package marker |
| `graph.py` | LangGraph pipeline: discover files → fan-out(process_file) → merge → parallel(anomalies, trends) → store |
| `loader.py` | File discovery and JSON parsing — supports NDJSON and concatenated JSON formats, streaming variants |
| `state.py` | LangGraph state schemas: FileProcessingState (per-file), EmailAnalyticsState (top-level with fan-in reducers) |
| `parsers.py` | Composite field parsing: XMRID (7 dot-delimited sub-fields), clicktrackingid (6 semicolon-delimited fields), listid taxonomy, compliance status |
| `aggregator.py` | Polars-based dimensional aggregation across listid, recipient_domain, sending_ip, account, segment, compliance. Tracks zero-value fields for completeness |
| `models.py` | Pydantic (DeliveryEvent, AnalysisReport, AnomalyFinding, TrendFinding) + SQLAlchemy (Postgres persistence records) + enums (DeliveryStatus, SmtpCategory, AnomalyType) |
| `anomaly.py` | Modified z-score anomaly detection (MAD-based, robust to heavy-tailed data). Segment-aware baselines for sparse dimensions |
| `smtp_classifier.py` | Regex-based SMTP response categorization into 10 semantic categories (throttling, blacklist, reputation, etc.). First-match-wins pattern ordering |
| `trends.py` | Linear regression trend detection (scipy). Filters by R² and slope significance. Classifies as improving/degrading/stable |
| `storage.py` | Postgres persistence: engine factory, store_analysis_results (atomic write of aggregations + anomalies + trends + completeness) |

## Key Concepts

**No raw event buffering** — Events are parsed and aggregated in a streaming fashion. The aggregator accumulates statistics, not raw records. This keeps memory flat regardless of input size.

**Composite field parsing at ingest** — XMRID, clicktrackingid, compliance, and listid taxonomy are decomposed during event parsing, not downstream. The `parsers.py` module operates on raw strings with no external dependencies.

**Primary grouping by listid** — Not sendid. Listid maps to engagement segment and IP pool. Pool reputation is segment-specific, making listid the natural aggregation key.

**Robust statistics** — MAD-based modified z-score handles heavy-tailed delivery data better than standard deviation. Falls back to standard z-score when MAD=0. Segment-aware baselines provide priors when historical data is sparse.

**Data completeness as first-class output** — Zero-value percentages per field, per segment, per account. Enables a feedback loop: ML identifies gaps → humans verify → engineering fixes plumbing.

## Contracts

- **Imports from**: `config` (settings, DB URLs), `models.py` internal (shared SQLAlchemy Base)
- **Exports**: `AnalysisReport` (the complete ML output), `run_email_analytics` (graph entry point), storage functions, all model/enum types
- **Consumed by**: `agents/orchestrator.py` (reads ML report), `tools/ml/` (query stored results), `agents/report_builder.py` (report assembly), `cli.py` (analyze_email command)
