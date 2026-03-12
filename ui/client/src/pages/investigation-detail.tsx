import { useParams, Link } from "wouter";
import { useInvestigation, useInvestigationReport } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { CopyableId } from "@/components/copyable-id";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import {
  ArrowLeft,
  Clock,
  FileText,
  AlertTriangle,
  ChevronDown,
  ExternalLink,
  FlaskConical,
  Lightbulb,
  BookOpen,
  ListChecks,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Finding, Hypothesis } from "@shared/schema";
import { useState } from "react";

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}m ${s}s`;
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString("en-US", {
    month: "short", day: "numeric", year: "numeric",
    hour: "numeric", minute: "2-digit", hour12: true,
  });
}

function FindingCard({ finding }: { finding: Finding }) {
  return (
    <Card className="border-card-border" data-testid={`card-finding-${finding.topic_title.slice(0, 20)}`}>
      <CardContent className="p-5 space-y-4">
        <div className="flex items-start justify-between gap-3">
          <h3 className="font-semibold text-[15px] leading-snug">{finding.topic_title}</h3>
          <div className="flex items-center gap-2 shrink-0">
            <StatusBadge status={finding.status} />
            {finding.is_fallback && (
              <Badge variant="outline" className="bg-amber-500/15 text-amber-700 border-amber-500/20 text-[10px]">
                FALLBACK
              </Badge>
            )}
          </div>
        </div>

        <blockquote className="border-l-2 border-primary/30 pl-4 text-sm text-muted-foreground italic leading-relaxed">
          {finding.statement}
        </blockquote>

        <div className="space-y-3">
          <div>
            <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Evidence</h4>
            <ul className="space-y-1.5">
              {finding.evidence.map((e, i) => (
                <li key={i} className="text-sm text-muted-foreground flex gap-2">
                  <span className="text-primary/60 mt-0.5 shrink-0">&bull;</span>
                  <span className="font-mono text-xs leading-relaxed">{e}</span>
                </li>
              ))}
            </ul>
          </div>

          {Object.keys(finding.metrics_cited).length > 0 && (
            <div>
              <h4 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Metrics Cited</h4>
              <div className="flex flex-wrap gap-2">
                {Object.entries(finding.metrics_cited).map(([key, value]) => (
                  <span
                    key={key}
                    className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-muted/50 text-xs font-mono"
                  >
                    <span className="text-muted-foreground">{key}:</span>
                    <span className="font-semibold">{typeof value === "number" && value < 1 && value > 0 ? (value * 100).toFixed(1) + "%" : value.toLocaleString()}</span>
                  </span>
                ))}
              </div>
            </div>
          )}

          {finding.quality_warnings.length > 0 && (
            <div className="flex items-start gap-2 p-3 rounded-md bg-amber-500/10 border border-amber-500/20">
              <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
              <div className="text-xs text-amber-700 dark:text-amber-400 space-y-0.5">
                {finding.quality_warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

function HypothesisCard({ hypothesis }: { hypothesis: Hypothesis }) {
  const [open, setOpen] = useState(false);
  return (
    <Card className="border-card-border" data-testid={`card-hypothesis-${hypothesis.topic_title.slice(0, 20)}`}>
      <CardContent className="p-5 space-y-3">
        <div className="flex items-start gap-3">
          <Lightbulb className="w-5 h-5 text-amber-500 shrink-0 mt-0.5" />
          <div className="space-y-2 flex-1">
            <h3 className="font-semibold text-[15px]">{hypothesis.topic_title}</h3>
            <p className="text-sm text-muted-foreground leading-relaxed">{hypothesis.statement}</p>
            <Collapsible open={open} onOpenChange={setOpen}>
              <CollapsibleTrigger className="flex items-center gap-1.5 text-xs text-primary hover:text-primary/80 font-medium" data-testid="button-toggle-reasoning">
                <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? "rotate-180" : ""}`} />
                {open ? "Hide" : "Show"} reasoning
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <p className="text-sm text-muted-foreground leading-relaxed bg-muted/30 p-3 rounded-md">
                  {hypothesis.reasoning}
                </p>
              </CollapsibleContent>
            </Collapsible>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export default function InvestigationDetail() {
  const params = useParams<{ runId: string }>();
  const runId = params.runId || "";
  const { data, isLoading, error } = useInvestigation(runId);
  const [reportView, setReportView] = useState<"markdown" | "json">("markdown");
  const { data: reportMd } = useInvestigationReport(runId, "markdown");
  const { data: reportJson } = useInvestigationReport(runId, "json");

  if (isLoading) {
    return (
      <div className="space-y-6">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  if (error || !data) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4" data-testid="error-state">
        <AlertTriangle className="w-12 h-12 text-destructive" />
        <h2 className="text-lg font-semibold">Investigation Not Found</h2>
        <Link href="/" className="text-sm text-primary hover:underline" data-testid="link-back-home">Return to runs list</Link>
      </div>
    );
  }

  const confirmedFindings = data.findings.filter((f) => f.status === "confirmed");
  const inconclusiveFindings = data.findings.filter((f) => f.status === "inconclusive");
  const disprovenFindings = data.findings.filter((f) => f.status === "disproven");

  return (
    <div className="space-y-6" data-testid="investigation-detail-page">
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
          <div className="flex flex-wrap items-start justify-between gap-4 mb-5">
            <div className="space-y-2">
              <div className="flex items-center gap-3">
                <h1 className="text-xl font-bold tracking-tight" data-testid="text-investigation-title">Investigation</h1>
                <StatusBadge status={data.domain} />
                <StatusBadge status={data.status} />
                {data.is_dry_run && <StatusBadge status="dry_run" />}
              </div>
              <div className="flex items-center gap-2">
                <CopyableId value={data.run_id} truncate={false} />
              </div>
              {data.label && (
                <p className="text-sm font-mono text-primary">{data.label}</p>
              )}
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 pt-4 border-t border-border">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Duration</p>
              <p className="text-sm font-mono flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5 text-muted-foreground" />
                {formatDuration(data.duration_seconds)}
              </p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Iterations</p>
              <p className="text-sm font-semibold">{data.iteration_count}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Findings</p>
              <p className="text-sm font-semibold">{data.finding_count}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Hypotheses</p>
              <p className="text-sm font-semibold">{data.hypothesis_count}</p>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4 pt-4 border-t border-border">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Started</p>
              <p className="text-sm">{formatDate(data.started_at)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Completed</p>
              <p className="text-sm">{formatDate(data.completed_at)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">ML Run</p>
              <Link href={`/ml/${data.ml_run_id}`} data-testid="link-ml-run">
                <span className="text-sm text-primary hover:underline cursor-pointer inline-flex items-center gap-1">
                  <CopyableId value={data.ml_run_id} />
                  <ExternalLink className="w-3 h-3" />
                </span>
              </Link>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Source Files</p>
              {data.source_files.map((f, i) => (
                <CopyableId key={i} value={f} truncate={false} className="block" />
              ))}
            </div>
          </div>

          {data.quality_warnings.length > 0 && (
            <Collapsible className="mt-4 pt-4 border-t border-border">
              <CollapsibleTrigger className="flex items-center gap-2 text-sm" data-testid="button-toggle-warnings">
                <AlertTriangle className="w-4 h-4 text-amber-500" />
                <span className="font-medium text-amber-700 dark:text-amber-400">
                  {data.quality_warnings.length} quality warning{data.quality_warnings.length > 1 ? "s" : ""}
                </span>
                <ChevronDown className="w-4 h-4 text-muted-foreground" />
              </CollapsibleTrigger>
              <CollapsibleContent className="mt-2">
                <ul className="space-y-1">
                  {data.quality_warnings.map((w, i) => (
                    <li key={i} className="text-sm text-amber-700 dark:text-amber-400 font-mono bg-amber-500/10 px-3 py-1.5 rounded-md">
                      {w}
                    </li>
                  ))}
                </ul>
              </CollapsibleContent>
            </Collapsible>
          )}
        </CardContent>
      </Card>

      <Tabs defaultValue="findings" className="space-y-4">
        <TabsList className="bg-muted/50" data-testid="tabs-investigation">
          <TabsTrigger value="findings" className="gap-1.5" data-testid="tab-findings">
            <FlaskConical className="w-3.5 h-3.5" />
            Findings ({data.findings.length})
          </TabsTrigger>
          <TabsTrigger value="hypotheses" className="gap-1.5" data-testid="tab-hypotheses">
            <Lightbulb className="w-3.5 h-3.5" />
            Hypotheses ({data.hypotheses.length})
          </TabsTrigger>
          <TabsTrigger value="synthesis" className="gap-1.5" data-testid="tab-synthesis">
            <BookOpen className="w-3.5 h-3.5" />
            Synthesis
          </TabsTrigger>
          <TabsTrigger value="report" className="gap-1.5" data-testid="tab-report">
            <FileText className="w-3.5 h-3.5" />
            Report
          </TabsTrigger>
        </TabsList>

        <TabsContent value="findings" className="space-y-6">
          {confirmedFindings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-emerald-600 flex items-center gap-2">
                <ListChecks className="w-4 h-4" />
                Confirmed ({confirmedFindings.length})
              </h3>
              <div className="space-y-3">
                {confirmedFindings.map((f, i) => <FindingCard key={i} finding={f} />)}
              </div>
            </div>
          )}
          {inconclusiveFindings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-gray-500 flex items-center gap-2">
                Inconclusive ({inconclusiveFindings.length})
              </h3>
              <div className="space-y-3">
                {inconclusiveFindings.map((f, i) => <FindingCard key={i} finding={f} />)}
              </div>
            </div>
          )}
          {disprovenFindings.length > 0 && (
            <div className="space-y-3">
              <h3 className="text-sm font-semibold uppercase tracking-wider text-red-500 flex items-center gap-2">
                Disproven ({disprovenFindings.length})
              </h3>
              <div className="space-y-3">
                {disprovenFindings.map((f, i) => <FindingCard key={i} finding={f} />)}
              </div>
            </div>
          )}
        </TabsContent>

        <TabsContent value="hypotheses" className="space-y-3">
          {data.hypotheses.length === 0 ? (
            <Card className="border-card-border">
              <CardContent className="flex flex-col items-center justify-center py-12 gap-3">
                <Lightbulb className="w-10 h-10 text-muted-foreground/40" />
                <p className="text-sm text-muted-foreground">No hypotheses generated</p>
              </CardContent>
            </Card>
          ) : (
            data.hypotheses.map((h, i) => <HypothesisCard key={i} hypothesis={h} />)
          )}
        </TabsContent>

        <TabsContent value="synthesis">
          <Card className="border-card-border">
            <CardContent className="p-6">
              {data.synthesis_narrative ? (
                <div className="prose prose-sm dark:prose-invert max-w-none">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{data.synthesis_narrative}</ReactMarkdown>
                </div>
              ) : (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <BookOpen className="w-10 h-10 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">No synthesis available</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="report">
          <Card className="border-card-border">
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base">Report</CardTitle>
                <div className="flex gap-1 bg-muted/50 rounded-md p-0.5">
                  <button
                    onClick={() => setReportView("markdown")}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      reportView === "markdown" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
                    }`}
                    data-testid="button-report-markdown"
                  >
                    Rendered
                  </button>
                  <button
                    onClick={() => setReportView("json")}
                    className={`px-3 py-1 rounded text-xs font-medium transition-colors ${
                      reportView === "json" ? "bg-background shadow-sm" : "text-muted-foreground hover:text-foreground"
                    }`}
                    data-testid="button-report-json"
                  >
                    JSON
                  </button>
                </div>
              </div>
            </CardHeader>
            <CardContent>
              {reportMd || reportJson ? (
                reportView === "markdown" && reportMd?.markdown ? (
                  <div className="prose prose-sm dark:prose-invert max-w-none">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{reportMd.markdown}</ReactMarkdown>
                  </div>
                ) : (
                  <pre className="text-xs font-mono bg-muted/30 p-4 rounded-md overflow-x-auto">
                    {JSON.stringify(reportJson?.report || reportJson, null, 2)}
                  </pre>
                )
              ) : (
                <div className="flex flex-col items-center justify-center py-12 gap-3">
                  <FileText className="w-10 h-10 text-muted-foreground/40" />
                  <p className="text-sm text-muted-foreground">Report not available</p>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}
