import { useState } from "react";
import { Check, Copy } from "lucide-react";
import { cn } from "@/lib/utils";

interface CopyableIdProps {
  value: string;
  truncate?: boolean;
  className?: string;
}

export function CopyableId({ value, truncate = true, className }: CopyableIdProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = (e: React.MouseEvent) => {
    e.stopPropagation();
    navigator.clipboard.writeText(value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const display = truncate ? value.slice(0, 8) + "..." : value;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 font-mono text-xs cursor-pointer group",
        className
      )}
      onClick={handleCopy}
      title={value}
      data-testid={`copyable-${value.slice(0, 8)}`}
    >
      <span className="text-muted-foreground group-hover:text-foreground transition-colors">
        {display}
      </span>
      {copied ? (
        <Check className="w-3 h-3 text-emerald-500" />
      ) : (
        <Copy className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
      )}
    </span>
  );
}
