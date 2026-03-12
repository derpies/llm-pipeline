import { z } from "zod";

export interface DomainRole {
  name: string;
  prompt_supplement: string;
}

export interface DomainMLDataTypes {
  dimensions: string[];
  metrics: string[];
  delivery_statuses: string[];
  smtp_categories: string[];
  anomaly_types: string[];
  trend_directions: string[];
  completeness_fields: string[];
  segment_thresholds: Record<string, number>;
}

export interface Domain {
  name: string;
  description: string;
  roles: DomainRole[];
  ml_data_types: DomainMLDataTypes;
}

export interface KnowledgeTier {
  name: string;
  weight: number;
  description: string;
  color: string;
}

export interface Meta {
  finding_statuses: string[];
  review_assessments: string[];
  review_actions: string[];
  knowledge_tiers: KnowledgeTier[];
  run_statuses: string[];
  commands: string[];
}

export interface RunBase {
  run_id: string;
  domain: string;
  command: string;
  created_at: string;
  source_files: string[];
  started_at: string;
  completed_at: string;
}

export interface AnalyzeEmailRun extends RunBase {
  command: "analyze_email";
  files_processed: number;
  events_parsed: number;
  anomaly_count: number;
  trend_count: number;
}

export interface InvestigateRun extends RunBase {
  command: "investigate" | "investigate_http";
  status: string;
  is_dry_run: boolean;
  label: string;
  ml_run_id: string;
  finding_count: number;
  hypothesis_count: number;
  iteration_count: number;
}

export type PipelineRun = AnalyzeEmailRun | InvestigateRun;

export function isInvestigationCommand(command: string): boolean {
  return command === "investigate" || command === "investigate_http";
}

export interface RunsResponse {
  total: number;
  runs: PipelineRun[];
}

export interface Finding {
  topic_title: string;
  statement: string;
  status: string;
  evidence: string[];
  metrics_cited: Record<string, number>;
  is_fallback: boolean;
  quality_warnings: string[];
}

export interface Hypothesis {
  topic_title: string;
  statement: string;
  reasoning: string;
}

export interface InvestigationDetail {
  run_id: string;
  domain: string;
  started_at: string;
  completed_at: string;
  duration_seconds: number;
  status: string;
  is_dry_run: boolean;
  label: string;
  ml_run_id: string;
  iteration_count: number;
  finding_count: number;
  hypothesis_count: number;
  checkpoint_digest: string;
  quality_warnings: string[];
  source_files: string[];
  findings: Finding[];
  hypotheses: Hypothesis[];
  synthesis_narrative: string | null;
}

export interface MLRunSummary {
  run_id: string;
  domain: string;
  started_at: string;
  completed_at: string;
  files_processed: number;
  events_parsed: number;
  counts: {
    aggregations: number;
    anomalies: number;
    trends: number;
    completeness: number;
  };
}

export interface Aggregation {
  time_window: string;
  dimension: string;
  dimension_value: string;
  total: number;
  delivered: number;
  bounced: number;
  deferred: number;
  complained: number;
  delivery_rate: number;
  bounce_rate: number;
  deferral_rate: number;
  complaint_rate: number;
  pre_edge_latency_mean: number;
  pre_edge_latency_p50: number;
  pre_edge_latency_p95: number;
  delivery_time_mean: number;
  delivery_time_p50: number;
  delivery_time_p95: number;
}

export interface AggregationsResponse {
  total: number;
  aggregations: Aggregation[];
}

export interface Anomaly {
  anomaly_type: string;
  dimension: string;
  dimension_value: string;
  metric: string;
  current_value: number;
  baseline_mean: number;
  z_score: number;
  severity: string;
}

export interface Trend {
  direction: string;
  dimension: string;
  dimension_value: string;
  metric: string;
  slope: number;
  r_squared: number;
  num_points: number;
  start_value: number;
  end_value: number;
}

export interface CompletenessEntry {
  time_window: string;
  dimension: string;
  dimension_value: string;
  total_records: number;
  field_name: string;
  zero_count: number;
  zero_rate: number;
}

export interface CompletenessResponse {
  total: number;
  completeness: CompletenessEntry[];
}

export interface KnowledgeEntry {
  entry_id: string;
  tier: string;
  statement: string;
  topic: string;
  dimension: string | null;
  dimension_value: string | null;
  scope: string;
  account_id: string | null;
  confidence: number;
  observation_count: number;
  similarity: number;
  weighted_score: number;
  finding_status: string | null;
  source_run_ids: string[];
}

export interface KnowledgeSearchResponse {
  total: number;
  results: KnowledgeEntry[];
}

export interface KnowledgeStat {
  tier: string;
  collection: string;
  count: number;
  weight: number;
  description: string;
}

export interface InvestigationReport {
  run_id: string;
  markdown?: string;
  report?: Record<string, unknown>;
}

export interface AnomalyWithRun extends Anomaly {
  run_id: string;
  started_at: string;
}

export interface TrendWithRun extends Trend {
  run_id: string;
  started_at: string;
}

export interface MLOverviewResponse {
  summaries: MLRunSummary[];
  anomalies: AnomalyWithRun[];
  trends: TrendWithRun[];
}
