import { useState } from "react";
import { useParams, Link } from "wouter";
import { useMLSummary, useAnomalies, useTrends, useAggregations, useCompleteness, useDomains } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { CopyableId } from "@/components/copyable-id";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ArrowLeft,
  ArrowDown,
  ArrowUp,
  ArrowRight,
  AlertTriangle,
  TrendingUp,
  BarChart3,
  Database,
  Clock,
  FileStack,
  Zap,
} from "lucide-react";
import { cn } from "@/lib/utils";

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit", hour12: true,
  });
}

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  return `${minutes}m ${seconds}s`;
}

function formatPercent(v: number): string {
  return (v * 100).toFixed(1) + "%";
}

function formatNumber(v: number): string {
  if (Math.abs(v) < 0.01 && v !== 0) return v.toExponential(2);
  if (Math.abs(v) < 1) return v.toFixed(4);
  return v.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function DirectionArrow({ direction }: { direction: string }) {
  if (direction === "degrading") return <ArrowDown className="w-4 h-4 text-red-500" />;
  if (direction === "improving") return <ArrowUp className="w-4 h-4 text-emerald-500" />;
  return <ArrowRight className="w-4 h-4 text-gray-400" />;
}

function fieldLabel(field: string): string {
  return field
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function isRateField(field: string): boolean {
  return field.includes("rate");
}

function formatMetricValue(field: string, value: number): string {
  if (isRateField(field)) return formatPercent(value);
  if (field.includes("latency") || field.includes("time")) return value.toFixed(1) + "s";
  return formatNumber(value);
}

export default function MLDetail() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId || "";
  const { data: summary, isLoading, error } = useMLSummary(runId);
  const { data: anomalies } = useAnomalies(runId);
  const { data: trends } = useTrends(runId);
  const { data: domains } = useDomains();

  const [aggDimension, setAggDimension] = useState("");
  const [compField, setCompField] = useState("");
  const { data: aggregations } = useAggregations(runId, { dimension: aggDimension });
  const { data: completeness } = useCompleteness(runId, { field_name: compField });

  const domain = summary?.domain ? domains?.find((d) => d.name === summary.domain) : undefined;
  const dimensions = domain?.ml_data_types.dimensions || [];
  const metrics = domain?.ml_data_types.metrics || [];
  const deliveryStatuses = domain?.ml_data_types.delivery_statuses || [];
  const completenessFields = domain?.ml_data_types.completeness_fields || [];
  const thresholds = domain?.ml_data_types.segment_thresholds || {};

  const sortedAnomalies = anomalies
    ? [...anomalies].sort((a, b) => {
        const severityOrder: Record<string, number> = { high: 0, medium: 1, low: 2 };
        const sevDiff = (severityOrder[a.severity] || 3) - (severityOrder[b.severity] || 3);
        if (sevDiff !== 0) return sevDiff;
        return Math.abs(b.z_score) - Math.abs(a.z_score);
      })
    : [];

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !summary) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4" data-testid="error-state">
        <AlertTriangle className="w-12 h-12 text-destructive" />
        <h2 className="text-lg font-semibold">ML Run Not Found</h2>
        <Link href="/" className="text-sm text-primary hover:underline" data-testid="link-back-home">Return to runs list</Link>
      </div>
    );
  }

  const isSegmentBelowThreshold = (dimValue: string, metricField: string, value: number) => {
    if (!isRateField(metricField)) return false;
    const segCode = dimValue.replace(/-.*/, "");
    const threshold = thresholds[segCode];
    return threshold !== undefined && value < threshold;
  };

  const aggMetricColumns = metrics.length > 0
    ? metrics
    : aggregations?.aggregations?.[0]
      ? Object.keys(aggregations.aggregations[0]).filter(
          (k) => !["time_window", "dimension", "dimension_value", "total", "delivered", "bounced", "deferred", "dropped", "complained"].includes(k) && typeof (aggregations.aggregations[0] as Record<string, any>)[k] === "number"
        )
      : [];
  const primaryRateMetric = aggMetricColumns.find((m) => isRateField(m)) || aggMetricColumns[0];

  return (
    <div className="space-y-6" data-testid="ml-detail-page">
      <div className="flex items-center gap-3">
        <Link href="/" data-testid="link-back">
          <span className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer">
            <ArrowLeft className="w-4 h-4" />
            Back to runs
          </span>
        </Link>
      </div>

      <Card className="border-card-border">
        <CardContent className="p-6">
          <div className="space-y-2 mb-5">
            <div className="flex items-center gap-3">
              <h1 className="text-xl font-bold tracking-tight" data-testid="text-ml-title">ML Analysis</h1>
              <StatusBadge status={summary.domain} />
            </div>
            <CopyableId value={summary.run_id} truncate={false} />
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-border">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Duration</p>
              <p className="text-sm font-mono flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                {formatDuration(summary.started_at, summary.completed_at)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Events Parsed</p>
              <p className="text-sm font-semibold flex items-center gap-1.5">
                <Zap className="w-3.5 h-3.5 text-amber-500" />
                {summary.events_parsed.toLocaleString()}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Files Processed</p>
              <p className="text-sm font-semibold flex items-center gap-1.5">
                <FileStack className="w-3.5 h-3.5 text-muted-foreground" />
                {summary.files_processed}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Started</p>
              <p className="text-sm">{formatDate(summary.started_at)}</p>
            </div>
          </div>

          <div className="grid grid-cols-4 gap-3 mt-4 pt-4 border-t border-border">
            {[
              { label: "Aggregations", value: summary.counts.aggregations, icon: BarChart3, color: "text-blue-500" },
              { label: "Anomalies", value: summary.counts.anomalies, icon: AlertTriangle, color: "text-red-500" },
              { label: "Trends", value: summary.counts.trends, icon: TrendingUp, color: "text-emerald-500" },
              { label: "Completeness", value: summary.counts.completeness, icon: Database, color: "text-purple-500" },
            ].map((item) => (
              <div key={item.label} className="flex items-center gap-3 p-3 rounded-lg bg-muted/30">
                <item.icon className={cn("w-5 h-5", item.color)} />
                <div>
                  <p className="text-lg font-bold">{item.value}</p>
                  <p className="text-[11px] text-muted-foreground uppercase tracking-wider">{item.label}</p>
                </div>
              </div>
            ))}
          </div>
        </CardContent>
      </Card>

      <Tabs defaultValue="anomalies" className="space-y-4">
        <TabsList className="bg-muted/50" data-testid="tabs-ml">
          <TabsTrigger value="anomalies" className="gap-1.5" data-testid="tab-anomalies">
            <AlertTriangle className="w-3.5 h-3.5" />
            Anomalies ({summary.counts.anomalies})
          </TabsTrigger>
          <TabsTrigger value="trends" className="gap-1.5" data-testid="tab-trends">
            <TrendingUp className="w-3.5 h-3.5" />
            Trends ({summary.counts.trends})
          </TabsTrigger>
          <TabsTrigger value="aggregations" className="gap-1.5" data-testid="tab-aggregations">
            <BarChart3 className="w-3.5 h-3.5" />
            Aggregations
          </TabsTrigger>
          <TabsTrigger value="completeness" className="gap-1.5" data-testid="tab-completeness">
            <Database className="w-3.5 h-3.5" />
            Completeness
          </TabsTrigger>
        </TabsList>

        <TabsContent value="anomalies">
          <Card className="border-card-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Severity</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Type</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Dimension</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Value</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Metric</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Current</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Baseline</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Z-Score</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sortedAnomalies.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12 text-sm text-muted-foreground">
                      No anomalies detected
                    </TableCell>
                  </TableRow>
                ) : (
                  sortedAnomalies.map((a, i) => (
                    <TableRow key={i} data-testid={`row-anomaly-${i}`}>
                      <TableCell><StatusBadge status={a.severity} /></TableCell>
                      <TableCell className="text-sm font-mono">{a.anomaly_type}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{a.dimension}</TableCell>
                      <TableCell className="text-sm font-mono font-medium">{a.dimension_value}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{a.metric}</TableCell>
                      <TableCell className="text-sm font-mono text-right font-semibold">
                        {a.metric.includes("rate") ? formatPercent(a.current_value) : formatNumber(a.current_value)}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-right text-muted-foreground">
                        {a.metric.includes("rate") ? formatPercent(a.baseline_mean) : formatNumber(a.baseline_mean)}
                      </TableCell>
                      <TableCell className={cn(
                        "text-sm font-mono text-right font-semibold",
                        Math.abs(a.z_score) >= 4 ? "text-red-600" : Math.abs(a.z_score) >= 3 ? "text-amber-600" : ""
                      )}>
                        {a.z_score > 0 ? "+" : ""}{a.z_score.toFixed(1)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="trends">
          <Card className="border-card-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead className="font-semibold text-xs uppercase tracking-wider w-[80px]">Direction</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Dimension</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Value</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Metric</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Slope</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">R&sup2;</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Points</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Start &rarr; End</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {(trends || []).length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={8} className="text-center py-12 text-sm text-muted-foreground">
                      No trends detected
                    </TableCell>
                  </TableRow>
                ) : (
                  (trends || []).map((t, i) => (
                    <TableRow key={i} data-testid={`row-trend-${i}`}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <DirectionArrow direction={t.direction} />
                          <StatusBadge status={t.direction} />
                        </div>
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground">{t.dimension}</TableCell>
                      <TableCell className="text-sm font-mono font-medium">{t.dimension_value}</TableCell>
                      <TableCell className="text-sm text-muted-foreground">{t.metric}</TableCell>
                      <TableCell className="text-sm font-mono text-right">
                        {t.slope > 0 ? "+" : ""}{t.slope.toFixed(4)}
                      </TableCell>
                      <TableCell className={cn(
                        "text-sm font-mono text-right",
                        t.r_squared >= 0.8 ? "font-semibold" : "text-muted-foreground"
                      )}>
                        {t.r_squared.toFixed(2)}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-right text-muted-foreground">{t.num_points}</TableCell>
                      <TableCell className="text-sm font-mono text-right">
                        {t.metric.includes("rate") ? formatPercent(t.start_value) : formatNumber(t.start_value)}
                        <span className="text-muted-foreground mx-1">&rarr;</span>
                        {t.metric.includes("rate") ? formatPercent(t.end_value) : formatNumber(t.end_value)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>

        <TabsContent value="aggregations" className="space-y-4">
          <Card className="border-card-border">
            <CardContent className="p-4">
              <Select value={aggDimension || "all"} onValueChange={(v) => setAggDimension(v === "all" ? "" : v)}>
                <SelectTrigger className="w-[220px] h-9" data-testid="select-agg-dimension">
                  <SelectValue placeholder="All dimensions" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All dimensions</SelectItem>
                  {dimensions.map((d) => (
                    <SelectItem key={d} value={d}>{d}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
          <Card className="border-card-border overflow-hidden">
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="bg-muted/30 hover:bg-muted/30">
                    <TableHead className="font-semibold text-xs uppercase tracking-wider">Dimension</TableHead>
                    <TableHead className="font-semibold text-xs uppercase tracking-wider">Value</TableHead>
                    <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Total</TableHead>
                    {aggMetricColumns.map((col) => (
                      <TableHead key={col} className="font-semibold text-xs uppercase tracking-wider text-right">
                        {fieldLabel(col)}
                      </TableHead>
                    ))}
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {!aggregations || aggregations.aggregations.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={3 + aggMetricColumns.length} className="text-center py-12 text-sm text-muted-foreground">
                        No aggregation data
                      </TableCell>
                    </TableRow>
                  ) : (
                    aggregations.aggregations.map((a, i) => {
                      const rowData = a as Record<string, any>;
                      const belowThreshold = isSegmentBelowThreshold(a.dimension_value, primaryRateMetric, rowData[primaryRateMetric] ?? 0);
                      return (
                        <TableRow
                          key={i}
                          className={belowThreshold ? "bg-amber-500/5" : ""}
                          data-testid={`row-agg-${i}`}
                        >
                          <TableCell className="text-sm text-muted-foreground">{a.dimension}</TableCell>
                          <TableCell>
                            <span className="text-sm font-mono font-medium">{a.dimension_value}</span>
                            {belowThreshold && (
                              <AlertTriangle className="w-3.5 h-3.5 text-amber-500 inline ml-1.5" />
                            )}
                          </TableCell>
                          <TableCell className="text-sm font-mono text-right">{a.total.toLocaleString()}</TableCell>
                          {aggMetricColumns.map((col) => {
                            const val = rowData[col];
                            const isBelowForCol = col === primaryRateMetric && belowThreshold;
                            return (
                              <TableCell
                                key={col}
                                className={cn(
                                  "text-sm font-mono text-right",
                                  isBelowForCol ? "font-semibold text-amber-600" : ""
                                )}
                              >
                                {val !== undefined ? formatMetricValue(col, val) : "—"}
                              </TableCell>
                            );
                          })}
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </div>
          </Card>
        </TabsContent>

        <TabsContent value="completeness" className="space-y-4">
          <Card className="border-card-border">
            <CardContent className="p-4">
              <Select value={compField || "all"} onValueChange={(v) => setCompField(v === "all" ? "" : v)}>
                <SelectTrigger className="w-[260px] h-9" data-testid="select-comp-field">
                  <SelectValue placeholder="All fields" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All fields</SelectItem>
                  {completenessFields.map((f) => (
                    <SelectItem key={f} value={f}>{f}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
          <Card className="border-card-border overflow-hidden">
            <Table>
              <TableHeader>
                <TableRow className="bg-muted/30 hover:bg-muted/30">
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Dimension</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Value</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider">Field</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Total Records</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Zero Count</TableHead>
                  <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Zero Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {!completeness || completeness.completeness.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-12 text-sm text-muted-foreground">
                      No completeness data
                    </TableCell>
                  </TableRow>
                ) : (
                  completeness.completeness.map((c, i) => (
                    <TableRow key={i} data-testid={`row-comp-${i}`}>
                      <TableCell className="text-sm text-muted-foreground">{c.dimension}</TableCell>
                      <TableCell className="text-sm font-mono font-medium">{c.dimension_value}</TableCell>
                      <TableCell className="text-sm font-mono text-muted-foreground">{c.field_name}</TableCell>
                      <TableCell className="text-sm font-mono text-right">{c.total_records.toLocaleString()}</TableCell>
                      <TableCell className="text-sm font-mono text-right">{c.zero_count.toLocaleString()}</TableCell>
                      <TableCell className={cn(
                        "text-sm font-mono text-right font-semibold",
                        c.zero_rate > 0.50 ? "text-red-600" : c.zero_rate > 0.20 ? "text-amber-600" : ""
                      )}>
                        {formatPercent(c.zero_rate)}
                      </TableCell>
                    </TableRow>
                  ))
                )}
              </TableBody>
            </Table>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
