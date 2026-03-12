export const mockDomains = [
  {
    name: "email_delivery",
    description: "Email delivery analytics — reputation, compliance, engagement, ISP, diagnostics",
    roles: [
      { name: "reputation", prompt_supplement: "IP and domain reputation, warming, throttling, feedback loops" },
      { name: "compliance", prompt_supplement: "SPF, DKIM, DMARC, ARC authentication and policy" },
      { name: "engagement", prompt_supplement: "Segment behavior, list hygiene, sunset policies" },
      { name: "isp", prompt_supplement: "Provider-specific filtering (Gmail, Microsoft, Yahoo, Apple)" },
      { name: "diagnostics", prompt_supplement: "General diagnostics, bounce analysis, data completeness" }
    ],
    ml_data_types: {
      dimensions: ["listid", "recipient_domain", "outmtaid", "engagement_segment", "listid_type", "compliance_status", "xmrid_account_id", "smtp_category"],
      metrics: ["delivery_rate", "bounce_rate", "deferral_rate", "complaint_rate", "pre_edge_latency_mean", "delivery_time_mean"],
      delivery_statuses: ["delivered", "bounced", "deferred", "dropped", "complaint", "unknown"],
      smtp_categories: ["throttling", "blacklist", "reputation", "auth_failure", "content_rejection", "recipient_unknown", "policy", "network", "success", "other"],
      anomaly_types: ["rate_drop", "rate_spike", "bounce_spike", "deferral_spike", "complaint_spike"],
      trend_directions: ["improving", "degrading", "stable"],
      completeness_fields: ["clicktrackingid", "xmrid_account_id", "xmrid_contact_id", "last_active_ts", "contact_added_ts", "op_queue_time_parsed"],
      segment_thresholds: { VH: 0.95, H: 0.90, M: 0.85, L: 0.75, VL: 0.60 }
    }
  }
];

export const mockMeta = {
  finding_statuses: ["confirmed", "disproven", "inconclusive"],
  review_assessments: ["supported", "weak_evidence", "contradicted", "gap_identified"],
  review_actions: ["accept", "investigate_further", "flag_for_human"],
  knowledge_tiers: [
    { name: "hypothesis", weight: 0.3, description: "LLM-generated, untested", color: "gray" },
    { name: "finding", weight: 0.6, description: "ML-tested, evidence attached", color: "amber" },
    { name: "truth", weight: 0.85, description: "ML + LLM + human confirmed", color: "blue" },
    { name: "grounded", weight: 1.0, description: "Authoritative domain knowledge (read-only)", color: "emerald" }
  ],
  run_statuses: ["success", "partial", "failed", "dry_run"],
  commands: ["analyze_email", "investigate", "investigate_http"]
};

const ML_RUN_1 = "d8e997d5-1a2b-4c3d-8e4f-5a6b7c8d9e0f";
const ML_RUN_2 = "f1a2b3c4-d5e6-7890-abcd-ef1234567890";
const ML_RUN_3 = "a9b8c7d6-e5f4-3210-9876-543210fedcba";
const INV_RUN_1 = "270e8dea-6350-4230-a095-f9b1986349d3";
const INV_RUN_2 = "81f3c2d4-7a6b-4e5f-9c8d-0e1f2a3b4c5d";
const INV_RUN_3 = "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f";

export const mockRuns = {
  total: 6,
  runs: [
    {
      run_id: INV_RUN_3,
      domain: "email_delivery",
      command: "investigate",
      created_at: "2026-02-14T14:22:10Z",
      source_files: ["raw-logs/delivery_logs.2026-02-14"],
      started_at: "2026-02-14T14:22:10Z",
      completed_at: "2026-02-14T14:31:45Z",
      status: "partial",
      is_dry_run: false,
      label: "daily-check-feb14",
      ml_run_id: ML_RUN_3,
      finding_count: 2,
      hypothesis_count: 3,
      iteration_count: 1
    },
    {
      run_id: ML_RUN_3,
      domain: "email_delivery",
      command: "analyze_email",
      created_at: "2026-02-14T14:10:00Z",
      source_files: ["raw-logs/delivery_logs.2026-02-14"],
      started_at: "2026-02-14T14:10:00Z",
      completed_at: "2026-02-14T14:12:33Z",
      files_processed: 1,
      events_parsed: 923104,
      anomaly_count: 8,
      trend_count: 4
    },
    {
      run_id: INV_RUN_2,
      domain: "email_delivery",
      command: "investigate",
      created_at: "2026-02-11T20:15:00Z",
      source_files: ["raw-logs/delivery_logs.2026-02-11"],
      started_at: "2026-02-11T20:15:00Z",
      completed_at: "2026-02-11T20:25:30Z",
      status: "success",
      is_dry_run: true,
      label: "A-without-knowledge",
      ml_run_id: ML_RUN_1,
      finding_count: 3,
      hypothesis_count: 1,
      iteration_count: 1
    },
    {
      run_id: INV_RUN_1,
      domain: "email_delivery",
      command: "investigate",
      created_at: "2026-02-11T19:04:57Z",
      source_files: ["raw-logs/delivery_logs.2026-02-11"],
      started_at: "2026-02-11T19:04:57Z",
      completed_at: "2026-02-11T19:14:19Z",
      status: "success",
      is_dry_run: false,
      label: "B-with-knowledge",
      ml_run_id: ML_RUN_1,
      finding_count: 4,
      hypothesis_count: 2,
      iteration_count: 2
    },
    {
      run_id: ML_RUN_1,
      domain: "email_delivery",
      command: "analyze_email",
      created_at: "2026-02-11T18:30:00Z",
      source_files: ["raw-logs/delivery_logs.2026-02-11"],
      started_at: "2026-02-11T18:30:00Z",
      completed_at: "2026-02-11T18:32:15Z",
      files_processed: 1,
      events_parsed: 847293,
      anomaly_count: 12,
      trend_count: 5
    },
    {
      run_id: ML_RUN_2,
      domain: "email_delivery",
      command: "analyze_email",
      created_at: "2026-02-10T08:00:00Z",
      source_files: ["raw-logs/delivery_logs.2026-02-10"],
      started_at: "2026-02-10T08:00:00Z",
      completed_at: "2026-02-10T08:01:45Z",
      files_processed: 1,
      events_parsed: 712450,
      anomaly_count: 3,
      trend_count: 2
    }
  ]
};

export const mockInvestigations: Record<string, any> = {
  [INV_RUN_1]: {
    run_id: INV_RUN_1,
    domain: "email_delivery",
    started_at: "2026-02-11T19:04:57Z",
    completed_at: "2026-02-11T19:14:19Z",
    duration_seconds: 562.0,
    status: "success",
    is_dry_run: false,
    label: "B-with-knowledge",
    ml_run_id: ML_RUN_1,
    iteration_count: 2,
    finding_count: 4,
    hypothesis_count: 2,
    checkpoint_digest: "## Investigation Checkpoint\n\n### Confirmed Findings\n- VH segment bounce spike on gmail.com\n- M segment delivery rate degradation\n- Data completeness regression in clicktrackingid\n\n### Inconclusive\n- Account 269124 DKIM compliance failure\n\n### Circuit Breaker\nConverged after 2 iterations. No new findings in iteration 2.",
    quality_warnings: ["VH bounce analysis: confirmed_without_ml_verification"],
    source_files: ["raw-logs/delivery_logs.2026-02-11"],
    findings: [
      {
        topic_title: "VH segment bounce spike on gmail.com",
        statement: "VH segment bounce rate to gmail.com spiked to 8.2%, 3x the historical baseline of 2.7%. The spike is concentrated on outmtaid 10.20.30.40 which shows 94% of the bounces.",
        status: "confirmed",
        evidence: [
          "Aggregation: VH-main bounce_rate=0.082 vs 14-day baseline 0.027",
          "Anomaly: bounce_spike severity=high z_score=4.1 for VH-main",
          "Aggregation by outmtaid: 10.20.30.40 shows bounce_rate=0.31"
        ],
        metrics_cited: { bounce_rate: 0.082, baseline_mean: 0.027, z_score: 4.1 },
        is_fallback: false,
        quality_warnings: []
      },
      {
        topic_title: "M segment delivery rate degradation",
        statement: "M segment delivery rate has degraded from 92% to 87% over the past 14 days, with a statistically significant downward trend (R\u00b2=0.87).",
        status: "confirmed",
        evidence: [
          "Trend: M-main delivery_rate slope=-0.003 R\u00b2=0.87 over 14 points",
          "Aggregation: M-main current delivery_rate=0.87 vs segment threshold 0.85"
        ],
        metrics_cited: { delivery_rate: 0.87, slope: -0.003, r_squared: 0.87 },
        is_fallback: false,
        quality_warnings: []
      },
      {
        topic_title: "Account 269124 DKIM compliance failure",
        statement: "Account 269124 has 100% DKIM failure on shared IP pool, but impact is limited \u2014 account represents only 0.3% of pool volume.",
        status: "inconclusive",
        evidence: [
          "Aggregation by xmrid_account_id: 269124 shows dkim_fail_rate=1.0",
          "Volume: 269124 total=2,847 vs pool total=948,000"
        ],
        metrics_cited: { dkim_fail_rate: 1.0, account_volume: 2847, pool_volume: 948000 },
        is_fallback: false,
        quality_warnings: ["confirmed_without_ml_verification"]
      },
      {
        topic_title: "Data completeness regression in clicktrackingid",
        statement: "clicktrackingid zero-value rate increased from 3% to 12% between Feb 11 and Feb 14, concentrated in DS and NM segments.",
        status: "confirmed",
        evidence: [
          "Completeness: clicktrackingid zero_rate=0.12 for DS-main (was 0.03 on Feb 11)",
          "Completeness: clicktrackingid zero_rate=0.09 for NM-main"
        ],
        metrics_cited: { zero_rate_current: 0.12, zero_rate_baseline: 0.03 },
        is_fallback: false,
        quality_warnings: []
      }
    ],
    hypotheses: [
      {
        topic_title: "Account 269124 compliance cascade risk",
        statement: "Non-compliant DKIM on account 269124 may be degrading shared pool reputation at gmail.com, contributing to the VH bounce spike.",
        reasoning: "Account 269124 shows 100% DKIM failure on the same IP pool where VH bounces spiked. Gmail's postmaster documentation indicates pool-level reputation penalties for mixed compliance. However, account volume is only 0.3% of the pool, which may be below Gmail's penalty threshold."
      },
      {
        topic_title: "DS/NM clicktrackingid regression source",
        statement: "The clicktrackingid completeness regression in DS/NM segments may originate from a specific automation workflow that stopped populating the field after a platform update.",
        reasoning: "DS and NM segments are predominantly system-generated traffic (automation, transactional). The regression appeared abruptly between Feb 11-14, consistent with a deployment change rather than gradual drift."
      }
    ],
    synthesis_narrative: "## Executive Summary\n\nThis investigation examined 847,293 email delivery events from February 11, 2026. Four findings were confirmed across reputation, compliance, and data quality dimensions.\n\n### Key Findings\n\n**VH Bounce Spike (High Severity)**: The VH segment experienced a 3x bounce rate spike to gmail.com, concentrated on a single outbound MTA IP. This warrants immediate investigation of IP reputation status.\n\n**M Segment Degradation**: Medium engagement segment shows a statistically significant 14-day delivery rate decline from 92% to 87%, approaching the segment threshold of 85%.\n\n**Data Quality Regression**: clicktrackingid completeness dropped from 97% to 88% in DS/NM segments, indicating a potential plumbing issue in automation workflows.\n\n### Untested Hypotheses\n\nTwo hypotheses remain for future investigation: possible compliance cascade from account 269124, and the specific automation source of the clicktrackingid regression."
  },
  [INV_RUN_2]: {
    run_id: INV_RUN_2,
    domain: "email_delivery",
    started_at: "2026-02-11T20:15:00Z",
    completed_at: "2026-02-11T20:25:30Z",
    duration_seconds: 630.0,
    status: "success",
    is_dry_run: true,
    label: "A-without-knowledge",
    ml_run_id: ML_RUN_1,
    iteration_count: 1,
    finding_count: 3,
    hypothesis_count: 1,
    checkpoint_digest: "## Investigation Checkpoint\n\n### Confirmed Findings\n- VH segment bounce spike on gmail.com\n- M segment delivery rate degradation\n\n### Inconclusive\n- Data completeness regression\n\n### Circuit Breaker\nConverged after 1 iteration.",
    quality_warnings: [],
    source_files: ["raw-logs/delivery_logs.2026-02-11"],
    findings: [
      {
        topic_title: "VH segment bounce spike on gmail.com",
        statement: "VH segment bounce rate to gmail.com spiked to 8.2%, significantly above historical norms.",
        status: "confirmed",
        evidence: [
          "Aggregation: VH-main bounce_rate=0.082 vs baseline 0.027",
          "Anomaly: bounce_spike severity=high z_score=4.1"
        ],
        metrics_cited: { bounce_rate: 0.082, baseline_mean: 0.027 },
        is_fallback: false,
        quality_warnings: []
      },
      {
        topic_title: "M segment delivery rate degradation",
        statement: "M segment delivery rate declining over 14 days from 92% to 87%.",
        status: "confirmed",
        evidence: [
          "Trend: M-main delivery_rate slope=-0.003 R\u00b2=0.87"
        ],
        metrics_cited: { delivery_rate: 0.87, slope: -0.003 },
        is_fallback: false,
        quality_warnings: []
      },
      {
        topic_title: "clicktrackingid data gap",
        statement: "Elevated zero-value rates for clicktrackingid in DS segment, but insufficient historical data to confirm trend.",
        status: "inconclusive",
        evidence: [
          "Completeness: clicktrackingid zero_rate=0.12 for DS-main"
        ],
        metrics_cited: { zero_rate: 0.12 },
        is_fallback: true,
        quality_warnings: []
      }
    ],
    hypotheses: [
      {
        topic_title: "IP reputation degradation",
        statement: "The VH bounce spike may be caused by IP 10.20.30.40 landing on a Gmail blacklist.",
        reasoning: "94% of bounces are concentrated on a single IP. This pattern is consistent with IP-level blocking rather than content or domain issues."
      }
    ],
    synthesis_narrative: "## Executive Summary\n\nDry run investigation of 847,293 events. Two findings confirmed, one inconclusive. Without knowledge store context, the investigation converged in a single iteration with fewer findings than the knowledge-assisted run.\n\n### Key Findings\n\n**VH Bounce Spike**: Confirmed 3x bounce rate increase on gmail.com.\n\n**M Segment Decline**: Confirmed 14-day degradation trend.\n\n### Limitations\n\nDry run mode \u2014 no knowledge store was consulted."
  },
  [INV_RUN_3]: {
    run_id: INV_RUN_3,
    domain: "email_delivery",
    started_at: "2026-02-14T14:22:10Z",
    completed_at: "2026-02-14T14:31:45Z",
    duration_seconds: 575.0,
    status: "partial",
    is_dry_run: false,
    label: "daily-check-feb14",
    ml_run_id: ML_RUN_3,
    iteration_count: 1,
    finding_count: 2,
    hypothesis_count: 3,
    checkpoint_digest: "## Investigation Checkpoint\n\n### Confirmed Findings\n- Outlook deferral spike\n- L segment improvement\n\n### Circuit Breaker\nPartial completion \u2014 timeout reached during iteration 2.",
    quality_warnings: ["timeout_during_iteration_2", "incomplete_specialist_coverage"],
    source_files: ["raw-logs/delivery_logs.2026-02-14"],
    findings: [
      {
        topic_title: "Outlook.com deferral rate spike",
        statement: "Deferral rate to outlook.com spiked to 15%, up from baseline of 4%. SMTP response codes indicate throttling.",
        status: "confirmed",
        evidence: [
          "Anomaly: deferral_spike severity=medium z_score=3.2 for outlook.com",
          "SMTP category breakdown: 78% throttling responses"
        ],
        metrics_cited: { deferral_rate: 0.15, baseline_mean: 0.04, z_score: 3.2 },
        is_fallback: false,
        quality_warnings: []
      },
      {
        topic_title: "L segment delivery improvement",
        statement: "L segment delivery rate improved from 68% to 71% over 14 days, a positive but modest trend.",
        status: "confirmed",
        evidence: [
          "Trend: L-main delivery_rate slope=+0.002 R\u00b2=0.72 over 14 points"
        ],
        metrics_cited: { delivery_rate: 0.71, slope: 0.002, r_squared: 0.72 },
        is_fallback: false,
        quality_warnings: []
      }
    ],
    hypotheses: [
      {
        topic_title: "Microsoft throttling due to volume spike",
        statement: "Outlook throttling may be triggered by a sudden volume increase from new campaign sends.",
        reasoning: "Volume to outlook.com increased 40% day-over-day. Microsoft's anti-spam systems are known to throttle based on volume deviation from sender profile."
      },
      {
        topic_title: "L segment improvement from sunset policy",
        statement: "The L segment improvement may reflect recent sunset policy changes removing chronically unengaged recipients.",
        reasoning: "L segment total volume decreased 8% while delivery rate improved, consistent with list pruning."
      },
      {
        topic_title: "Cross-ISP reputation spillover",
        statement: "The outlook.com throttling may be a leading indicator of broader ISP reputation issues that could affect Yahoo and Apple Mail.",
        reasoning: "Microsoft often acts as an early warning system for reputation problems. If the throttling is reputation-based rather than volume-based, other ISPs may follow."
      }
    ],
    synthesis_narrative: null
  }
};

export const mockMLSummaries: Record<string, any> = {
  [ML_RUN_1]: {
    run_id: ML_RUN_1,
    domain: "email_delivery",
    started_at: "2026-02-11T18:30:00Z",
    completed_at: "2026-02-11T18:32:15Z",
    files_processed: 1,
    events_parsed: 847293,
    counts: { aggregations: 312, anomalies: 12, trends: 5, completeness: 48 }
  },
  [ML_RUN_2]: {
    run_id: ML_RUN_2,
    domain: "email_delivery",
    started_at: "2026-02-10T08:00:00Z",
    completed_at: "2026-02-10T08:01:45Z",
    files_processed: 1,
    events_parsed: 712450,
    counts: { aggregations: 280, anomalies: 3, trends: 2, completeness: 36 }
  },
  [ML_RUN_3]: {
    run_id: ML_RUN_3,
    domain: "email_delivery",
    started_at: "2026-02-14T14:10:00Z",
    completed_at: "2026-02-14T14:12:33Z",
    files_processed: 1,
    events_parsed: 923104,
    counts: { aggregations: 345, anomalies: 8, trends: 4, completeness: 52 }
  }
};

export const mockAnomalies: Record<string, any[]> = {
  [ML_RUN_1]: [
    { anomaly_type: "bounce_spike", dimension: "listid", dimension_value: "VH-main", metric: "bounce_rate", current_value: 0.082, baseline_mean: 0.027, z_score: 4.1, severity: "high" },
    { anomaly_type: "rate_drop", dimension: "listid", dimension_value: "M-main", metric: "delivery_rate", current_value: 0.87, baseline_mean: 0.92, z_score: -2.8, severity: "medium" },
    { anomaly_type: "deferral_spike", dimension: "recipient_domain", dimension_value: "outlook.com", metric: "deferral_rate", current_value: 0.15, baseline_mean: 0.04, z_score: 3.2, severity: "medium" },
    { anomaly_type: "complaint_spike", dimension: "listid", dimension_value: "L-main", metric: "complaint_rate", current_value: 0.005, baseline_mean: 0.001, z_score: 3.8, severity: "high" },
    { anomaly_type: "rate_drop", dimension: "recipient_domain", dimension_value: "yahoo.com", metric: "delivery_rate", current_value: 0.91, baseline_mean: 0.95, z_score: -2.1, severity: "medium" },
    { anomaly_type: "bounce_spike", dimension: "outmtaid", dimension_value: "10.20.30.40", metric: "bounce_rate", current_value: 0.31, baseline_mean: 0.02, z_score: 8.5, severity: "high" },
    { anomaly_type: "rate_spike", dimension: "listid", dimension_value: "DS-main", metric: "deferral_rate", current_value: 0.08, baseline_mean: 0.03, z_score: 2.5, severity: "low" },
    { anomaly_type: "bounce_spike", dimension: "recipient_domain", dimension_value: "gmail.com", metric: "bounce_rate", current_value: 0.045, baseline_mean: 0.02, z_score: 3.0, severity: "medium" },
    { anomaly_type: "complaint_spike", dimension: "recipient_domain", dimension_value: "aol.com", metric: "complaint_rate", current_value: 0.008, baseline_mean: 0.002, z_score: 2.8, severity: "medium" },
    { anomaly_type: "rate_drop", dimension: "engagement_segment", dimension_value: "VL", metric: "delivery_rate", current_value: 0.52, baseline_mean: 0.58, z_score: -2.3, severity: "medium" },
    { anomaly_type: "deferral_spike", dimension: "smtp_category", dimension_value: "throttling", metric: "deferral_rate", current_value: 0.22, baseline_mean: 0.08, z_score: 3.5, severity: "high" },
    { anomaly_type: "rate_drop", dimension: "xmrid_account_id", dimension_value: "269124", metric: "delivery_rate", current_value: 0.45, baseline_mean: 0.89, z_score: -5.2, severity: "high" }
  ],
  [ML_RUN_2]: [
    { anomaly_type: "rate_drop", dimension: "listid", dimension_value: "VL-main", metric: "delivery_rate", current_value: 0.55, baseline_mean: 0.60, z_score: -2.0, severity: "low" },
    { anomaly_type: "deferral_spike", dimension: "recipient_domain", dimension_value: "comcast.net", metric: "deferral_rate", current_value: 0.09, baseline_mean: 0.03, z_score: 2.4, severity: "low" },
    { anomaly_type: "bounce_spike", dimension: "outmtaid", dimension_value: "10.20.30.41", metric: "bounce_rate", current_value: 0.05, baseline_mean: 0.02, z_score: 2.1, severity: "low" }
  ],
  [ML_RUN_3]: [
    { anomaly_type: "deferral_spike", dimension: "recipient_domain", dimension_value: "outlook.com", metric: "deferral_rate", current_value: 0.18, baseline_mean: 0.04, z_score: 3.8, severity: "high" },
    { anomaly_type: "bounce_spike", dimension: "listid", dimension_value: "VH-main", metric: "bounce_rate", current_value: 0.055, baseline_mean: 0.027, z_score: 2.5, severity: "medium" },
    { anomaly_type: "rate_drop", dimension: "listid", dimension_value: "M-main", metric: "delivery_rate", current_value: 0.86, baseline_mean: 0.92, z_score: -3.0, severity: "medium" },
    { anomaly_type: "complaint_spike", dimension: "listid", dimension_value: "L-main", metric: "complaint_rate", current_value: 0.004, baseline_mean: 0.001, z_score: 3.2, severity: "medium" },
    { anomaly_type: "rate_spike", dimension: "recipient_domain", dimension_value: "outlook.com", metric: "bounce_rate", current_value: 0.06, baseline_mean: 0.025, z_score: 2.8, severity: "medium" },
    { anomaly_type: "deferral_spike", dimension: "smtp_category", dimension_value: "throttling", metric: "deferral_rate", current_value: 0.25, baseline_mean: 0.08, z_score: 4.0, severity: "high" },
    { anomaly_type: "rate_drop", dimension: "engagement_segment", dimension_value: "VL", metric: "delivery_rate", current_value: 0.50, baseline_mean: 0.58, z_score: -2.5, severity: "medium" },
    { anomaly_type: "bounce_spike", dimension: "xmrid_account_id", dimension_value: "269124", metric: "bounce_rate", current_value: 0.42, baseline_mean: 0.08, z_score: 5.1, severity: "high" }
  ]
};

export const mockTrends: Record<string, any[]> = {
  [ML_RUN_1]: [
    { direction: "degrading", dimension: "listid", dimension_value: "M-main", metric: "delivery_rate", slope: -0.003, r_squared: 0.87, num_points: 14, start_value: 0.92, end_value: 0.87 },
    { direction: "improving", dimension: "listid", dimension_value: "L-main", metric: "delivery_rate", slope: 0.002, r_squared: 0.72, num_points: 14, start_value: 0.68, end_value: 0.71 },
    { direction: "stable", dimension: "recipient_domain", dimension_value: "gmail.com", metric: "bounce_rate", slope: 0.0001, r_squared: 0.12, num_points: 14, start_value: 0.028, end_value: 0.029 },
    { direction: "degrading", dimension: "listid", dimension_value: "VL-main", metric: "delivery_rate", slope: -0.004, r_squared: 0.65, num_points: 14, start_value: 0.58, end_value: 0.52 },
    { direction: "stable", dimension: "recipient_domain", dimension_value: "yahoo.com", metric: "delivery_rate", slope: -0.0005, r_squared: 0.08, num_points: 14, start_value: 0.95, end_value: 0.94 }
  ],
  [ML_RUN_2]: [
    { direction: "degrading", dimension: "listid", dimension_value: "M-main", metric: "delivery_rate", slope: -0.002, r_squared: 0.78, num_points: 14, start_value: 0.93, end_value: 0.90 },
    { direction: "stable", dimension: "recipient_domain", dimension_value: "gmail.com", metric: "delivery_rate", slope: 0.0002, r_squared: 0.05, num_points: 14, start_value: 0.96, end_value: 0.96 }
  ],
  [ML_RUN_3]: [
    { direction: "degrading", dimension: "listid", dimension_value: "M-main", metric: "delivery_rate", slope: -0.003, r_squared: 0.89, num_points: 14, start_value: 0.92, end_value: 0.86 },
    { direction: "improving", dimension: "listid", dimension_value: "L-main", metric: "delivery_rate", slope: 0.002, r_squared: 0.72, num_points: 14, start_value: 0.68, end_value: 0.71 },
    { direction: "degrading", dimension: "recipient_domain", dimension_value: "outlook.com", metric: "deferral_rate", slope: 0.008, r_squared: 0.91, num_points: 14, start_value: 0.04, end_value: 0.15 },
    { direction: "stable", dimension: "recipient_domain", dimension_value: "gmail.com", metric: "bounce_rate", slope: 0.0003, r_squared: 0.15, num_points: 14, start_value: 0.028, end_value: 0.031 }
  ]
};

export const mockAggregations: Record<string, any[]> = {
  [ML_RUN_1]: [
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "VH-main", total: 142857, delivered: 138571, bounced: 11714, deferred: 1429, complained: 0, delivery_rate: 0.97, bounce_rate: 0.082, deferral_rate: 0.01, complaint_rate: 0.0, pre_edge_latency_mean: 1.23, pre_edge_latency_p50: 0.89, pre_edge_latency_p95: 3.45, delivery_time_mean: 2.1, delivery_time_p50: 1.5, delivery_time_p95: 5.8 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "H-main", total: 98432, delivered: 93710, bounced: 2953, deferred: 1769, complained: 98, delivery_rate: 0.952, bounce_rate: 0.03, deferral_rate: 0.018, complaint_rate: 0.001, pre_edge_latency_mean: 1.45, pre_edge_latency_p50: 1.02, pre_edge_latency_p95: 4.12, delivery_time_mean: 2.8, delivery_time_p50: 1.9, delivery_time_p95: 7.2 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "M-main", total: 75000, delivered: 65250, bounced: 4500, deferred: 3750, complained: 150, delivery_rate: 0.87, bounce_rate: 0.06, deferral_rate: 0.05, complaint_rate: 0.002, pre_edge_latency_mean: 1.78, pre_edge_latency_p50: 1.25, pre_edge_latency_p95: 5.10, delivery_time_mean: 3.5, delivery_time_p50: 2.4, delivery_time_p95: 9.1 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "L-main", total: 42000, delivered: 29820, bounced: 6300, deferred: 4200, complained: 420, delivery_rate: 0.71, bounce_rate: 0.15, deferral_rate: 0.10, complaint_rate: 0.01, pre_edge_latency_mean: 2.10, pre_edge_latency_p50: 1.50, pre_edge_latency_p95: 6.20, delivery_time_mean: 4.8, delivery_time_p50: 3.2, delivery_time_p95: 12.5 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "VL-main", total: 18000, delivered: 9360, bounced: 4500, deferred: 2700, complained: 540, delivery_rate: 0.52, bounce_rate: 0.25, deferral_rate: 0.15, complaint_rate: 0.03, pre_edge_latency_mean: 2.85, pre_edge_latency_p50: 2.00, pre_edge_latency_p95: 8.50, delivery_time_mean: 6.2, delivery_time_p50: 4.5, delivery_time_p95: 18.0 },
    { time_window: "2026-02-11T00:00:00", dimension: "recipient_domain", dimension_value: "gmail.com", total: 287654, delivered: 275745, bounced: 8630, deferred: 3279, complained: 288, delivery_rate: 0.959, bounce_rate: 0.03, deferral_rate: 0.011, complaint_rate: 0.001, pre_edge_latency_mean: 1.1, pre_edge_latency_p50: 0.75, pre_edge_latency_p95: 3.2, delivery_time_mean: 3.5, delivery_time_p50: 2.1, delivery_time_p95: 9.8 },
    { time_window: "2026-02-11T00:00:00", dimension: "recipient_domain", dimension_value: "outlook.com", total: 124500, delivered: 112050, bounced: 6225, deferred: 6225, complained: 125, delivery_rate: 0.90, bounce_rate: 0.05, deferral_rate: 0.05, complaint_rate: 0.001, pre_edge_latency_mean: 1.8, pre_edge_latency_p50: 1.2, pre_edge_latency_p95: 5.5, delivery_time_mean: 4.2, delivery_time_p50: 2.8, delivery_time_p95: 12.0 },
    { time_window: "2026-02-11T00:00:00", dimension: "recipient_domain", dimension_value: "yahoo.com", total: 98000, delivered: 93100, bounced: 2940, deferred: 1960, complained: 98, delivery_rate: 0.95, bounce_rate: 0.03, deferral_rate: 0.02, complaint_rate: 0.001, pre_edge_latency_mean: 1.3, pre_edge_latency_p50: 0.90, pre_edge_latency_p95: 3.8, delivery_time_mean: 2.9, delivery_time_p50: 1.8, delivery_time_p95: 8.5 },
    { time_window: "2026-02-11T00:00:00", dimension: "outmtaid", dimension_value: "10.20.30.40", total: 45000, delivered: 31050, bounced: 13950, deferred: 450, complained: 0, delivery_rate: 0.69, bounce_rate: 0.31, deferral_rate: 0.01, complaint_rate: 0.0, pre_edge_latency_mean: 0.95, pre_edge_latency_p50: 0.70, pre_edge_latency_p95: 2.8, delivery_time_mean: 1.8, delivery_time_p50: 1.2, delivery_time_p95: 4.5 },
    { time_window: "2026-02-11T00:00:00", dimension: "outmtaid", dimension_value: "10.20.30.41", total: 52000, delivered: 50440, bounced: 1040, deferred: 520, complained: 52, delivery_rate: 0.97, bounce_rate: 0.02, deferral_rate: 0.01, complaint_rate: 0.001, pre_edge_latency_mean: 1.05, pre_edge_latency_p50: 0.78, pre_edge_latency_p95: 3.0, delivery_time_mean: 2.0, delivery_time_p50: 1.4, delivery_time_p95: 5.2 }
  ],
  [ML_RUN_2]: [
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "VH-main", total: 132000, delivered: 129360, bounced: 1320, deferred: 1320, complained: 0, delivery_rate: 0.98, bounce_rate: 0.01, deferral_rate: 0.01, complaint_rate: 0.0, pre_edge_latency_mean: 1.15, pre_edge_latency_p50: 0.82, pre_edge_latency_p95: 3.2, delivery_time_mean: 2.0, delivery_time_p50: 1.4, delivery_time_p95: 5.5 },
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "H-main", total: 89000, delivered: 85440, bounced: 1780, deferred: 1780, complained: 89, delivery_rate: 0.96, bounce_rate: 0.02, deferral_rate: 0.02, complaint_rate: 0.001, pre_edge_latency_mean: 1.35, pre_edge_latency_p50: 0.95, pre_edge_latency_p95: 3.9, delivery_time_mean: 2.6, delivery_time_p50: 1.8, delivery_time_p95: 6.8 },
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "M-main", total: 68000, delivered: 61200, bounced: 3400, deferred: 3400, complained: 136, delivery_rate: 0.90, bounce_rate: 0.05, deferral_rate: 0.05, complaint_rate: 0.002, pre_edge_latency_mean: 1.65, pre_edge_latency_p50: 1.15, pre_edge_latency_p95: 4.8, delivery_time_mean: 3.2, delivery_time_p50: 2.2, delivery_time_p95: 8.5 },
    { time_window: "2026-02-10T00:00:00", dimension: "recipient_domain", dimension_value: "gmail.com", total: 265000, delivered: 256445, bounced: 5300, deferred: 3180, complained: 265, delivery_rate: 0.968, bounce_rate: 0.02, deferral_rate: 0.012, complaint_rate: 0.001, pre_edge_latency_mean: 1.05, pre_edge_latency_p50: 0.72, pre_edge_latency_p95: 3.0, delivery_time_mean: 3.3, delivery_time_p50: 2.0, delivery_time_p95: 9.2 }
  ],
  [ML_RUN_3]: [
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "VH-main", total: 155000, delivered: 149575, bounced: 3875, deferred: 1550, complained: 0, delivery_rate: 0.965, bounce_rate: 0.025, deferral_rate: 0.01, complaint_rate: 0.0, pre_edge_latency_mean: 1.20, pre_edge_latency_p50: 0.85, pre_edge_latency_p95: 3.4, delivery_time_mean: 2.0, delivery_time_p50: 1.4, delivery_time_p95: 5.6 },
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "H-main", total: 102000, delivered: 97920, bounced: 2040, deferred: 2040, complained: 102, delivery_rate: 0.96, bounce_rate: 0.02, deferral_rate: 0.02, complaint_rate: 0.001, pre_edge_latency_mean: 1.40, pre_edge_latency_p50: 1.00, pre_edge_latency_p95: 4.0, delivery_time_mean: 2.7, delivery_time_p50: 1.85, delivery_time_p95: 7.0 },
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "M-main", total: 78000, delivered: 67080, bounced: 5460, deferred: 3900, complained: 156, delivery_rate: 0.86, bounce_rate: 0.07, deferral_rate: 0.05, complaint_rate: 0.002, pre_edge_latency_mean: 1.82, pre_edge_latency_p50: 1.28, pre_edge_latency_p95: 5.2, delivery_time_mean: 3.6, delivery_time_p50: 2.5, delivery_time_p95: 9.5 },
    { time_window: "2026-02-14T00:00:00", dimension: "recipient_domain", dimension_value: "gmail.com", total: 298000, delivered: 285780, bounced: 8940, deferred: 3278, complained: 298, delivery_rate: 0.959, bounce_rate: 0.03, deferral_rate: 0.011, complaint_rate: 0.001, pre_edge_latency_mean: 1.08, pre_edge_latency_p50: 0.73, pre_edge_latency_p95: 3.1, delivery_time_mean: 3.4, delivery_time_p50: 2.0, delivery_time_p95: 9.5 },
    { time_window: "2026-02-14T00:00:00", dimension: "recipient_domain", dimension_value: "outlook.com", total: 135000, delivered: 108000, bounced: 8100, deferred: 18900, complained: 135, delivery_rate: 0.80, bounce_rate: 0.06, deferral_rate: 0.14, complaint_rate: 0.001, pre_edge_latency_mean: 2.50, pre_edge_latency_p50: 1.80, pre_edge_latency_p95: 7.5, delivery_time_mean: 6.8, delivery_time_p50: 4.5, delivery_time_p95: 18.0 }
  ]
};

export const mockCompleteness: Record<string, any[]> = {
  [ML_RUN_1]: [
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "VH-main", total_records: 142857, field_name: "clicktrackingid", zero_count: 4286, zero_rate: 0.03 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "H-main", total_records: 98432, field_name: "clicktrackingid", zero_count: 1969, zero_rate: 0.02 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "DS-main", total_records: 31204, field_name: "clicktrackingid", zero_count: 3744, zero_rate: 0.12 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "NM-main", total_records: 18456, field_name: "clicktrackingid", zero_count: 1661, zero_rate: 0.09 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "NM-main", total_records: 18456, field_name: "xmrid_account_id", zero_count: 9228, zero_rate: 0.50 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "VL-main", total_records: 18000, field_name: "last_active_ts", zero_count: 10800, zero_rate: 0.60 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "L-main", total_records: 42000, field_name: "contact_added_ts", zero_count: 12600, zero_rate: 0.30 },
    { time_window: "2026-02-11T00:00:00", dimension: "listid", dimension_value: "M-main", total_records: 75000, field_name: "op_queue_time_parsed", zero_count: 3750, zero_rate: 0.05 }
  ],
  [ML_RUN_2]: [
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "VH-main", total_records: 132000, field_name: "clicktrackingid", zero_count: 2640, zero_rate: 0.02 },
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "H-main", total_records: 89000, field_name: "clicktrackingid", zero_count: 1780, zero_rate: 0.02 },
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "DS-main", total_records: 28000, field_name: "clicktrackingid", zero_count: 840, zero_rate: 0.03 },
    { time_window: "2026-02-10T00:00:00", dimension: "listid", dimension_value: "NM-main", total_records: 16000, field_name: "xmrid_account_id", zero_count: 8000, zero_rate: 0.50 }
  ],
  [ML_RUN_3]: [
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "VH-main", total_records: 155000, field_name: "clicktrackingid", zero_count: 4650, zero_rate: 0.03 },
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "DS-main", total_records: 35000, field_name: "clicktrackingid", zero_count: 4900, zero_rate: 0.14 },
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "NM-main", total_records: 20000, field_name: "clicktrackingid", zero_count: 2200, zero_rate: 0.11 },
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "NM-main", total_records: 20000, field_name: "xmrid_account_id", zero_count: 10400, zero_rate: 0.52 },
    { time_window: "2026-02-14T00:00:00", dimension: "listid", dimension_value: "VL-main", total_records: 19500, field_name: "last_active_ts", zero_count: 12480, zero_rate: 0.64 }
  ]
};

export const mockKnowledgeStats = [
  { tier: "hypothesis", collection: "knowledge_hypothesis", count: 8, weight: 0.3, description: "LLM-generated, untested" },
  { tier: "finding", collection: "knowledge_finding", count: 12, weight: 0.6, description: "ML-tested, evidence attached" },
  { tier: "truth", collection: "knowledge_truth", count: 0, weight: 0.85, description: "ML + LLM + human confirmed" },
  { tier: "grounded", collection: "knowledge_grounded", count: 1142, weight: 1.0, description: "Authoritative domain knowledge (read-only)" }
];

export const mockKnowledgeEntries = [
  { entry_id: "a1b2c3d4-e5f6-7890-abcd-ef1234567890", tier: "grounded", statement: "VH (Very Hot) segment contains recipients who clicked or opened within the last 30 days. This segment routes through the highest-reputation IP pools and is expected to maintain delivery rates above 95%.", topic: "engagement segments", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.92, weighted_score: 0.92, finding_status: null, source_run_ids: [] },
  { entry_id: "b2c3d4e5-f6a7-8901-bcde-f12345678901", tier: "finding", statement: "VH segment baseline bounce rate is 2.7% across 14 days of data from Feb 1-14, 2026. This is within the expected range for high-reputation IP pools sending to engaged recipients.", topic: "VH bounce baseline", dimension: "listid", dimension_value: "VH-main", scope: "community", account_id: null, confidence: 0.75, observation_count: 3, similarity: 0.85, weighted_score: 0.383, finding_status: "confirmed", source_run_ids: ["270e8dea-6350-4230-a095-f9b1986349d3"] },
  { entry_id: "c3d4e5f6-a7b8-9012-cdef-123456789012", tier: "hypothesis", statement: "Account 269124 DKIM non-compliance on shared IP pool may be contributing to pool-wide reputation degradation at gmail.com.", topic: "compliance cascade", dimension: "xmrid_account_id", dimension_value: "269124", scope: "account", account_id: "269124", confidence: 0.4, observation_count: 1, similarity: 0.78, weighted_score: 0.094, finding_status: null, source_run_ids: ["270e8dea-6350-4230-a095-f9b1986349d3"] },
  { entry_id: "d4e5f6a7-b8c9-0123-def0-234567890123", tier: "grounded", statement: "Gmail Postmaster Tools classifies sender reputation into four tiers: High, Medium, Low, Bad. Reputation is computed per IP and per domain, with different weights. Volume thresholds apply.", topic: "Gmail reputation system", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.75, weighted_score: 0.75, finding_status: null, source_run_ids: [] },
  { entry_id: "e5f6a7b8-c9d0-1234-ef01-345678901234", tier: "finding", statement: "M segment delivery rate shows consistent 14-day degradation trend across multiple runs, currently at 87% approaching the 85% threshold.", topic: "M segment degradation", dimension: "listid", dimension_value: "M-main", scope: "community", account_id: null, confidence: 0.8, observation_count: 4, similarity: 0.82, weighted_score: 0.394, finding_status: "confirmed", source_run_ids: ["270e8dea-6350-4230-a095-f9b1986349d3", "81f3c2d4-7a6b-4e5f-9c8d-0e1f2a3b4c5d"] },
  { entry_id: "f6a7b8c9-d0e1-2345-f012-456789012345", tier: "grounded", statement: "DKIM (DomainKeys Identified Mail) failure rate above 5% on shared IP pools triggers reputation penalties at major ISPs. The penalty threshold varies: Gmail ~2%, Microsoft ~5%, Yahoo ~10%.", topic: "DKIM compliance thresholds", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.70, weighted_score: 0.70, finding_status: null, source_run_ids: [] },
  { entry_id: "a7b8c9d0-e1f2-3456-0123-567890123456", tier: "hypothesis", statement: "The clicktrackingid completeness regression in DS/NM segments may originate from a specific automation workflow that stopped populating the field after a platform update.", topic: "clicktrackingid regression", dimension: "listid", dimension_value: "DS-main", scope: "community", account_id: null, confidence: 0.35, observation_count: 1, similarity: 0.68, weighted_score: 0.071, finding_status: null, source_run_ids: ["270e8dea-6350-4230-a095-f9b1986349d3"] },
  { entry_id: "b8c9d0e1-f2a3-4567-1234-678901234567", tier: "finding", statement: "Outlook.com deferral rates correlate with sending volume changes. A 40%+ day-over-day volume increase triggers throttling in 85% of observed cases.", topic: "Outlook throttling patterns", dimension: "recipient_domain", dimension_value: "outlook.com", scope: "community", account_id: null, confidence: 0.65, observation_count: 2, similarity: 0.72, weighted_score: 0.281, finding_status: "confirmed", source_run_ids: ["c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f"] },
  { entry_id: "c9d0e1f2-a3b4-5678-2345-789012345678", tier: "grounded", statement: "Engagement-based segmentation (VH/H/M/L/VL) determines IP pool routing. Higher engagement segments are routed through higher-reputation IPs to protect deliverability.", topic: "IP pool routing", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.65, weighted_score: 0.65, finding_status: null, source_run_ids: [] },
  { entry_id: "d0e1f2a3-b4c5-6789-3456-890123456789", tier: "hypothesis", statement: "VL segment delivery rate may be artificially depressed by stale DNS records causing hard bounces on defunct domains.", topic: "VL stale DNS", dimension: "listid", dimension_value: "VL-main", scope: "community", account_id: null, confidence: 0.25, observation_count: 1, similarity: 0.55, weighted_score: 0.041, finding_status: null, source_run_ids: [] },
  { entry_id: "e1f2a3b4-c5d6-7890-4567-901234567890", tier: "grounded", statement: "SPF (Sender Policy Framework) alignment is required for DMARC compliance. When SPF alignment fails, DMARC evaluation falls back to DKIM alignment only. Dual-aligned messages have the highest deliverability.", topic: "SPF alignment", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.60, weighted_score: 0.60, finding_status: null, source_run_ids: [] },
  { entry_id: "f2a3b4c5-d6e7-8901-5678-012345678901", tier: "grounded", statement: "Yahoo Mail applies sender throttling when complaint rates exceed 0.3% over a 7-day rolling window. Recovery requires complaint rate below 0.1% for at least 14 consecutive days.", topic: "Yahoo complaint thresholds", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.58, weighted_score: 0.58, finding_status: null, source_run_ids: [] },
  { entry_id: "a3b4c5d6-e7f8-9012-6789-123456789012", tier: "grounded", statement: "Bounce codes in the 5xx range indicate permanent delivery failures. 550 indicates mailbox not found, 551 indicates user not local, 552 indicates storage exceeded, 553 indicates invalid address syntax.", topic: "SMTP bounce codes", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.55, weighted_score: 0.55, finding_status: null, source_run_ids: [] },
  { entry_id: "b4c5d6e7-f8a9-0123-7890-234567890123", tier: "grounded", statement: "List hygiene best practices recommend removing hard-bounce addresses after 1 occurrence and soft-bounce addresses after 3-5 consecutive failures within a 30-day window.", topic: "list hygiene", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.53, weighted_score: 0.53, finding_status: null, source_run_ids: [] },
  { entry_id: "c5d6e7f8-a9b0-1234-8901-345678901234", tier: "grounded", statement: "Apple Mail Privacy Protection (MPP) prefetches email images, inflating open rate metrics. MPP-affected opens should be excluded from engagement scoring for accurate segmentation.", topic: "Apple MPP impact", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.51, weighted_score: 0.51, finding_status: null, source_run_ids: [] },
  { entry_id: "d6e7f8a9-b0c1-2345-9012-456789012345", tier: "grounded", statement: "Warm-up schedules for new IPs should start at 50-100 messages per day and double volume every 2-3 days until reaching target volume. Exceeding warm-up velocity triggers throttling at most ISPs.", topic: "IP warm-up", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.49, weighted_score: 0.49, finding_status: null, source_run_ids: [] },
  { entry_id: "e7f8a9b0-c1d2-3456-0123-567890123456", tier: "grounded", statement: "Microsoft SmartScreen filtering evaluates sender reputation, URL reputation, and content signals. New senders without established reputation default to junk folder placement for the first 30-60 days.", topic: "SmartScreen filtering", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.47, weighted_score: 0.47, finding_status: null, source_run_ids: [] },
  { entry_id: "f8a9b0c1-d2e3-4567-1234-678901234567", tier: "grounded", statement: "Feedback loops (FBLs) from ISPs report user complaint events. Gmail uses a header-based FBL requiring List-Unsubscribe-Post support. Yahoo, Microsoft, and AOL use ARF-format FBLs.", topic: "feedback loop mechanisms", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.45, weighted_score: 0.45, finding_status: null, source_run_ids: [] },
  { entry_id: "a9b0c1d2-e3f4-5678-2345-789012345678", tier: "grounded", statement: "ARC (Authenticated Received Chain) preserves authentication results across forwarding hops. Google Workspace and Microsoft 365 evaluate ARC headers when direct DKIM/SPF fail due to forwarding.", topic: "ARC authentication", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.43, weighted_score: 0.43, finding_status: null, source_run_ids: [] },
  { entry_id: "b0c1d2e3-f4a5-6789-3456-890123456789", tier: "grounded", statement: "MX record lookup failures result in temporary delivery failures (4xx). DNS TTL values below 300 seconds can cause excessive lookups and intermittent delivery issues during DNS propagation.", topic: "MX DNS resolution", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.41, weighted_score: 0.41, finding_status: null, source_run_ids: [] },
  { entry_id: "c1d2e3f4-a5b6-7890-4567-901234567890", tier: "grounded", statement: "TLS encryption is enforced by Gmail for all inbound connections since 2020. Senders that cannot negotiate TLS 1.2+ will receive 530 errors and messages will be rejected.", topic: "TLS requirements", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.39, weighted_score: 0.39, finding_status: null, source_run_ids: [] },
  { entry_id: "d2e3f4a5-b6c7-8901-5678-012345678901", tier: "grounded", statement: "BIMI (Brand Indicators for Message Identification) requires DMARC enforcement at p=quarantine or p=reject. VMC (Verified Mark Certificate) is required by Gmail but optional for Apple Mail.", topic: "BIMI requirements", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.37, weighted_score: 0.37, finding_status: null, source_run_ids: [] },
  { entry_id: "e3f4a5b6-c7d8-9012-6789-123456789012", tier: "grounded", statement: "Shared IP pools aggregate reputation across all senders. A single sender with >5% complaint rate can degrade pool reputation, affecting all senders. Isolation thresholds vary by ISP.", topic: "shared IP reputation", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.35, weighted_score: 0.35, finding_status: null, source_run_ids: [] },
  { entry_id: "f4a5b6c7-d8e9-0123-7890-234567890123", tier: "grounded", statement: "Gmail's one-click unsubscribe requirement (effective Feb 2024) mandates List-Unsubscribe and List-Unsubscribe-Post headers for bulk senders exceeding 5,000 messages/day to Gmail.", topic: "Gmail unsubscribe requirements", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.33, weighted_score: 0.33, finding_status: null, source_run_ids: [] },
  { entry_id: "a5b6c7d8-e9f0-1234-8901-345678901234", tier: "grounded", statement: "Sunset policies define the maximum age of subscriber inactivity before suppression. Industry standard is 6-12 months of no engagement. Aggressive sunset (90 days) improves deliverability but reduces reach.", topic: "sunset policy", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.31, weighted_score: 0.31, finding_status: null, source_run_ids: [] },
  { entry_id: "b6c7d8e9-f0a1-2345-9012-456789012345", tier: "grounded", statement: "Pre-edge latency measures the time between message submission and first delivery attempt. Values above 5 seconds indicate queue congestion or rate-limiting by the MTA.", topic: "pre-edge latency", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.29, weighted_score: 0.29, finding_status: null, source_run_ids: [] },
  { entry_id: "c7d8e9f0-a1b2-3456-0123-567890123456", tier: "grounded", statement: "Recipient domain categorization groups ISPs by volume and filtering behavior. Tier 1 (Gmail, Outlook, Yahoo) represents 70%+ of consumer email volume and has the most sophisticated filtering.", topic: "ISP tier classification", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.27, weighted_score: 0.27, finding_status: null, source_run_ids: [] },
  { entry_id: "d8e9f0a1-b2c3-4567-1234-678901234567", tier: "grounded", statement: "Content filtering evaluates subject lines, body text, HTML-to-text ratio, image-to-text ratio, and URL reputation. Short URLs from public shorteners are heavily penalized by spam filters.", topic: "content filtering signals", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.25, weighted_score: 0.25, finding_status: null, source_run_ids: [] },
  { entry_id: "e9f0a1b2-c3d4-5678-2345-789012345678", tier: "grounded", statement: "Delivery time optimization considers recipient timezone and historical engagement patterns. Messages delivered between 8-10 AM local time show 15-25% higher open rates across most verticals.", topic: "send time optimization", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.23, weighted_score: 0.23, finding_status: null, source_run_ids: [] },
  { entry_id: "f0a1b2c3-d4e5-6789-3456-890123456789", tier: "grounded", statement: "Dedicated IPs should maintain minimum sending volume of 10,000 messages per week to establish and maintain reputation. IPs with intermittent sending patterns lose reputation faster than consistent senders.", topic: "dedicated IP volume", dimension: null, dimension_value: null, scope: "community", account_id: null, confidence: 1.0, observation_count: 1, similarity: 0.21, weighted_score: 0.21, finding_status: null, source_run_ids: [] }
];

export const mockReports: Record<string, any> = {
  [INV_RUN_1]: {
    run_id: INV_RUN_1,
    markdown: "# Investigation Report \u2014 270e8dea-6350-4230-a095-f9b1986349d3\n\n**Status:** SUCCESS\n**Label:** B-with-knowledge\n**Duration:** 9m 22s\n**Iterations:** 2\n\n---\n\n## Findings\n\n### 1. VH segment bounce spike on gmail.com \u2014 CONFIRMED\n\nVH segment bounce rate to gmail.com spiked to 8.2%, 3x the historical baseline of 2.7%. The spike is concentrated on outmtaid 10.20.30.40 which shows 94% of the bounces.\n\n**Evidence:**\n- Aggregation: VH-main bounce_rate=0.082 vs 14-day baseline 0.027\n- Anomaly: bounce_spike severity=high z_score=4.1 for VH-main\n- Aggregation by outmtaid: 10.20.30.40 shows bounce_rate=0.31\n\n**Metrics:** bounce_rate=0.082, baseline_mean=0.027, z_score=4.1\n\n### 2. M segment delivery rate degradation \u2014 CONFIRMED\n\nM segment delivery rate has degraded from 92% to 87% over the past 14 days, with a statistically significant downward trend (R\u00b2=0.87).\n\n**Evidence:**\n- Trend: M-main delivery_rate slope=-0.003 R\u00b2=0.87 over 14 points\n- Aggregation: M-main current delivery_rate=0.87 vs segment threshold 0.85\n\n### 3. Account 269124 DKIM compliance failure \u2014 INCONCLUSIVE\n\nAccount 269124 has 100% DKIM failure on shared IP pool, but impact is limited \u2014 account represents only 0.3% of pool volume.\n\n### 4. Data completeness regression in clicktrackingid \u2014 CONFIRMED\n\nclicktrackingid zero-value rate increased from 3% to 12% between Feb 11 and Feb 14, concentrated in DS and NM segments.\n\n---\n\n## Hypotheses\n\n1. **Account 269124 compliance cascade risk**: Non-compliant DKIM on account 269124 may be degrading shared pool reputation at gmail.com.\n2. **DS/NM clicktrackingid regression source**: The regression may originate from a specific automation workflow.\n\n---\n\n## Synthesis\n\nThis investigation examined 847,293 email delivery events. Four findings were confirmed across reputation, compliance, and data quality dimensions. The VH bounce spike warrants immediate attention."
  }
};
