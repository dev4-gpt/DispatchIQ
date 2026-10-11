import type { HTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const badgeVariants = cva("inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded px-1.5 py-0.5 text-[11px] font-medium leading-none [&_svg]:size-3", {
  variants: {
    tone: {
      neutral: "bg-canvas text-muted border border-line",
      blue: "bg-committed-soft text-committed",
      amber: "bg-proposed-soft text-proposed",
      red: "bg-emergency-soft text-emergency",
      green: "bg-ok-soft text-ok",
    },
  },
  defaultVariants: { tone: "neutral" },
});

export function Badge({ className, tone, ...props }: HTMLAttributes<HTMLSpanElement> & VariantProps<typeof badgeVariants>) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
