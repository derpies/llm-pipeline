import type {
  Domain,
  Meta,
  RunsResponse,
  InvestigationDetail,
  MLRunSummary,
  MLOverviewResponse,
  AggregationsResponse,
  Anomaly,
  Trend,
  CompletenessResponse,
  KnowledgeSearchResponse,
  KnowledgeStat,
  InvestigationReport,
} from "@shared/schema";
import { useQuery } from "@tanstack/react-query";

async function fetchJson<T>(url: string): Promise<T> {
  const res = await fetch(url);
  if (!res.ok) {
    const text = (await res.text()) || res.statusText;
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json();
}

export function useDomains() {
  return useQuery<Domain[]>({
    queryKey: ["/api/domains"],
    queryFn: () => fetchJson("/api/domains"),
    staleTime: Infinity,
  });
}

export function useMeta() {
  return useQuery<Meta>({
    queryKey: ["/api/meta"],
    queryFn: () => fetchJson("/api/meta"),
    staleTime: Infinity,
  });
}

export function useRuns(params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v !== undefined)
  );
  const url = `/api/runs?${searchParams.toString()}`;
  return useQuery<RunsResponse>({
    queryKey: ["/api/runs", params],
    queryFn: () => fetchJson(url),
  });
}

export function useInvestigation(runId: string) {
  return useQuery<InvestigationDetail>({
    queryKey: ["/api/investigations", runId],
    queryFn: () => fetchJson(`/api/investigations/${runId}`),
    enabled: !!runId,
  });
}

export function useInvestigationReport(runId: string, format: string = "markdown") {
  return useQuery<InvestigationReport>({
    queryKey: ["/api/investigations", runId, "report", format],
    queryFn: () => fetchJson(`/api/investigations/${runId}/report?format=${format}`),
    enabled: !!runId,
  });
}

export function useMLOverview() {
  return useQuery<MLOverviewResponse>({
    queryKey: ["/api/ml"],
    queryFn: () => fetchJson("/api/ml"),
  });
}

export function useMLSummary(runId: string) {
  return useQuery<MLRunSummary>({
    queryKey: ["/api/ml", runId],
    queryFn: () => fetchJson(`/api/ml/${runId}`),
    enabled: !!runId,
  });
}

export function useAggregations(runId: string, params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v !== undefined)
  );
  const url = `/api/ml/${runId}/aggregations?${searchParams.toString()}`;
  return useQuery<AggregationsResponse>({
    queryKey: ["/api/ml", runId, "aggregations", params],
    queryFn: () => fetchJson(url),
    enabled: !!runId,
  });
}

export function useAnomalies(runId: string) {
  return useQuery<Anomaly[]>({
    queryKey: ["/api/ml", runId, "anomalies"],
    queryFn: () => fetchJson(`/api/ml/${runId}/anomalies`),
    enabled: !!runId,
  });
}

export function useTrends(runId: string) {
  return useQuery<Trend[]>({
    queryKey: ["/api/ml", runId, "trends"],
    queryFn: () => fetchJson(`/api/ml/${runId}/trends`),
    enabled: !!runId,
  });
}

export function useCompleteness(runId: string, params: Record<string, string> = {}) {
  const searchParams = new URLSearchParams(
    Object.entries(params).filter(([, v]) => v !== "" && v !== undefined)
  );
  const url = `/api/ml/${runId}/completeness?${searchParams.toString()}`;
  return useQuery<CompletenessResponse>({
    queryKey: ["/api/ml", runId, "completeness", params],
    queryFn: () => fetchJson(url),
    enabled: !!runId,
  });
}

export function useKnowledgeStats() {
  return useQuery<KnowledgeStat[]>({
    queryKey: ["/api/knowledge/stats"],
    queryFn: () => fetchJson("/api/knowledge/stats"),
  });
}

export function useKnowledgeSearch(q: string, tier?: string, offset: number = 0, limit: number = 20) {
  const params = new URLSearchParams();
  if (q) params.set("q", q);
  if (tier) params.set("tier", tier);
  params.set("offset", String(offset));
  params.set("limit", String(limit));
  return useQuery<KnowledgeSearchResponse>({
    queryKey: ["/api/knowledge/search", q, tier, offset, limit],
    queryFn: () => fetchJson(`/api/knowledge/search?${params.toString()}`),
  });
}
