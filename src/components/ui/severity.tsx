import type { Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

const styles: Record<string, string> = {
  critical: "text-critical",
  high: "text-high",
  medium: "text-medium",
  low: "text-low",
  own: "text-muted",
};

export function SeverityDot({
  level,
  label,
  className,
}: {
  level: Severity | "own";
  label?: string;
  className?: string;
}) {
  const text =
    label ??
    (level === "own" ? "OWN BRAND" : level.toUpperCase());
  return (
    <span className={cn("inline-flex items-center gap-1.5 text-xs font-medium tracking-wide", className)}>
      <span
        className={cn("h-1.5 w-1.5 rounded-full", {
          "bg-critical": level === "critical",
          "bg-high": level === "high",
          "bg-medium": level === "medium",
          "bg-low": level === "low",
          "bg-muted": level === "own",
        })}
        aria-hidden
      />
      <span className={styles[level]}>{text}</span>
    </span>
  );
}
