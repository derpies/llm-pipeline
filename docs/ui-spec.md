# LLM Pipeline — Investigation Dashboard UI Spec

## Overview

Read-only dashboard for browsing pipeline runs, investigation results, ML analysis data, and the knowledge store. This is a proof-of-concept internal tool — no authentication required.

Replit will be responsible for the FE implementation only; BE references are included for context only and to assist in developing the various FE components.

### Architecture

```
[ React Frontend ]  ←→  [ FastAPI Backend ]  ←→  [ Postgres ]
                                            ←→  [ Weaviate (knowledge store) ]
```

- **Frontend**: Standalone React app (Vite + TypeScript + Tailwind CSS recommended)
- **Backend**: FastAPI (Python), serves JSON only — no HTML rendering
- **Data**: All reads from Postgres except knowledge store (Weaviate)
- **Communication**: All API responses are `application/json`

The frontend and backend are separate applications. The backend exposes a REST API; the frontend consumes it. CORS should be enabled for local development.

---

## Data Model Context

The system runs two pipeline stages:

1. **ML Analysis** (`analyze_email`): Parses raw email delivery log files → produces aggregations, anomaly detections, trend detections, and data completeness metrics. Stored across multiple Postgres tables keyed by `run_id`.

2. **Investigation** (`investigate`): Takes ML output → fans out to LLM-powered investigator agents → produces structured findings (confirmed/disproven/inconclusive) and hypotheses (untested). A reviewer agent spot-checks evidence. A synthesizer produces a narrative summary. Results stored in Postgres + markdown/JSON report files on disk.

Investigations reference their source ML run via `ml_run_id`. Multiple investigations can share the same ML run (e.g., A/B comparison with different labels).

### Domain Model

The system is designed for pluggable domains. Currently only `email_delivery` exists. Each domain defines:
- Its own ML data types (what tables/metrics exist)
- Investigator specialist roles
- Segment thresholds and display hints

Every run is tagged with a `domain` identifier. The investigation layer (findings, hypotheses, knowledge) is domain-agnostic — the same structure regardless of domain. The ML layer is domain-specific — different domains produce different data shapes.

The frontend should **not hardcode** domain-specific values (dimension names, anomaly types, thresholds, etc.). Instead, it should read these from `GET /api/domains` on startup and use them to drive rendering.

### Key Entities

| Entity | Description |
|--------|-------------|
| **ML Run** (`email_analysis_runs`) | One execution of the ML pipeline. Has aggregations, anomalies, trends, completeness data. |
| **Investigation Run** (`investigation_runs`) | One execution of the investigation cycle. References an ML run. Has findings, hypotheses, quality warnings. |
| **Finding** (`investigation_findings`) | A structured claim with status (confirmed/disproven/inconclusive), evidence, and cited metrics. |
| **Hypothesis** (`investigation_hypotheses`) | An untested claim with reasoning. |
| **Report** (`investigation_reports`) | Rendered JSON + markdown report for an investigation. |
| **Knowledge Entry** (Weaviate) | Four-tier hierarchy: hypothesis → finding → truth → grounded. Accumulated learnings across runs. |

---

## API Endpoints

Base URL: `http://localhost:20005/api`

### Domain Discovery

#### `GET /api/domains`

List all registered domains and their schemas. The frontend calls this on startup to understand what data types exist and how to render them.

**Response** — flat array (not wrapped in an object):
```json
[
  {
    "name": "email_delivery",
    "description": "Email delivery analytics — reputation, compliance, engagement, ISP, diagnostics",
    "roles": [
      {"name": "reputation", "prompt_supplement": "IP and domain reputation, warming, throttling, feedback loops"},
      {"name": "compliance", "prompt_supplement": "SPF, DKIM, DMARC, ARC authentication and policy"},
      {"name": "engagement", "prompt_supplement": "Segment behavior, list hygiene, sunset policies"},
      {"name": "isp", "prompt_supplement": "Provider-specific filtering (Gmail, Microsoft, Yahoo, Apple)"},
      {"name": "diagnostics", "prompt_supplement": "General diagnostics, bounce analysis, data completeness"}
    ],
    "ml_data_types": {
      "dimensions": [
        "listid", "recipient_domain", "outmtaid", "engagement_segment",
        "listid_type", "compliance_status", "xmrid_account_id", "smtp_category"
      ],
      "metrics": [
        "delivery_rate", "bounce_rate", "deferral_rate", "complaint_rate",
        "pre_edge_latency_mean", "delivery_time_mean"
      ],
      "delivery_statuses": ["delivered", "bounced", "deferred", "dropped", "complaint", "unknown"],
      "smtp_categories": [
        "throttling", "blacklist", "reputation", "auth_failure", "content_rejection",
        "recipient_unknown", "policy", "network", "success", "other"
      ],
      "anomaly_types": ["rate_drop", "rate_spike", "bounce_spike", "deferral_spike", "complaint_spike"],
      "trend_directions": ["improving", "degrading", "stable"],
      "completeness_fields": [
        "clicktrackingid", "xmrid_account_id", "xmrid_contact_id",
        "last_active_ts", "contact_added_ts", "op_queue_time_parsed"
      ],
      "segment_thresholds": {
        "VH": 0.95,
        "H": 0.90,
        "M": 0.85,
        "L": 0.75,
        "VL": 0.60
      }
    }
  }
]
```

Notes:
- `roles` uses `prompt_supplement` (not `description`).
- `ml_data_types` is flat — `dimensions` is a top-level array, not nested under `aggregations`.
- `segment_thresholds` maps engagement segment codes to expected delivery rate floors. Use these to color-code aggregation rows: if a segment's `delivery_rate` is below its threshold, highlight it.

---

#### `GET /api/meta`

Static enum values and display metadata. Called once on app load.

**Response:**
```json
{
  "finding_statuses": ["confirmed", "disproven", "inconclusive"],
  "review_assessments": ["supported", "weak_evidence", "contradicted", "gap_identified"],
  "review_actions": ["accept", "investigate_further", "flag_for_human"],
  "knowledge_tiers": [
    {"name": "hypothesis", "weight": 0.3, "description": "LLM-generated, untested", "color": "gray"},
    {"name": "finding", "weight": 0.6, "description": "ML-tested, evidence attached", "color": "amber"},
    {"name": "truth", "weight": 0.85, "description": "ML + LLM + human confirmed", "color": "blue"},
    {"name": "grounded", "weight": 1.0, "description": "Authoritative domain knowledge (read-only)", "color": "emerald"}
  ],
  "run_statuses": ["success", "partial", "failed", "dry_run"],
  "commands": ["analyze_email", "investigate"]
}
```

Notes:
- Tier colors are Tailwind-friendly: `emerald`, `blue`, `amber`, `gray` (not blue/green/yellow/gray).
- `review_assessments` and `review_actions` are new fields vs. earlier drafts. Used for displaying reviewer quality annotations on findings.
- Tiers are ordered lowest-to-highest weight (hypothesis → grounded). The `KnowledgeTier` enum iterates in this order.

---

### Runs

#### `GET /api/runs`

List all pipeline runs (both ML and investigation). Returns a unified view.

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `domain` | string | Filter by domain: `email_delivery` |
| `command` | string | Filter by command type: `analyze_email`, `investigate` |
| `status` | string | Filter by status: `success`, `partial`, `failed`, `dry_run` |
| `source_file` | string | Substring match against source file paths |
| `search` | string | Substring match against run_id or label |
| `limit` | int | Page size (default 50, max 500) |
| `offset` | int | Pagination offset (default 0) |

**Response** — fields differ by `command` type:
```json
{
  "total": 42,
  "runs": [
    {
      "run_id": "d8e997d5-1a2b-4c3d-8e4f-5a6b7c8d9e0f",
      "domain": "email_delivery",
      "command": "analyze_email",
      "created_at": "2026-02-11T18:30:00Z",
      "source_files": ["raw-logs/delivery_logs.2026-02-11"],
      "started_at": "2026-02-11T18:30:00Z",
      "completed_at": "2026-02-11T18:32:15Z",
      "files_processed": 1,
      "events_parsed": 847293,
      "anomaly_count": 12,
      "trend_count": 5
    },
    {
      "run_id": "270e8dea-6350-4230-a095-f9b1986349d3",
      "domain": "email_delivery",
      "command": "investigate",
      "created_at": "2026-02-11T19:04:57Z",
      "source_files": ["raw-logs/delivery_logs.2026-02-11"],
      "started_at": "2026-02-11T19:04:57Z",
      "completed_at": "2026-02-11T19:14:19Z",
      "status": "success",
      "is_dry_run": false,
      "label": "B-with-knowledge",
      "ml_run_id": "d8e997d5-1a2b-4c3d-8e4f-5a6b7c8d9e0f",
      "finding_count": 4,
      "hypothesis_count": 2,
      "iteration_count": 2
    }
  ]
}
```

**Important**: The field set differs by `command`:
- **`analyze_email` runs** have: `files_processed`, `events_parsed`, `anomaly_count`, `trend_count`. They do NOT have `status`, `label`, `finding_count`, `hypothesis_count`, `ml_run_id`, `is_dry_run`, `iteration_count`.
- **`investigate` runs** have: `status`, `is_dry_run`, `label`, `ml_run_id`, `finding_count`, `hypothesis_count`, `iteration_count`. They do NOT have `files_processed`, `events_parsed`, `anomaly_count`, `trend_count`.

Common fields on both: `run_id`, `domain`, `command`, `created_at`, `source_files`, `started_at`, `completed_at`.

The frontend should render columns conditionally based on `command` type, or use a unified table that shows blank cells for inapplicable fields.

---

### Investigations

#### `GET /api/investigations/{run_id}`

Full investigation detail for a single run.

**Response:**
```json
{
  "run_id": "270e8dea-6350-4230-a095-f9b1986349d3",
  "started_at": "2026-02-11T19:04:57Z",
  "completed_at": "2026-02-11T19:14:19Z",
  "duration_seconds": 562.0,
  "status": "success",
  "is_dry_run": false,
  "label": "B-with-knowledge",
  "ml_run_id": "d8e997d5-1a2b-4c3d-8e4f-5a6b7c8d9e0f",
  "iteration_count": 2,
  "finding_count": 4,
  "hypothesis_count": 2,
  "checkpoint_digest": "## Investigation Checkpoint\n\n### Confirmed Findings\n...",
  "quality_warnings": ["VH bounce analysis: confirmed_without_ml_verification"],
  "source_files": ["raw-logs/delivery_logs.2026-02-11"],
  "findings": [
    {
      "topic_title": "VH segment bounce spike on gmail.com",
      "statement": "VH segment bounce rate to gmail.com spiked to 8.2%, 3x the historical baseline of 2.7%. The spike is concentrated on outmtaid 10.20.30.40 which shows 94% of the bounces.",
      "status": "confirmed",
      "evidence": [
        "Aggregation: VH-main bounce_rate=0.082 vs 14-day baseline 0.027",
        "Anomaly: bounce_spike severity=high z_score=4.1 for VH-main",
        "Aggregation by outmtaid: 10.20.30.40 shows bounce_rate=0.31"
      ],
      "metrics_cited": {"bounce_rate": 0.082, "baseline_mean": 0.027, "z_score": 4.1},
      "is_fallback": false,
      "quality_warnings": []
    },
    {
      "topic_title": "M segment delivery rate degradation",
      "statement": "M segment delivery rate has degraded from 92% to 87% over the past 14 days, with a statistically significant downward trend (R²=0.87).",
      "status": "confirmed",
      "evidence": [
        "Trend: M-main delivery_rate slope=-0.003 R²=0.87 over 14 points",
        "Aggregation: M-main current delivery_rate=0.87 vs segment threshold 0.85"
      ],
      "metrics_cited": {"delivery_rate": 0.87, "slope": -0.003, "r_squared": 0.87},
      "is_fallback": false,
      "quality_warnings": []
    },
    {
      "topic_title": "Account 269124 DKIM compliance failure",
      "statement": "Account 269124 has 100% DKIM failure on shared IP pool, but impact is limited — account represents only 0.3% of pool volume.",
      "status": "inconclusive",
      "evidence": [
        "Aggregation by xmrid_account_id: 269124 shows dkim_fail_rate=1.0",
        "Volume: 269124 total=2,847 vs pool total=948,000"
      ],
      "metrics_cited": {"dkim_fail_rate": 1.0, "account_volume": 2847, "pool_volume": 948000},
      "is_fallback": false,
      "quality_warnings": ["confirmed_without_ml_verification"]
    },
    {
      "topic_title": "Data completeness regression in clicktrackingid",
      "statement": "clicktrackingid zero-value rate increased from 3% to 12% between Feb 11 and Feb 14, concentrated in DS and NM segments.",
      "status": "confirmed",
      "evidence": [
        "Completeness: clicktrackingid zero_rate=0.12 for DS-main (was 0.03 on Feb 11)",
        "Completeness: clicktrackingid zero_rate=0.09 for NM-main"
      ],
      "metrics_cited": {"zero_rate_current": 0.12, "zero_rate_baseline": 0.03},
      "is_fallback": false,
      "quality_warnings": []
    }
  ],
  "hypotheses": [
    {
      "topic_title": "Account 269124 compliance cascade risk",
      "statement": "Non-compliant DKIM on account 269124 may be degrading shared pool reputation at gmail.com, contributing to the VH bounce spike.",
      "reasoning": "Account 269124 shows 100% DKIM failure on the same IP pool where VH bounces spiked. Gmail's postmaster documentation indicates pool-level reputation penalties for mixed compliance. However, account volume is only 0.3% of the pool, which may be below Gmail's penalty threshold."
    },
    {
      "topic_title": "DS/NM clicktrackingid regression source",
      "statement": "The clicktrackingid completeness regression in DS/NM segments may originate from a specific automation workflow that stopped populating the field after a platform update.",
      "reasoning": "DS and NM segments are predominantly system-generated traffic (automation, transactional). The regression appeared abruptly between Feb 11-14, consistent with a deployment change rather than gradual drift. Would need to cross-reference with xmrid op-queue-time patterns to identify the specific automation source."
    }
  ],
  "synthesis_narrative": "## Executive Summary\n\nThis investigation examined 847,293 email delivery events from February 11, 2026. Four findings were confirmed across reputation, compliance, and data quality dimensions.\n\n### Key Findings\n\n**VH Bounce Spike (High Severity)**: The VH segment experienced a 3x bounce rate spike to gmail.com, concentrated on a single outbound MTA IP. This warrants immediate investigation of IP reputation status.\n\n**M Segment Degradation**: Medium engagement segment shows a statistically significant 14-day delivery rate decline from 92% to 87%, approaching the segment threshold of 85%.\n\n**Data Quality Regression**: clicktrackingid completeness dropped from 97% to 88% in DS/NM segments, indicating a potential plumbing issue in automation workflows.\n\n### Untested Hypotheses\n\nTwo hypotheses remain for future investigation: possible compliance cascade from account 269124, and the specific automation source of the clicktrackingid regression."
}
```

Notes:
- `duration_seconds` is a float (computed from started_at/completed_at).
- No `domain` field on the investigation detail response.
- `checkpoint_digest` is raw markdown text from the investigation loop's circuit breaker output.
- `synthesis_narrative` can be `null` if synthesis was skipped.

---

#### `GET /api/investigations/{run_id}/report`

Rendered report content (the same content written to disk as files).

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `format` | string | `json` (structured report) or `markdown` (rendered markdown). Default: `json` |

**Response (format=json):**
```json
{
  "run_id": "270e8dea-6350-4230-a095-f9b1986349d3",
  "report": { "...full InvestigationReport structure..." }
}
```

**Response (format=markdown):**
```json
{
  "run_id": "270e8dea-6350-4230-a095-f9b1986349d3",
  "markdown": "# Investigation Report — 270e8dea-6350-4230-a095-f9b1986349d3\n\n**Status:** SUCCESS\n..."
}
```

---

### ML Analysis

#### `GET /api/ml/{run_id}`

ML run summary — high-level stats without the full data.

**Response:**
```json
{
  "run_id": "d8e997d5-1a2b-4c3d-8e4f-5a6b7c8d9e0f",
  "started_at": "2026-02-11T18:30:00Z",
  "completed_at": "2026-02-11T18:32:15Z",
  "files_processed": 1,
  "events_parsed": 847293,
  "counts": {
    "aggregations": 312,
    "anomalies": 12,
    "trends": 5,
    "completeness": 48
  }
}
```

Notes:
- Counts are in a nested `counts` object (not flat top-level fields).
- No `domain`, `source_files`, or `errors` fields on this endpoint.

---

#### `GET /api/ml/{run_id}/aggregations`

Paginated aggregation bucket data. This can be hundreds of rows.

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `dimension` | string | Filter by dimension (e.g., `listid`, `recipient_domain`, `outmtaid`) |
| `dimension_value` | string | Filter by specific dimension value |
| `limit` | int | Page size (default 100, max 1000) |
| `offset` | int | Pagination offset (default 0) |

**Response:**
```json
{
  "total": 312,
  "aggregations": [
    {
      "time_window": "2026-02-11T00:00:00",
      "dimension": "listid",
      "dimension_value": "VH-main",
      "total": 142857,
      "delivered": 138571,
      "bounced": 11714,
      "deferred": 1429,
      "complained": 0,
      "delivery_rate": 0.97,
      "bounce_rate": 0.082,
      "deferral_rate": 0.01,
      "complaint_rate": 0.0,
      "pre_edge_latency_mean": 1.23,
      "pre_edge_latency_p50": 0.89,
      "pre_edge_latency_p95": 3.45,
      "delivery_time_mean": 2.1,
      "delivery_time_p50": 1.5,
      "delivery_time_p95": 5.8
    },
    {
      "time_window": "2026-02-11T00:00:00",
      "dimension": "listid",
      "dimension_value": "H-main",
      "total": 98432,
      "delivered": 93710,
      "bounced": 2953,
      "deferred": 1769,
      "complained": 98,
      "delivery_rate": 0.952,
      "bounce_rate": 0.03,
      "deferral_rate": 0.018,
      "complaint_rate": 0.001,
      "pre_edge_latency_mean": 1.45,
      "pre_edge_latency_p50": 1.02,
      "pre_edge_latency_p95": 4.12,
      "delivery_time_mean": 2.8,
      "delivery_time_p50": 1.9,
      "delivery_time_p95": 7.2
    },
    {
      "time_window": "2026-02-11T00:00:00",
      "dimension": "recipient_domain",
      "dimension_value": "gmail.com",
      "total": 287654,
      "delivered": 275745,
      "bounced": 8630,
      "deferred": 3279,
      "complained": 288,
      "delivery_rate": 0.959,
      "bounce_rate": 0.03,
      "deferral_rate": 0.011,
      "complaint_rate": 0.001,
      "pre_edge_latency_mean": 1.1,
      "pre_edge_latency_p50": 0.75,
      "pre_edge_latency_p95": 3.2,
      "delivery_time_mean": 3.5,
      "delivery_time_p50": 2.1,
      "delivery_time_p95": 9.8
    }
  ]
}
```

Notes:
- Latency fields may include `p50`, `p95`, and `mean` variants. The exact set depends on what the ML pipeline computed. Not all `_p99` and `_max` variants are guaranteed to be present.
- Use `segment_thresholds` from `GET /api/domains` to highlight rows where `delivery_rate` is below the segment threshold for that `dimension_value` (when dimension is `listid` or `engagement_segment`).

---

#### `GET /api/ml/{run_id}/anomalies`

All anomalies for an ML run.

**Response** — flat array (not wrapped in an object):
```json
[
  {
    "anomaly_type": "bounce_spike",
    "dimension": "listid",
    "dimension_value": "VH-main",
    "metric": "bounce_rate",
    "current_value": 0.082,
    "baseline_mean": 0.027,
    "z_score": 4.1,
    "severity": "high"
  },
  {
    "anomaly_type": "rate_drop",
    "dimension": "listid",
    "dimension_value": "M-main",
    "metric": "delivery_rate",
    "current_value": 0.87,
    "baseline_mean": 0.92,
    "z_score": -2.8,
    "severity": "medium"
  },
  {
    "anomaly_type": "deferral_spike",
    "dimension": "recipient_domain",
    "dimension_value": "outlook.com",
    "metric": "deferral_rate",
    "current_value": 0.15,
    "baseline_mean": 0.04,
    "z_score": 3.2,
    "severity": "medium"
  }
]
```

Notes:
- Response is a **bare array**, not `{"anomalies": [...], "total": N}`.
- Sort by `severity` (high → medium → low) then by `|z_score|` descending for display.
- Severity badge colors: high=red, medium=amber, low=gray.

---

#### `GET /api/ml/{run_id}/trends`

All trends for an ML run.

**Response** — flat array (not wrapped in an object):
```json
[
  {
    "direction": "degrading",
    "dimension": "listid",
    "dimension_value": "M-main",
    "metric": "delivery_rate",
    "slope": -0.003,
    "r_squared": 0.87,
    "num_points": 14,
    "start_value": 0.92,
    "end_value": 0.87
  },
  {
    "direction": "improving",
    "dimension": "listid",
    "dimension_value": "L-main",
    "metric": "delivery_rate",
    "slope": 0.002,
    "r_squared": 0.72,
    "num_points": 14,
    "start_value": 0.68,
    "end_value": 0.71
  },
  {
    "direction": "stable",
    "dimension": "recipient_domain",
    "dimension_value": "gmail.com",
    "metric": "bounce_rate",
    "slope": 0.0001,
    "r_squared": 0.12,
    "num_points": 14,
    "start_value": 0.028,
    "end_value": 0.029
  }
]
```

Notes:
- Response is a **bare array**, not `{"trends": [...], "total": N}`.
- Direction arrows: red ↓ for degrading, green ↑ for improving, gray → for stable.
- `r_squared` indicates fit quality (closer to 1.0 = more reliable trend).

---

#### `GET /api/ml/{run_id}/completeness`

Data completeness metrics — zero-value rates by field/dimension.

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `dimension` | string | Filter by dimension |
| `field_name` | string | Filter by field name |
| `limit` | int | Page size (default 100, max 1000) |
| `offset` | int | Pagination offset (default 0) |

**Response:**
```json
{
  "total": 48,
  "completeness": [
    {
      "time_window": "2026-02-11T00:00:00",
      "dimension": "listid",
      "dimension_value": "VH-main",
      "total_records": 142857,
      "field_name": "clicktrackingid",
      "zero_count": 4286,
      "zero_rate": 0.03
    },
    {
      "time_window": "2026-02-11T00:00:00",
      "dimension": "listid",
      "dimension_value": "DS-main",
      "total_records": 31204,
      "field_name": "clicktrackingid",
      "zero_count": 3744,
      "zero_rate": 0.12
    },
    {
      "time_window": "2026-02-11T00:00:00",
      "dimension": "listid",
      "dimension_value": "NM-main",
      "total_records": 18456,
      "field_name": "xmrid_account_id",
      "zero_count": 9228,
      "zero_rate": 0.50
    }
  ]
}
```

Notes:
- Highlight `zero_rate` > 0.50 in red, > 0.20 in amber.
- The `completeness_fields` array from `GET /api/domains` tells you which fields to expect.

---

### Knowledge Store

#### `GET /api/knowledge/search`

Search the knowledge store across all tiers.

**Query parameters:**
| Param | Type | Description |
|-------|------|-------------|
| `q` | string | Search query text (required, min 1 char) |
| `tier` | string | Filter by tier: `hypothesis`, `finding`, `truth`, `grounded` |
| `top_k` | int | Max results (default 10, max 100) |

**Response:**
```json
{
  "results": [
    {
      "entry_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
      "tier": "grounded",
      "statement": "VH (Very Hot) segment contains recipients who clicked or opened within the last 30 days. This segment routes through the highest-reputation IP pools and is expected to maintain delivery rates above 95%.",
      "topic": "engagement segments",
      "dimension": null,
      "dimension_value": null,
      "scope": "community",
      "account_id": null,
      "confidence": 1.0,
      "observation_count": 1,
      "similarity": 0.92,
      "weighted_score": 0.92,
      "finding_status": null,
      "source_run_ids": []
    },
    {
      "entry_id": "b2c3d4e5-f6a7-8901-bcde-f12345678901",
      "tier": "finding",
      "statement": "VH segment baseline bounce rate is 2.7% across 14 days of data from Feb 1-14, 2026. This is within the expected range for high-reputation IP pools sending to engaged recipients.",
      "topic": "VH bounce baseline",
      "dimension": "listid",
      "dimension_value": "VH-main",
      "scope": "community",
      "account_id": null,
      "confidence": 0.75,
      "observation_count": 3,
      "similarity": 0.85,
      "weighted_score": 0.383,
      "finding_status": "confirmed",
      "source_run_ids": ["270e8dea-6350-4230-a095-f9b1986349d3"]
    },
    {
      "entry_id": "c3d4e5f6-a7b8-9012-cdef-123456789012",
      "tier": "hypothesis",
      "statement": "Account 269124 DKIM non-compliance on shared IP pool may be contributing to pool-wide reputation degradation at gmail.com.",
      "topic": "compliance cascade",
      "dimension": "xmrid_account_id",
      "dimension_value": "269124",
      "scope": "account",
      "account_id": "269124",
      "confidence": 0.4,
      "observation_count": 1,
      "similarity": 0.78,
      "weighted_score": 0.094,
      "finding_status": null,
      "source_run_ids": ["270e8dea-6350-4230-a095-f9b1986349d3"]
    }
  ]
}
```

Notes:
- The text field is `statement` (not `content`).
- The relevance score is `weighted_score` (not `score`). Computed as `similarity × tier_weight × confidence`.
- Fields are **flat** — no nested `metadata` object. `dimension`, `dimension_value`, `scope`, `account_id`, `observation_count`, `finding_status`, `source_run_ids` are all top-level.
- `finding_status` is only populated for `finding` tier entries. It is `null` for other tiers.
- `source_run_ids` may be empty (especially for `grounded` entries imported from the knowledge corpus).
- Sort results by `weighted_score` descending (they come pre-sorted from the API).
- Use tier badge colors from `GET /api/meta` (`emerald`/`blue`/`amber`/`gray`).

---

#### `GET /api/knowledge/stats`

Counts and high-level stats per tier.

**Response** — flat array of objects (not a nested dict):
```json
[
  {
    "tier": "hypothesis",
    "collection": "knowledge_hypothesis",
    "count": 8,
    "weight": 0.3,
    "description": "LLM-generated, untested"
  },
  {
    "tier": "finding",
    "collection": "knowledge_finding",
    "count": 12,
    "weight": 0.6,
    "description": "ML-tested, evidence attached"
  },
  {
    "tier": "truth",
    "collection": "knowledge_truth",
    "count": 0,
    "weight": 0.85,
    "description": "ML + LLM + human confirmed"
  },
  {
    "tier": "grounded",
    "collection": "knowledge_grounded",
    "count": 1142,
    "weight": 1.0,
    "description": "Authoritative domain knowledge (read-only)"
  }
]
```

Notes:
- Response is a **bare array**, not `{"tiers": {...}, "total": N}`.
- Each element includes `collection` (Weaviate collection name) and `weight` (tier weight used in scoring).
- Compute total client-side by summing `count` values.
- Display as a summary bar or badge row. Use tier colors from `GET /api/meta`.

---

## Frontend Pages

### 1. Runs List (Dashboard Home)

The landing page. Shows all pipeline runs in reverse chronological order.

**Layout:**
- Filter bar at top: domain dropdown (populated from `GET /api/domains`), command type dropdown (`analyze_email`/`investigate` from `GET /api/meta` → `commands`), status dropdown (from `run_statuses`), source file search, free-text search
- Table with columns:
  - **Common**: Run ID (truncated, monospace), Domain, Command (badge), Created At, Duration (computed from `started_at`/`completed_at`)
  - **`analyze_email` rows**: Events Parsed, Anomaly Count, Trend Count
  - **`investigate` rows**: Status (badge), Label, Finding Count, Hypothesis Count
- Click a row to navigate to detail view (investigation detail or ML detail depending on `command`)
- Pagination controls at bottom

**Visual cues:**
- Status badges (investigate only): green=success, amber=partial, red=failed, gray=dry_run
- Command badges: blue=investigate, teal=analyze_email
- Duration displayed as `9m 22s` (compute from `started_at` and `completed_at`)

### 2. Investigation Detail

Drill-down into a single investigation run. Data from `GET /api/investigations/{run_id}`.

**Layout — Header:**
- Run ID (monospace, copyable)
- Status badge
- Label (if present)
- Source files (list, each copyable)
- ML Run ID (link to ML detail view — navigates to ML page with this `ml_run_id`)
- Timing: started_at, completed_at, duration_seconds
- Iteration count
- Finding/hypothesis counts
- Quality warnings (collapsible, amber if present)

**Layout — Body (tabbed or sectioned):**

**Findings tab:**
- Grouped by `status`: confirmed first, then inconclusive, then disproven
- Each finding is a card:
  - `topic_title` (heading)
  - `statement` (blockquote style)
  - `status` badge (green=confirmed, gray=inconclusive, red=disproven)
  - `evidence` (bulleted list)
  - `metrics_cited` (key-value table — keys are metric names, values are numbers)
  - `is_fallback` badge if true (amber, indicates tool-use failure fallback)
  - `quality_warnings` (amber list if non-empty)

**Hypotheses tab:**
- List of cards:
  - `topic_title`
  - `statement`
  - `reasoning` (expandable)

**Synthesis tab:**
- Rendered markdown of `synthesis_narrative`
- Show "No synthesis available" if `null`

**Report tab:**
- Toggle between rendered markdown view and raw JSON view
- Fetched from `GET /api/investigations/{run_id}/report`

### 3. ML Analysis Detail

Drill-down into ML pipeline output. Data from `GET /api/ml/{run_id}` (summary) plus sub-endpoints.

The tabs and column names are driven by the domain schema from `GET /api/domains` — the frontend reads `ml_data_types` to determine what dimension filters to show and how to label values.

**Layout — Header:**
- Run ID (monospace), timing (`started_at`, `completed_at`), `files_processed`, `events_parsed`
- Summary counts from `counts` object: aggregations, anomalies, trends, completeness

**Layout — Body (tabbed):**

**Anomalies tab** (data from `GET /api/ml/{run_id}/anomalies`):
- Table: `severity` (badge), `anomaly_type`, `dimension`, `dimension_value`, `metric`, `current_value` vs `baseline_mean`, `z_score`
- Sortable by severity and z_score
- Color-code severity: high=red, medium=amber, low=gray
- Anomaly type labels from domain schema `anomaly_types`

**Trends tab** (data from `GET /api/ml/{run_id}/trends`):
- Table: `direction` (arrow icon), `dimension`, `dimension_value`, `metric`, `slope`, `r_squared`, `num_points`, `start_value` → `end_value`
- Color: red arrow for degrading, green for improving, gray for stable

**Aggregations tab** (data from `GET /api/ml/{run_id}/aggregations`):
- Dimension filter dropdown populated from domain schema `dimensions`
- Table shows all count, rate, and latency columns present in the data
- Sortable, paginated
- Highlight rows using `segment_thresholds` from domain schema: if the row's `dimension_value` matches a segment code (VH, H, M, L, VL) and `delivery_rate` < threshold → amber highlight

**Completeness tab** (data from `GET /api/ml/{run_id}/completeness`):
- Table: `dimension`, `dimension_value`, `field_name`, `zero_count`, `zero_rate`, `total_records`
- Field filter dropdown populated from domain schema `completeness_fields`
- Highlight `zero_rate` > 0.50 in red, > 0.20 in amber

### 4. Knowledge Browser

Browse the knowledge store. Data from `GET /api/knowledge/search` and `GET /api/knowledge/stats`.

**Layout:**
- Search bar (always visible, maps to `q` parameter)
- Tier filter (checkboxes: grounded, truth, finding, hypothesis — maps to `tier` parameter)
- Tier stats summary (from `GET /api/knowledge/stats` — show count per tier as badges)
- Results as cards:
  - Tier badge (color from `GET /api/meta` → `knowledge_tiers[].color`)
  - `topic` (heading)
  - `statement` (truncated with expand)
  - `confidence` score (formatted as percentage)
  - `weighted_score` (relevance score, secondary display)
  - `dimension` / `dimension_value` (if present — show as a tag)
  - `scope` badge (community or account)
  - `finding_status` badge (if tier=finding: confirmed/disproven/inconclusive)
  - `observation_count` (small metadata line)
  - `source_run_ids` (links to investigation detail, if non-empty)

---

## Technical Notes for Implementation

### Frontend

- No authentication — all endpoints are open.
- Use a simple HTTP client (fetch or axios) to call the backend API.
- All data is read-only — no POST/PUT/DELETE operations.
- Markdown rendering: use a markdown rendering library for the synthesis narrative and report views.
- The frontend should handle the backend being unavailable gracefully (show connection error, not crash).
- Mobile responsiveness is not required — this is a desktop tool.

### CORS

The backend enables CORS for `*` origins. This is an internal tool with no auth, so permissive CORS is acceptable.

### Ports

- Frontend dev server: `localhost:3000` (or Vite default)
- Backend API: `localhost:20005`

---

## Out of Scope (v1)

These are planned for later versions:

- **Write operations**: No creating, editing, promoting, or deprecating anything from the UI
- **Authentication**: No login, no user accounts
- **Real-time updates**: No WebSocket/SSE — standard request/response
- **Mobile support**: Desktop only
- **Charts/visualizations**: Tables are sufficient for v1 (charts can be added later)
- **Comparison view**: Side-by-side A/B investigation comparison (label-based)
- **Export**: CSV/PDF export of data
