import { useState, useMemo } from "react";
import { useLocation } from "wouter";
import { useMLOverview } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { CopyableId } from "@/components/copyable-id";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import {
  BarChart3,
  Activity,
  AlertTriangle,
  TrendingDown,
  TrendingUp,
  Minus,
  ArrowRight,
  Zap,
  Database,
  FileBarChart,
  Search,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import type { AnomalyWithRun, TrendWithRun, MLRunSummary } from "@shared/schema";

interface Filters {
  domain: string;
  severity: string;
  anomalyType: string;
  dimension: string;
  trendDirection: string;
  search: string;
}

const emptyFilters: Filters = {
  domain: "",
  severity: "",
  anomalyType: "",
  dimension: "",
  trendDirection: "",
  search: "",
};

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
    " " +
    d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

function formatNumber(n: number): string {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return String(n);
}

function fieldLabel(field: string): string {
  return field
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function severityOrder(s: string): number {
  if (s === "high") return 0;
  if (s === "medium") return 1;
  return 2;
}

function directionIcon(dir: string) {
  if (dir === "degrading") return <TrendingDown className="w-4 h-4 text-red-500" />;
  if (dir === "improving") return <TrendingUp className="w-4 h-4 text-emerald-500" />;
  return <Minus className="w-4 h-4 text-muted-foreground" />;
}

function hasActiveFilters(filters: Filters): boolean {
  return Object.values(filters).some((v) => v !== "");
}

function SummaryCards({ summaries, anomalies, trends }: { summaries: MLRunSummary[]; anomalies: AnomalyWithRun[]; trends: TrendWithRun[] }) {
  const totalEvents = summaries.reduce((s, r) => s + r.events_parsed, 0);
  const highSeverity = anomalies.filter((a) => a.severity === "high").length;
  const degradingTrends = trends.filter((t) => t.direction === "degrading").length;

  const cards = [
    { label: "ML Runs", value: summaries.length, icon: FileBarChart, color: "text-blue-500" },
    { label: "Events Processed", value: formatNumber(totalEvents), icon: Database, color: "text-teal-500" },
    { label: "Total Anomalies", value: anomalies.length, sub: highSeverity > 0 ? `${highSeverity} high severity` : undefined, icon: AlertTriangle, color: "text-amber-500" },
    { label: "Active Trends", value: trends.length, sub: degradingTrends > 0 ? `${degradingTrends} degrading` : undefined, icon: Activity, color: "text-purple-500" },
  ];

  return (
    <div className="grid grid-cols-4 gap-4" data-testid="ml-summary-cards">
      {cards.map((c) => (
        <Card key={c.label} className="border-border/50">
          <CardContent className="pt-5 pb-4 px-5">
            <div className="flex items-start justify-between">
              <div>
                <p className="text-sm text-muted-foreground font-medium">{c.label}</p>
                <p className="text-2xl font-semibold tracking-tight mt-1" data-testid={`stat-${c.label.toLowerCase().replace(/\s+/g, "-")}`}>{c.value}</p>
                {c.sub && <p className="text-xs text-muted-foreground mt-1">{c.sub}</p>}
              </div>
              <div className={`p-2 rounded-lg bg-muted/50 ${c.color}`}>
                <c.icon className="w-5 h-5" />
              </div>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function RunsTable({ summaries, anomalyCounts, trendCounts }: { summaries: MLRunSummary[]; anomalyCounts: Record<string, number>; trendCounts: Record<string, { degrading: number; improving: number; stable: number }> }) {
  const [, navigate] = useLocation();

  if (summaries.length === 0) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <BarChart3 className="w-4 h-4 text-primary" />
            All ML Runs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No ML runs match the current filters.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <BarChart3 className="w-4 h-4 text-primary" />
          All ML Runs
          <span className="text-xs font-normal text-muted-foreground ml-1">({summaries.length})</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-6">Run ID</TableHead>
              <TableHead>Domain</TableHead>
              <TableHead>Started</TableHead>
              <TableHead>Duration</TableHead>
              <TableHead className="text-right">Events</TableHead>
              <TableHead className="text-right">Aggregations</TableHead>
              <TableHead className="text-right">Anomalies</TableHead>
              <TableHead>Trends</TableHead>
              <TableHead className="w-10 pr-6"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {summaries.map((run) => {
              const tc = trendCounts[run.run_id] || { degrading: 0, improving: 0, stable: 0 };
              return (
                <TableRow
                  key={run.run_id}
                  className="cursor-pointer"
                  onClick={() => navigate(`/ml/${run.run_id}`)}
                  data-testid={`row-ml-${run.run_id.slice(0, 8)}`}
                >
                  <TableCell className="pl-6">
                    <CopyableId value={run.run_id} />
                  </TableCell>
                  <TableCell>
                    <StatusBadge status={run.domain || "unknown"} />
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                    {formatDate(run.started_at)}
                  </TableCell>
                  <TableCell className="text-sm font-mono text-muted-foreground">
                    {formatDuration(run.started_at, run.completed_at)}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {run.events_parsed.toLocaleString()}
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    {run.counts.aggregations}
                  </TableCell>
                  <TableCell className="text-right">
                    <span className="font-mono text-sm">{anomalyCounts[run.run_id] || 0}</span>
                  </TableCell>
                  <TableCell>
                    <div className="flex items-center gap-2">
                      {tc.degrading > 0 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center gap-0.5 text-xs text-red-600 dark:text-red-400">
                              <TrendingDown className="w-3 h-3" />{tc.degrading}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>{tc.degrading} degrading trend{tc.degrading > 1 ? "s" : ""}</TooltipContent>
                        </Tooltip>
                      )}
                      {tc.improving > 0 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center gap-0.5 text-xs text-emerald-600 dark:text-emerald-400">
                              <TrendingUp className="w-3 h-3" />{tc.improving}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>{tc.improving} improving trend{tc.improving > 1 ? "s" : ""}</TooltipContent>
                        </Tooltip>
                      )}
                      {tc.stable > 0 && (
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="inline-flex items-center gap-0.5 text-xs text-muted-foreground">
                              <Minus className="w-3 h-3" />{tc.stable}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>{tc.stable} stable trend{tc.stable > 1 ? "s" : ""}</TooltipContent>
                        </Tooltip>
                      )}
                    </div>
                  </TableCell>
                  <TableCell className="pr-6">
                    <ArrowRight className="w-4 h-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function TopAnomalies({ anomalies, limit = 10 }: { anomalies: AnomalyWithRun[]; limit?: number }) {
  const sorted = [...anomalies]
    .sort((a, b) => {
      const sev = severityOrder(a.severity) - severityOrder(b.severity);
      if (sev !== 0) return sev;
      return Math.abs(b.z_score) - Math.abs(a.z_score);
    })
    .slice(0, limit);

  const [, navigate] = useLocation();

  if (sorted.length === 0) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-500" />
            Top Anomalies Across Runs
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No anomalies match the current filters.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-500" />
          Top Anomalies Across Runs
          <span className="text-xs font-normal text-muted-foreground ml-1">({anomalies.length} total, showing top {sorted.length})</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-6">Severity</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Dimension</TableHead>
              <TableHead>Segment</TableHead>
              <TableHead>Metric</TableHead>
              <TableHead className="text-right">Current</TableHead>
              <TableHead className="text-right">Baseline</TableHead>
              <TableHead className="text-right">Z-Score</TableHead>
              <TableHead>Run</TableHead>
              <TableHead className="w-10 pr-6"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((a, i) => {
              const isRate = a.metric.includes("rate");
              const fmt = (v: number) => isRate ? (v * 100).toFixed(2) + "%" : v.toFixed(2);
              return (
                <TableRow
                  key={`${a.run_id}-${i}`}
                  className="cursor-pointer"
                  onClick={() => navigate(`/ml/${a.run_id}`)}
                  data-testid={`row-anomaly-${i}`}
                >
                  <TableCell className="pl-6">
                    <StatusBadge status={a.severity} />
                  </TableCell>
                  <TableCell className="text-sm">
                    <span className="flex items-center gap-1.5">
                      <Zap className="w-3.5 h-3.5 text-amber-500" />
                      {fieldLabel(a.anomaly_type)}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{a.dimension}</TableCell>
                  <TableCell className="text-sm font-mono">{a.dimension_value}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{fieldLabel(a.metric)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{fmt(a.current_value)}</TableCell>
                  <TableCell className="text-right font-mono text-sm text-muted-foreground">{fmt(a.baseline_mean)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    <span className={a.z_score > 0 ? "text-red-600 dark:text-red-400" : "text-amber-600 dark:text-amber-400"}>
                      {a.z_score > 0 ? "+" : ""}{a.z_score.toFixed(1)}
                    </span>
                  </TableCell>
                  <TableCell>
                    <CopyableId value={a.run_id} />
                  </TableCell>
                  <TableCell className="pr-6">
                    <ArrowRight className="w-4 h-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function TrendsSummary({ trends }: { trends: TrendWithRun[] }) {
  const sorted = [...trends].sort((a, b) => {
    if (a.direction === "degrading" && b.direction !== "degrading") return -1;
    if (a.direction !== "degrading" && b.direction === "degrading") return 1;
    if (a.direction === "improving" && b.direction === "stable") return -1;
    if (a.direction === "stable" && b.direction === "improving") return 1;
    return Math.abs(b.slope) - Math.abs(a.slope);
  });

  const [, navigate] = useLocation();

  if (sorted.length === 0) {
    return (
      <Card className="border-border/50">
        <CardHeader className="pb-3">
          <CardTitle className="text-base font-semibold flex items-center gap-2">
            <Activity className="w-4 h-4 text-purple-500" />
            Trends
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">No trends match the current filters.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="border-border/50">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <Activity className="w-4 h-4 text-purple-500" />
          Trends
          <span className="text-xs font-normal text-muted-foreground ml-1">({sorted.length})</span>
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-6">Direction</TableHead>
              <TableHead>Dimension</TableHead>
              <TableHead>Segment</TableHead>
              <TableHead>Metric</TableHead>
              <TableHead className="text-right">Start</TableHead>
              <TableHead className="text-right">End</TableHead>
              <TableHead className="text-right">R²</TableHead>
              <TableHead>Run</TableHead>
              <TableHead className="w-10 pr-6"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {sorted.map((t, i) => {
              const isRate = t.metric.includes("rate");
              const fmt = (v: number) => isRate ? (v * 100).toFixed(1) + "%" : v.toFixed(3);
              return (
                <TableRow
                  key={`${t.run_id}-${i}`}
                  className="cursor-pointer"
                  onClick={() => navigate(`/ml/${t.run_id}`)}
                  data-testid={`row-trend-${i}`}
                >
                  <TableCell className="pl-6">
                    <span className="inline-flex items-center gap-1.5">
                      {directionIcon(t.direction)}
                      <StatusBadge status={t.direction} />
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{t.dimension}</TableCell>
                  <TableCell className="text-sm font-mono">{t.dimension_value}</TableCell>
                  <TableCell className="text-sm text-muted-foreground">{fieldLabel(t.metric)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">{fmt(t.start_value)}</TableCell>
                  <TableCell className="text-right font-mono text-sm">
                    <span className={t.direction === "degrading" ? "text-red-600 dark:text-red-400" : t.direction === "improving" ? "text-emerald-600 dark:text-emerald-400" : ""}>
                      {fmt(t.end_value)}
                    </span>
                  </TableCell>
                  <TableCell className="text-right font-mono text-sm text-muted-foreground">{t.r_squared.toFixed(2)}</TableCell>
                  <TableCell>
                    <CopyableId value={t.run_id} />
                  </TableCell>
                  <TableCell className="pr-6">
                    <ArrowRight className="w-4 h-4 text-muted-foreground" />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function LoadingSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-4 gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Card key={i} className="border-border/50">
            <CardContent className="pt-5 pb-4 px-5">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
      <Card className="border-border/50">
        <CardHeader className="pb-3"><Skeleton className="h-5 w-32" /></CardHeader>
        <CardContent><Skeleton className="h-40 w-full" /></CardContent>
      </Card>
    </div>
  );
}

export default function MLOverview() {
  const { data, isLoading, error } = useMLOverview();
  const [filters, setFilters] = useState<Filters>({ ...emptyFilters });

  const updateFilter = (key: keyof Filters, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value === "all" ? "" : value }));
  };

  const clearFilters = () => setFilters({ ...emptyFilters });

  const filterOptions = useMemo(() => {
    if (!data) return { domains: [], severities: [], anomalyTypes: [], dimensions: [], trendDirections: [] };
    const domainSet = new Set(data.summaries.map((s) => s.domain).filter(Boolean));
    const severities = [...new Set(data.anomalies.map((a) => a.severity))];
    const anomalyTypes = [...new Set(data.anomalies.map((a) => a.anomaly_type))];
    const dimSet = new Set<string>();
    for (const a of data.anomalies) dimSet.add(a.dimension);
    for (const t of data.trends) dimSet.add(t.dimension);
    const dimensions = [...dimSet].sort();
    const trendDirections = [...new Set(data.trends.map((t) => t.direction))];
    return { domains: [...domainSet].sort(), severities, anomalyTypes, dimensions, trendDirections };
  }, [data]);

  const filtered = useMemo(() => {
    if (!data) return { summaries: [], anomalies: [], trends: [] };

    let { anomalies, trends } = data;
    let summaries = data.summaries;
    const searchLower = filters.search.toLowerCase();

    if (filters.domain) {
      const domainRunIds = new Set(summaries.filter((s) => s.domain === filters.domain).map((s) => s.run_id));
      summaries = summaries.filter((s) => domainRunIds.has(s.run_id));
      anomalies = anomalies.filter((a) => domainRunIds.has(a.run_id));
      trends = trends.filter((t) => domainRunIds.has(t.run_id));
    }

    if (filters.severity) {
      anomalies = anomalies.filter((a) => a.severity === filters.severity);
    }
    if (filters.anomalyType) {
      anomalies = anomalies.filter((a) => a.anomaly_type === filters.anomalyType);
    }
    if (filters.dimension) {
      anomalies = anomalies.filter((a) => a.dimension === filters.dimension);
      trends = trends.filter((t) => t.dimension === filters.dimension);
    }
    if (filters.trendDirection) {
      trends = trends.filter((t) => t.direction === filters.trendDirection);
    }
    if (searchLower) {
      anomalies = anomalies.filter(
        (a) =>
          a.dimension_value.toLowerCase().includes(searchLower) ||
          a.dimension.toLowerCase().includes(searchLower) ||
          a.anomaly_type.toLowerCase().includes(searchLower) ||
          a.metric.toLowerCase().includes(searchLower)
      );
      trends = trends.filter(
        (t) =>
          t.dimension_value.toLowerCase().includes(searchLower) ||
          t.dimension.toLowerCase().includes(searchLower) ||
          t.metric.toLowerCase().includes(searchLower)
      );
    }

    const hasAnomalyFilters = filters.severity || filters.anomalyType;
    const hasTrendFilters = filters.trendDirection;
    const hasSharedFilters = filters.dimension || filters.search;

    if (hasAnomalyFilters || hasTrendFilters || hasSharedFilters) {
      const anomalyRunIds = new Set(anomalies.map((a) => a.run_id));
      const trendRunIds = new Set(trends.map((t) => t.run_id));

      let runIds: Set<string>;
      if (hasAnomalyFilters && hasTrendFilters) {
        runIds = new Set([...anomalyRunIds].filter((id) => trendRunIds.has(id)));
      } else if (hasAnomalyFilters && !hasTrendFilters && !hasSharedFilters) {
        runIds = anomalyRunIds;
      } else if (hasTrendFilters && !hasAnomalyFilters && !hasSharedFilters) {
        runIds = trendRunIds;
      } else {
        runIds = new Set([...anomalyRunIds, ...trendRunIds]);
      }

      summaries = summaries.filter((s) => runIds.has(s.run_id));
      anomalies = anomalies.filter((a) => runIds.has(a.run_id));
      trends = trends.filter((t) => runIds.has(t.run_id));
    }

    return { summaries, anomalies, trends };
  }, [data, filters]);

  if (isLoading) return <LoadingSkeleton />;

  if (error || !data) {
    return (
      <div className="flex items-center justify-center py-20" data-testid="ml-overview-error">
        <p className="text-muted-foreground">Failed to load ML overview data.</p>
      </div>
    );
  }

  const { summaries, anomalies, trends } = filtered;

  const anomalyCounts: Record<string, number> = {};
  for (const a of anomalies) {
    anomalyCounts[a.run_id] = (anomalyCounts[a.run_id] || 0) + 1;
  }

  const trendCounts: Record<string, { degrading: number; improving: number; stable: number }> = {};
  for (const t of trends) {
    if (!trendCounts[t.run_id]) trendCounts[t.run_id] = { degrading: 0, improving: 0, stable: 0 };
    trendCounts[t.run_id][t.direction as "degrading" | "improving" | "stable"]++;
  }

  const active = hasActiveFilters(filters);

  return (
    <div className="space-y-6" data-testid="ml-overview-page">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight" data-testid="heading-ml-overview">ML Analysis Overview</h1>
        <p className="text-sm text-muted-foreground mt-1">Cross-run summary of ML analysis results, anomalies, and trends</p>
      </div>

      <Card className="border-border/50" data-testid="ml-filters">
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search segments, dimensions, metrics..."
                value={filters.search}
                onChange={(e) => updateFilter("search", e.target.value)}
                className="pl-9 h-9"
                data-testid="input-ml-search"
              />
            </div>
            <Select value={filters.domain || "all"} onValueChange={(v) => updateFilter("domain", v)}>
              <SelectTrigger className="w-[170px] h-9" data-testid="select-ml-domain">
                <SelectValue placeholder="All domains" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All domains</SelectItem>
                {filterOptions.domains.map((d) => (
                  <SelectItem key={d} value={d}>{fieldLabel(d)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.severity || "all"} onValueChange={(v) => updateFilter("severity", v)}>
              <SelectTrigger className="w-[150px] h-9" data-testid="select-ml-severity">
                <SelectValue placeholder="All severities" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All severities</SelectItem>
                {filterOptions.severities.map((s) => (
                  <SelectItem key={s} value={s}>{fieldLabel(s)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.anomalyType || "all"} onValueChange={(v) => updateFilter("anomalyType", v)}>
              <SelectTrigger className="w-[170px] h-9" data-testid="select-ml-anomaly-type">
                <SelectValue placeholder="All anomaly types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All anomaly types</SelectItem>
                {filterOptions.anomalyTypes.map((t) => (
                  <SelectItem key={t} value={t}>{fieldLabel(t)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.dimension || "all"} onValueChange={(v) => updateFilter("dimension", v)}>
              <SelectTrigger className="w-[180px] h-9" data-testid="select-ml-dimension">
                <SelectValue placeholder="All dimensions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All dimensions</SelectItem>
                {filterOptions.dimensions.map((d) => (
                  <SelectItem key={d} value={d}>{d}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.trendDirection || "all"} onValueChange={(v) => updateFilter("trendDirection", v)}>
              <SelectTrigger className="w-[160px] h-9" data-testid="select-ml-trend-direction">
                <SelectValue placeholder="All directions" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All directions</SelectItem>
                {filterOptions.trendDirections.map((d) => (
                  <SelectItem key={d} value={d}>{fieldLabel(d)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            {active && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="h-9 px-3 text-muted-foreground hover:text-foreground"
                data-testid="button-clear-ml-filters"
              >
                <X className="w-4 h-4 mr-1" />
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      <SummaryCards summaries={summaries} anomalies={anomalies} trends={trends} />
      <RunsTable summaries={summaries} anomalyCounts={anomalyCounts} trendCounts={trendCounts} />
      <TopAnomalies anomalies={anomalies} />
      <TrendsSummary trends={trends} />
    </div>
  );
}
