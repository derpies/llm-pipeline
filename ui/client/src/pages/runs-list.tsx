import { useState } from "react";
import { useLocation } from "wouter";
import { useRuns, useDomains, useMeta } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { CopyableId } from "@/components/copyable-id";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { Skeleton } from "@/components/ui/skeleton";
import { Button } from "@/components/ui/button";
import { Search, ChevronLeft, ChevronRight, Activity, FlaskConical, BarChart3, AlertTriangle, FileText } from "lucide-react";
import type { PipelineRun, AnalyzeEmailRun, InvestigateRun } from "@shared/schema";

function formatDuration(start: string, end: string): string {
  const ms = new Date(end).getTime() - new Date(start).getTime();
  const totalSeconds = Math.floor(ms / 1000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (minutes === 0) return `${seconds}s`;
  return `${minutes}m ${seconds}s`;
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" }) +
    " " +
    d.toLocaleTimeString("en-US", { hour: "numeric", minute: "2-digit", hour12: true });
}

export default function RunsList() {
  const [, navigate] = useLocation();
  const [filters, setFilters] = useState({
    domain: "",
    command: "",
    status: "",
    search: "",
    source_file: "",
  });
  const [offset, setOffset] = useState(0);

  const { data: domains } = useDomains();
  const { data: meta } = useMeta();
  const { data, isLoading, error } = useRuns({
    ...filters,
    limit: "50",
    offset: String(offset),
  });

  const handleRowClick = (run: PipelineRun) => {
    if (run.command === "investigate") {
      navigate(`/investigations/${run.run_id}`);
    } else {
      navigate(`/ml/${run.run_id}`);
    }
  };

  const updateFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value === "all" ? "" : value }));
    setOffset(0);
  };

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4" data-testid="error-state">
        <div className="w-16 h-16 rounded-2xl bg-destructive/10 flex items-center justify-center">
          <AlertTriangle className="w-8 h-8 text-destructive" />
        </div>
        <h2 className="text-lg font-semibold">Connection Error</h2>
        <p className="text-sm text-muted-foreground max-w-md text-center">
          Unable to connect to the pipeline API. Ensure the backend is running.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6" data-testid="runs-list-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Pipeline Runs</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse all ML analysis and investigation pipeline executions
        </p>
      </div>

      <Card className="border-card-border">
        <CardContent className="p-4">
          <div className="flex flex-wrap gap-3 items-center">
            <div className="relative flex-1 min-w-[200px]">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search by run ID or label..."
                value={filters.search}
                onChange={(e) => updateFilter("search", e.target.value)}
                className="pl-9 h-9"
                data-testid="input-search"
              />
            </div>
            <div className="relative min-w-[180px]">
              <FileText className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Source file..."
                value={filters.source_file}
                onChange={(e) => updateFilter("source_file", e.target.value)}
                className="pl-9 h-9"
                data-testid="input-source-file"
              />
            </div>
            <Select value={filters.domain || "all"} onValueChange={(v) => updateFilter("domain", v)}>
              <SelectTrigger className="w-[170px] h-9" data-testid="select-domain">
                <SelectValue placeholder="All domains" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All domains</SelectItem>
                {domains?.map((d) => (
                  <SelectItem key={d.name} value={d.name}>{d.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.command || "all"} onValueChange={(v) => updateFilter("command", v)}>
              <SelectTrigger className="w-[170px] h-9" data-testid="select-command">
                <SelectValue placeholder="All commands" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All commands</SelectItem>
                {meta?.commands.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={filters.status || "all"} onValueChange={(v) => updateFilter("status", v)}>
              <SelectTrigger className="w-[140px] h-9" data-testid="select-status">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {meta?.run_statuses.map((s) => (
                  <SelectItem key={s} value={s}>{s}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </CardContent>
      </Card>

      <Card className="border-card-border overflow-hidden">
        {data && data.total > 50 && (
          <div className="border-b border-border px-4 py-3 flex items-center justify-between bg-muted/20" data-testid="runs-pagination-top">
            <span className="text-xs text-muted-foreground">
              Showing {offset + 1}–{Math.min(offset + 50, data.total)} of {data.total} runs
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 50))}
                data-testid="button-prev-page-top"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-xs text-muted-foreground px-2">
                Page {Math.floor(offset / 50) + 1} of {Math.ceil(data.total / 50)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + 50 >= data.total}
                onClick={() => setOffset(offset + 50)}
                data-testid="button-next-page-top"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
        <div className="overflow-x-auto">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/30 hover:bg-muted/30">
                <TableHead className="w-[120px] font-semibold text-xs uppercase tracking-wider">Run ID</TableHead>
                <TableHead className="font-semibold text-xs uppercase tracking-wider">Domain</TableHead>
                <TableHead className="font-semibold text-xs uppercase tracking-wider">Command</TableHead>
                <TableHead className="font-semibold text-xs uppercase tracking-wider">Created</TableHead>
                <TableHead className="font-semibold text-xs uppercase tracking-wider">Duration</TableHead>
                <TableHead className="font-semibold text-xs uppercase tracking-wider">Status / Label</TableHead>
                <TableHead className="font-semibold text-xs uppercase tracking-wider text-right">Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {isLoading ? (
                Array.from({ length: 5 }).map((_, i) => (
                  <TableRow key={i}>
                    {Array.from({ length: 7 }).map((_, j) => (
                      <TableCell key={j}><Skeleton className="h-5 w-full" /></TableCell>
                    ))}
                  </TableRow>
                ))
              ) : data?.runs.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={7} className="text-center py-12">
                    <div className="flex flex-col items-center gap-3">
                      <Activity className="w-10 h-10 text-muted-foreground/40" />
                      <p className="text-sm text-muted-foreground">No runs found matching your filters</p>
                    </div>
                  </TableCell>
                </TableRow>
              ) : (
                data?.runs.map((run) => {
                  const isInvestigation = run.command === "investigate";
                  const invRun = isInvestigation ? (run as InvestigateRun) : null;
                  const mlRun = !isInvestigation ? (run as AnalyzeEmailRun) : null;
                  return (
                    <TableRow
                      key={run.run_id}
                      className="cursor-pointer hover:bg-muted/40 transition-colors"
                      onClick={() => handleRowClick(run)}
                      data-testid={`row-run-${run.run_id.slice(0, 8)}`}
                    >
                      <TableCell>
                        <CopyableId value={run.run_id} />
                      </TableCell>
                      <TableCell className="text-xs text-muted-foreground">{run.domain}</TableCell>
                      <TableCell>
                        <StatusBadge status={run.command} />
                      </TableCell>
                      <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                        {formatDate(run.created_at)}
                      </TableCell>
                      <TableCell className="text-sm font-mono text-muted-foreground whitespace-nowrap">
                        {formatDuration(run.started_at, run.completed_at)}
                      </TableCell>
                      <TableCell>
                        {invRun ? (
                          <div className="flex items-center gap-2">
                            <StatusBadge status={invRun.status} />
                            {invRun.is_dry_run && <StatusBadge status="dry_run" />}
                            {invRun.label && (
                              <span className="text-xs text-muted-foreground font-mono">{invRun.label}</span>
                            )}
                          </div>
                        ) : (
                          <span className="text-xs text-muted-foreground">
                            {mlRun?.events_parsed?.toLocaleString()} events
                          </span>
                        )}
                      </TableCell>
                      <TableCell className="text-right">
                        {invRun ? (
                          <div className="flex items-center justify-end gap-3 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <FlaskConical className="w-3.5 h-3.5" />
                              {invRun.finding_count} findings
                            </span>
                            <span>{invRun.hypothesis_count} hyp.</span>
                          </div>
                        ) : (
                          <div className="flex items-center justify-end gap-3 text-xs text-muted-foreground">
                            <span className="flex items-center gap-1">
                              <BarChart3 className="w-3.5 h-3.5" />
                              {mlRun?.anomaly_count} anomalies
                            </span>
                            <span>{mlRun?.trend_count} trends</span>
                          </div>
                        )}
                      </TableCell>
                    </TableRow>
                  );
                })
              )}
            </TableBody>
          </Table>
        </div>

        {data && data.total > 50 && (
          <div className="border-t border-border px-4 py-3 flex items-center justify-between bg-muted/20" data-testid="runs-pagination-bottom">
            <span className="text-xs text-muted-foreground">
              Showing {offset + 1}–{Math.min(offset + 50, data.total)} of {data.total} runs
            </span>
            <div className="flex items-center gap-1">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - 50))}
                data-testid="button-prev-page-bottom"
              >
                <ChevronLeft className="w-4 h-4" />
              </Button>
              <span className="text-xs text-muted-foreground px-2">
                Page {Math.floor(offset / 50) + 1} of {Math.ceil(data.total / 50)}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + 50 >= data.total}
                onClick={() => setOffset(offset + 50)}
                data-testid="button-next-page-bottom"
              >
                <ChevronRight className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}
      </Card>

      {data && (
        <p className="text-xs text-muted-foreground text-center">
          {data.total} total run{data.total !== 1 ? "s" : ""}
        </p>
      )}
    </div>
  );
}
