import { useState } from "react";
import { Link } from "wouter";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useKnowledgeSearch, useKnowledgeStats, useMeta } from "@/lib/api";
import { StatusBadge } from "@/components/status-badge";
import { CopyableId } from "@/components/copyable-id";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Search,
  Brain,
  ExternalLink,
  ChevronLeft,
  ChevronRight,
  Eye,
  Hash,
  Tag,
} from "lucide-react";
import { cn } from "@/lib/utils";
import type { KnowledgeEntry } from "@shared/schema";

const tierColorMap: Record<string, string> = {
  grounded: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  truth: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20",
  finding: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20",
  hypothesis: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
};

export default function KnowledgeBrowser() {
  const [inputValue, setInputValue] = useState("");
  const [query, setQuery] = useState("");
  const [selectedTiers, setSelectedTiers] = useState<Set<string>>(new Set());
  const [offset, setOffset] = useState(0);
  const pageSize = 20;

  const { data: meta } = useMeta();
  const { data: stats, isLoading: statsLoading } = useKnowledgeStats();
  const tierFilter = selectedTiers.size === 1 ? [...selectedTiers][0] : undefined;
  const { data: searchResults, isLoading: searchLoading } = useKnowledgeSearch(
    query,
    tierFilter,
    offset,
    pageSize
  );

  const submitSearch = () => {
    setQuery(inputValue);
    setOffset(0);
  };

  const clearSearch = () => {
    setInputValue("");
    setQuery("");
    setOffset(0);
  };

  const totalEntries = stats?.reduce((sum, s) => sum + s.count, 0) || 0;

  const toggleTier = (tier: string) => {
    setSelectedTiers((prev) => {
      const next = new Set(prev);
      if (next.has(tier)) next.delete(tier);
      else next.add(tier);
      return next;
    });
    setOffset(0);
  };

  const filteredResults = searchResults?.results.filter(
    (e) => selectedTiers.size === 0 || selectedTiers.has(e.tier)
  );
  const totalResults = searchResults?.total ?? 0;

  return (
    <div className="space-y-6" data-testid="knowledge-browser-page">
      <div>
        <h1 className="text-2xl font-bold tracking-tight" data-testid="text-page-title">Knowledge Store</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Browse accumulated learnings across pipeline runs ({totalEntries.toLocaleString()} entries)
        </p>
      </div>

      <div className="grid grid-cols-4 gap-3">
        {statsLoading ? (
          Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-24" />
          ))
        ) : (
          stats?.map((stat) => {
            const tierMeta = meta?.knowledge_tiers.find((t) => t.name === stat.tier);
            const isSelected = selectedTiers.has(stat.tier);
            return (
              <button
                key={stat.tier}
                onClick={() => toggleTier(stat.tier)}
                className={cn(
                  "text-left p-4 rounded-lg border transition-all",
                  selectedTiers.has(stat.tier)
                    ? "border-primary bg-primary/5 ring-1 ring-primary/30"
                    : "border-card-border bg-card hover:bg-muted/30"
                )}
                data-testid={`button-tier-${stat.tier}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <Badge
                    variant="outline"
                    className={cn("text-[10px] uppercase tracking-wider border font-medium", tierColorMap[stat.tier])}
                  >
                    {stat.tier}
                  </Badge>
                  <span className="text-xl font-bold">{stat.count.toLocaleString()}</span>
                </div>
                <p className="text-[11px] text-muted-foreground leading-snug">{tierMeta?.description || stat.description}</p>
              </button>
            );
          })
        )}
      </div>

      <Card className="border-card-border">
        <CardContent className="p-4">
          <div className="relative flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                placeholder="Search knowledge entries... (press Enter)"
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter") submitSearch(); }}
                className="pl-9 h-10"
                data-testid="input-knowledge-search"
              />
            </div>
            {query && (
              <Button variant="outline" size="sm" className="h-10" onClick={clearSearch}>
                Clear
              </Button>
            )}
          </div>
        </CardContent>
      </Card>

      {totalResults > pageSize && <PaginationBar position="top" offset={offset} pageSize={pageSize} total={totalResults} onOffsetChange={setOffset} />}

      <div className="space-y-3">
        {searchLoading ? (
          Array.from({ length: 3 }).map((_, i) => (
            <Skeleton key={i} className="h-40" />
          ))
        ) : !filteredResults || filteredResults.length === 0 ? (
          <Card className="border-card-border">
            <CardContent className="flex flex-col items-center justify-center py-16 gap-3">
              <Brain className="w-12 h-12 text-muted-foreground/30" />
              <p className="text-sm text-muted-foreground">
                {query ? "No results found for your search" : "No knowledge entries available"}
              </p>
            </CardContent>
          </Card>
        ) : (
          filteredResults.map((entry) => (
            <KnowledgeEntryCard key={entry.entry_id} entry={entry} />
          ))
        )}
      </div>

      {totalResults > pageSize && <PaginationBar position="bottom" offset={offset} pageSize={pageSize} total={totalResults} onOffsetChange={setOffset} />}
    </div>
  );
}

function PaginationBar({ position, offset, pageSize, total, onOffsetChange }: { position: "top" | "bottom"; offset: number; pageSize: number; total: number; onOffsetChange: (v: number) => void }) {
  return (
    <div className="flex items-center justify-between border border-card-border rounded-lg px-4 py-3 bg-card" data-testid={`knowledge-pagination-${position}`}>
      <span className="text-xs text-muted-foreground">
        Showing {offset + 1}–{Math.min(offset + pageSize, total)} of {total.toLocaleString()} entries
      </span>
      <div className="flex items-center gap-1">
        <Button
          variant="outline"
          size="sm"
          disabled={offset === 0}
          onClick={() => onOffsetChange(Math.max(0, offset - pageSize))}
          data-testid={`button-knowledge-prev-${position}`}
        >
          <ChevronLeft className="w-4 h-4" />
        </Button>
        <span className="text-xs text-muted-foreground px-2">
          Page {Math.floor(offset / pageSize) + 1} of {Math.ceil(total / pageSize)}
        </span>
        <Button
          variant="outline"
          size="sm"
          disabled={offset + pageSize >= total}
          onClick={() => onOffsetChange(offset + pageSize)}
          data-testid={`button-knowledge-next-${position}`}
        >
          <ChevronRight className="w-4 h-4" />
        </Button>
      </div>
    </div>
  );
}

/** Truncate a markdown string at a character limit, breaking at a word boundary. */
function truncateMarkdown(text: string, maxLen: number): string {
  if (text.length <= maxLen) return text;
  // Find last space before the limit to avoid mid-word breaks
  const breakAt = text.lastIndexOf(" ", maxLen);
  const cutoff = breakAt > maxLen * 0.5 ? breakAt : maxLen;
  return text.slice(0, cutoff) + "…";
}

function KnowledgeEntryCard({ entry }: { entry: KnowledgeEntry }) {
  const [expanded, setExpanded] = useState(false);
  const isLong = entry.statement.length > 200;

  return (
    <Card className="border-card-border" data-testid={`card-knowledge-${entry.entry_id.slice(0, 8)}`}>
      <CardContent className="p-5 space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-2 flex-wrap">
            <Badge
              variant="outline"
              className={cn("text-[10px] uppercase tracking-wider border font-medium", tierColorMap[entry.tier])}
            >
              {entry.tier}
            </Badge>
            <StatusBadge status={entry.scope} />
            {entry.finding_status && (
              <StatusBadge status={entry.finding_status} />
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground shrink-0">
            <span className="flex items-center gap-1" title="Confidence">
              <span className="font-semibold text-foreground">{(entry.confidence * 100).toFixed(0)}%</span>
              conf.
            </span>
            <span className="flex items-center gap-1" title="Weighted score">
              <span className="font-mono">{entry.weighted_score.toFixed(3)}</span>
              score
            </span>
          </div>
        </div>

        <h3 className="font-semibold text-[15px]">{entry.topic}</h3>

        <div>
          <div className="prose prose-sm dark:prose-invert max-w-none text-muted-foreground">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {isLong && !expanded ? truncateMarkdown(entry.statement, 200) : entry.statement}
            </ReactMarkdown>
          </div>
          {isLong && (
            <button
              onClick={() => setExpanded(!expanded)}
              className="text-xs text-primary hover:text-primary/80 font-medium mt-1 flex items-center gap-1"
              data-testid="button-expand-statement"
            >
              <Eye className="w-3 h-3" />
              {expanded ? "Show less" : "Show more"}
            </button>
          )}
        </div>

        <div className="flex items-center flex-wrap gap-3 pt-2 border-t border-border">
          {entry.dimension && (
            <span className="inline-flex items-center gap-1 text-xs bg-muted/50 px-2 py-1 rounded font-mono">
              <Tag className="w-3 h-3 text-muted-foreground" />
              {entry.dimension}: {entry.dimension_value}
            </span>
          )}
          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
            <Hash className="w-3 h-3" />
            {entry.observation_count} observation{entry.observation_count !== 1 ? "s" : ""}
          </span>
          {entry.source_run_ids.length > 0 && (
            <div className="flex items-center gap-1.5">
              <ExternalLink className="w-3 h-3 text-muted-foreground" />
              {entry.source_run_ids.map((id: string) => (
                <Link key={id} href={`/investigations/${id}`} data-testid={`link-source-run-${id.slice(0, 8)}`}>
                  <span className="text-xs text-primary hover:underline cursor-pointer font-mono">
                    {id.slice(0, 8)}...
                  </span>
                </Link>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
