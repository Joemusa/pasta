import { cn } from "@/lib/utils";
import type { InputHTMLAttributes, TextareaHTMLAttributes, SelectHTMLAttributes } from "react";

export function Input({ className, ...props }: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-9 w-full rounded-sm border border-rule bg-white px-3 text-sm text-ink-text placeholder:text-muted/70 focus:border-teal focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}

export function Textarea({ className, ...props }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return (
    <textarea
      className={cn(
        "w-full rounded-sm border border-rule bg-white px-3 py-2 text-sm text-ink-text placeholder:text-muted/70 focus:border-teal focus:outline-none",
        className,
      )}
      {...props}
    />
  );
}

export function Select({ className, children, ...props }: SelectHTMLAttributes<HTMLSelectElement>) {
  return (
    <select
      className={cn(
        "h-9 rounded-sm border border-rule bg-white px-2 text-sm text-ink-text focus:border-teal focus:outline-none",
        className,
      )}
      {...props}
    >
      {children}
    </select>
  );
}
