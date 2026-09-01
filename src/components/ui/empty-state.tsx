import { cn } from "@/lib/utils";

export function EmptyState({
  title,
  body,
  className,
}: {
  title: string;
  body?: string;
  className?: string;
}) {
  return (
    <div className={cn("border border-dashed border-rule bg-paper-2/50 px-5 py-10", className)}>
      <p className="text-sm font-medium text-ink-text">{title}</p>
      {body ? <p className="mt-1 max-w-lg text-sm text-muted">{body}</p> : null}
    </div>
  );
}
