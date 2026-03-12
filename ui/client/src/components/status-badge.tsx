import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface StatusBadgeProps {
  status: string;
  className?: string;
}

const statusStyles: Record<string, string> = {
  success: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  partial: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20",
  failed: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20",
  dry_run: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
  confirmed: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  inconclusive: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
  disproven: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20",
  investigate: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20",
  analyze_email: "bg-teal-500/15 text-teal-700 dark:text-teal-400 border-teal-500/20",
  high: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20",
  medium: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20",
  low: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
  degrading: "bg-red-500/15 text-red-700 dark:text-red-400 border-red-500/20",
  improving: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  stable: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
  hypothesis: "bg-gray-500/15 text-gray-600 dark:text-gray-400 border-gray-500/20",
  finding: "bg-amber-500/15 text-amber-700 dark:text-amber-400 border-amber-500/20",
  truth: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20",
  grounded: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-400 border-emerald-500/20",
  community: "bg-blue-500/15 text-blue-700 dark:text-blue-400 border-blue-500/20",
  account: "bg-purple-500/15 text-purple-700 dark:text-purple-400 border-purple-500/20",
};

export function StatusBadge({ status, className }: StatusBadgeProps) {
  const style = statusStyles[status] || "bg-gray-500/15 text-gray-600 border-gray-500/20";
  return (
    <Badge
      variant="outline"
      className={cn("font-medium text-[11px] uppercase tracking-wider border", style, className)}
      data-testid={`badge-${status}`}
    >
      {status.replace(/_/g, " ")}
    </Badge>
  );
}
