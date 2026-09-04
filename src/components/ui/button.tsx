import { cva, type VariantProps } from "class-variance-authority";
import type { ButtonHTMLAttributes } from "react";
import { cn } from "@/lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 rounded-sm text-[13px] font-medium tracking-tight transition-colors disabled:pointer-events-none disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-teal",
  {
    variants: {
      variant: {
        primary: "bg-teal text-white hover:bg-teal-2 px-3.5 py-2",
        secondary:
          "bg-transparent text-ink-text border border-rule hover:bg-paper-2 px-3.5 py-2",
        ghost: "bg-transparent text-muted hover:text-ink-text px-2.5 py-2",
        danger: "bg-transparent text-critical border border-critical/30 hover:bg-critical/10 px-3.5 py-2",
      },
      size: {
        sm: "text-xs py-1.5 px-2.5",
        md: "text-[13px]",
      },
    },
    defaultVariants: { variant: "primary", size: "md" },
  },
);

type Props = ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof buttonVariants>;

export function Button({ className, variant, size, ...props }: Props) {
  return (
    <button className={cn(buttonVariants({ variant, size }), className)} {...props} />
  );
}
