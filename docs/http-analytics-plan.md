# HTTP Analytics Domain — Implementation Plan

## Context

The pipeline currently processes email delivery logs through a complete ML → LLM investigation → knowledge store cycle. We need to add HTTP access log processing as a **separate domain**, following the same pluggable architecture. The sample data (80K records from a 1m41s window on `edge001.corleone`) reveals: 53% PHP vulnerability probes, a custom status 679 (known-valid content missing = bug indicator), 40% empty user-agents (bots), Apple MPP tracking, and two backend upstreams with 28.7% edge-level rejections.

**Scale target**: 80K records/minute, 100M+/day. Streaming aggregation from the start — bounded memory, chunk-at-a-time processing.

---

## Phase 0: Multi-Domain Support

Currently `get_active_domain()` returns the first discovered domain. With two domains registered, we need domain selection.

### Files to modify

**`src/llm_pipeline/agents/domain_registry.py`**
- Add `get_domain(name: str) -> DomainManifest | None`
- Modify `get_active_domain(domain_name: str | None = None)` — if name provided, look it up; else fall back to first discovered (backward-compat)

**`src/llm_pipeline/agents/state.py`**
- Add `domain_name: str` to `InvestigationCycleState` and `InvestigatorState`

**`src/llm_pipeline/agents/orchestrator.py`**
- Read `state.get("domain_name")` in `orchestrator_plan` and `orchestrator_evaluate`
- Pass to `get_active_domain(domain_name)` for prompt construction

**`src/llm_pipeline/agents/plugins/investigator/agent.py`**
- Read `domain_name` from state in `_build_investigator_prompt`
- Pass to `get_active_domain(domain_name)`

**`src/llm_pipeline/agents/graph.py`**
- Propagate `domain_name` through `Send` when creating `InvestigatorState` dicts

All changes backward-compatible — if `domain_name` not set, existing behavior preserved.

---

## Phase 1: HTTP Analytics ML Pipeline

All new files in `src/llm_pipeline/http_analytics/`.

### 1a. `models.py` — Enums, events, aggregation buckets, ORM

**Enums:**
- `RequestCategory`: php_probe, tracking_pixel, click_tracking, page_load, static_asset, api_call, websocket, other
- `HostCategory`: ontraport.com, ontralink.com, ontraport.net, custom_domain
- `UaCategory`: real_browser, bot_crawler, scanner, empty, curl, email_client, apple_mpp, other
- `StatusClass`: 2xx, 3xx, 4xx, 5xx, 679, other
- `HttpAnomalyType`: error_rate_spike, latency_spike, traffic_spike, traffic_drop, status_679_spike, bot_traffic_spike
- Reuse `TrendDirection` from email_analytics

**`HttpAccessEvent(BaseModel)`** — Pydantic model for a single log record:
- Raw fields: isotime, server, remoteaddr, http_host, request, http_status, sizesent, tts, upstream, http_referrer, useragent, applempp, xff, trueip, accountid, session
- Derived fields (via `model_validator`): http_method, request_path, request_category, host_category, ua_category, status_class, is_apple_mpp

**`HttpAggregationBucket(BaseModel)`** — Dimensional aggregation output:
- Key: time_window, dimension, dimension_value
- Counts: total, status_2xx/3xx/4xx/5xx/679/other
- Rates: success_rate, client_error_rate, server_error_rate, known_content_error_rate
- TTS: p50, p90, p95, p99, max, mean
- Size: total_bytes, mean_bytes
- Completeness: empty_ua_count, empty_upstream_count, empty_referrer_count

**`HttpAnomalyFinding`**, **`HttpTrendFinding`**, **`HttpDataCompleteness`**, **`HttpAnalysisReport`** — parallel to email models

**SQLAlchemy ORM** (tables: `http_aggregations`, `http_anomalies`, `http_trends`, `http_data_completeness`, `http_analysis_runs`) — same pattern as email, inheriting from `Base` in `models/db.py`

### 1b. `classifier.py` — Rule-based request/UA/host classifiers

Three classifiers (regex/pattern-based, similar to `smtp_classifier.py`):

- **`classify_request(request_line) -> (method, path, RequestCategory)`** — ordered regex: `.php` → PHP_PROBE, `/o?` → TRACKING_PIXEL, `/c/` → CLICK_TRACKING, static file extensions → STATIC_ASSET, `/api/` → API_CALL, etc.
- **`classify_useragent(ua, applempp) -> UaCategory`** — empty → EMPTY, curl/wget → CURL, bot patterns → BOT_CRAWLER, scanner fingerprints (zgrab, masscan, nikto) → SCANNER, applempp=TRUE → APPLE_MPP, real browsers → REAL_BROWSER
- **`classify_host(host) -> HostCategory`** — suffix matching on `.ontraport.com`, `.ontralink.com`, `.ontraport.net`, else CUSTOM_DOMAIN

### 1c. `loader.py` — NDJSON streaming loader

- `discover_files(path) -> list[str]` — same pattern as email
- `iter_http_event_chunks(path, chunk_size) -> Iterator[list[HttpAccessEvent]]` — reads NDJSON line by line, validates into HttpAccessEvent, yields chunks of `chunk_size` (default: 50K)

### 1d. `aggregator.py` — Polars-based dimensional aggregation

**Dimensions:**
```
http_host, host_category, status_code, status_class,
request_category, http_method, upstream, ua_category
```

- `events_to_dataframe(events) -> pl.DataFrame` — converts to Polars with derived columns
- `aggregate(df, window_minutes=1, dimensions=None) -> list[HttpAggregationBucket]` — group by (time_window, dimension), compute counts/rates/quantiles. **Minute-level** windows (not hour-level like email — HTTP data density is much higher)
- `compute_data_completeness(df, ...) -> list[HttpDataCompleteness]` — empty rates for useragent, upstream, http_referrer, accountid
- `merge_bucket_list(buckets) -> list[HttpAggregationBucket]` — dedup/merge by key, sum counts, recompute rates, weighted mean for TTS
- `aggregate_file(path, ...) -> FileAggregationResult` — stream chunks, aggregate each, merge

**Streaming note:** Initial implementation uses Polars quantiles per chunk + weighted-mean merge (same approach as email). Known limitation: percentiles lose accuracy on cross-chunk merge. T-digest upgrade path is straightforward — add `tts_digest_bytes` field and use `tdigest` library for mergeable streaming quantile estimation. Deferred to follow-up.

### 1e. `anomaly.py` — Modified z-score anomaly detection

Same MAD-based algorithm as email. Metrics:
- Positive (drop = bad): `success_rate`
- Negative (spike = bad): `client_error_rate`, `server_error_rate`, `known_content_error_rate`, `tts_p95`

Category-aware baselines (parallel to email's segment baselines):
```python
_CATEGORY_BASELINES = {
    "php_probe": {"success_rate": 0.0, "client_error_rate": 1.0, ...},
    "tracking_pixel": {"success_rate": 0.95, ...},
    "page_load": {"success_rate": 0.98, ...},
    ...
}
```

### 1f. `trends.py` — Linear regression trend detection

Same approach as email. Metrics: success_rate, client_error_rate, server_error_rate, known_content_error_rate, tts_p95.

### 1g. `state.py` — LangGraph state

`HttpAnalyticsState(TypedDict)` with `operator.add` annotations for fan-out/fan-in (aggregations, completeness, event_count, errors).

### 1h. `graph.py` — LangGraph ML pipeline

Same topology: `discover → fan-out(process_file) → merge → parallel(anomaly, trends) → store`.

### 1i. `storage.py` — Postgres persistence

`store_results(report)`, `load_historical_aggregations(lookback_days)`, `load_report(run_id)` — same pattern as email.

---

## Phase 2: HTTP Analytics Domain Plugin

All new files in `src/llm_pipeline/domains/http_analytics/`.

### 2a. `roles.py` — Four investigator roles

| Role | Focus |
|------|-------|
| `error_analysis` | Status code patterns, 679 bugs, 4xx/5xx distribution, edge rejections |
| `latency` | TTS profiling, slow endpoints, upstream performance, WebSocket filtering |
| `security` | Bot detection, scanner classification, PHP probes, IP clustering |
| `traffic` | Throughput patterns, host distribution, load balance, account-level volume |

### 2b. `prompts.py` — Domain knowledge and role descriptions

`INVESTIGATOR_DOMAIN_PROMPT` covers: 679 meaning, PHP probe baseline (53%), empty UA baseline (40%), Apple MPP, edge rejections, two-upstream topology.

`ORCHESTRATOR_ROLE_PROMPT` lists the four roles with selection guidance.

### 2c. `manifest.py` — DomainManifest instance

Wires roles, prompts, report_builder, report_renderer.

### 2d. `report_models.py` — Pydantic report structure

- `HostHealthRow` — per-host-category health (rates + latency percentiles)
- `CategoryBreakdownRow` — per-request-category traffic distribution
- `Status679Summary` — affected hosts, paths, counts
- `BotTrafficSummary` — scanner %, empty UA %, top scanner UAs
- `HttpStructuredReport` — combines all sections + confirmed issues + trend summary
- `HttpInvestigationNotes` — overflow: hypotheses, observations, process notes

### 2e. `report_builder.py` — Deterministic report assembly (no LLM)

`assemble_full_report(run_id, ml_run_id, ml_report, findings, hypotheses, digest_lines) -> HttpInvestigationReport`

### 2f. `report_renderer.py` — Markdown rendering

`render_markdown(report) -> str`

### 2g. `cli.py` — CLI commands

- `analyze-http` — run ML pipeline on HTTP log files
- `investigate-http` — ML analysis → investigation cycle → findings (passes `domain_name="http_analytics"` to investigation graph)

---

## Phase 3: Investigator Tools

New files in `src/llm_pipeline/tools/http/`.

Six tools, **prefixed with `http_`** to avoid collision with email tools (both sets are visible to all investigators — domain prompts guide selection):

| Tool | Queries | Parameters |
|------|---------|-----------|
| `get_http_aggregations` | `http_aggregations` | run_id, dimension?, dimension_value?, limit |
| `get_http_anomalies` | `http_anomalies` | run_id, dimension?, anomaly_type?, severity? |
| `get_http_trends` | `http_trends` | run_id, dimension?, direction? |
| `get_http_report_summary` | `http_analysis_runs` | run_id |
| `get_http_data_completeness` | `http_data_completeness` | run_id, dimension?, field_name? |
| `compare_http_dimensions` | `http_aggregations` | run_id, dimension, values[], metric |

All follow the same pattern: `@tool` decorator, SQLAlchemy query, return `tool_result(ToolStatus.OK/EMPTY, json)`.

`TOOL_ROLES` declaration in `__init__.py` — auto-discovered by registry.

---

## Phase 4: Tests

### New files

- `tests/test_http_classifier.py` — classify_request, classify_useragent, classify_host edge cases
- `tests/test_http_loader.py` — NDJSON loading, chunking, malformed records
- `tests/test_http_aggregator.py` — dimensional bucketing, rates, merge, completeness
- `tests/test_http_anomaly.py` — anomaly detection with known deviations
- `tests/test_http_trends.py` — trend detection with synthetic series
- `tests/test_http_graph.py` — integration test of ML pipeline
- `tests/test_http_domain.py` — manifest discovery, roles, prompts
- `tests/test_http_tools.py` — tool functions with mocked Postgres
- `tests/test_multi_domain.py` — both domains discovered, domain_name propagation

---

## Phase 5: Config and Integration

**`src/llm_pipeline/config.py`** — add HTTP-specific settings:
- `http_batch_size: int = 50000` (larger chunks — simpler events)
- `http_time_window_minutes: int = 1` (minute-level, not hour-level)
- `http_lookback_days: int = 7`
- `http_anomaly_threshold: float = 3.5`
- `http_trend_min_points: int = 10` (more data points at minute granularity)

**`src/llm_pipeline/models/db.py`** — add `import llm_pipeline.http_analytics.models` in `init_db()` so tables auto-create.

No new dependencies, no Docker changes, no init-db.sql changes.

---

## Implementation Order

1. **Phase 0** — multi-domain support (small, unblocks everything, verify email still works)
2. **Phase 1a-1c** — models, classifier, loader (foundation, testable in isolation)
3. **Phase 1d** — aggregator (the core, most complex piece)
4. **Phase 1e-1f** — anomaly + trends (straightforward adaptation)
5. **Phase 1g-1i** — state, graph, storage (wires pipeline together)
6. **Phase 5** — config + db init (small integration touches)
7. **Phase 4** — tests (alongside each phase, bulk integration here)
8. **Phase 2** — domain plugin (manifest, roles, prompts, reports, CLI)
9. **Phase 3** — investigator tools (requires storage working)

---

## Key Differences from Email Analytics

| Aspect | Email | HTTP |
|--------|-------|------|
| Time window | Hours | Minutes |
| Event complexity | High (composite XMRID, clicktrackingid) | Low (flat JSON) |
| Classification | SMTP response codes (10 categories) | Request path + UA + host (3 classifiers) |
| Primary metrics | Delivery/bounce/deferral rates | Status code rates + TTS latency |
| Special status | None | 679 (bug indicator) |
| Chunk size | 10K | 50K (simpler model) |
| Baselines | Segment-aware (VH/H/M/L/VL) | Category-aware (php_probe/tracking/page_load) |

## What's Reused vs New

**Reused directly**: `Base`, `ToolStatus`/`tool_result`, `DomainManifest`/`RoleDefinition`, domain + tool auto-discovery, investigation graph/orchestrator/reviewer/synthesizer, knowledge store, `Finding`/`Hypothesis` models.

**Same pattern, new code**: ML graph topology, Polars aggregation, MAD anomaly detection, linear regression trends, tool implementations, CLI commands, report builder/renderer.

**Genuinely new**: Request/UA/host classifiers, status 679 as first-class metric, minute-level time windows, bot traffic analysis.

---

## Verification

1. `uv run pytest` — all existing tests still pass after Phase 0
2. `uv run python -m llm_pipeline.cli analyze-http raw-logs/http-logs.json` — processes 80K records, stores to Postgres
3. `uv run python -m llm_pipeline.cli investigate-http raw-logs/http-logs.json --dry-run` — runs investigation cycle with dry-run LLM
4. Check Postgres: `SELECT COUNT(*) FROM http_aggregations`, `http_anomalies`, etc.
5. Knowledge store: findings stored after investigation
6. `uv run pytest tests/test_http_*.py tests/test_multi_domain.py` — all new tests pass
