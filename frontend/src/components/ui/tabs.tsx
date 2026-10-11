import * as TabsPrimitive from "@radix-ui/react-tabs";
import type { ComponentProps } from "react";
import { cn } from "@/lib/utils";

export const Tabs = TabsPrimitive.Root;
export function TabsList({
  className,
  ...p
}: ComponentProps<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn(
        "inline-flex h-8 items-center rounded-md border border-line bg-canvas p-0.5",
        className,
      )}
      {...p}
    />
  );
}
export function TabsTrigger({
  className,
  ...p
}: ComponentProps<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "inline-flex h-7 items-center gap-1 rounded px-2.5 text-[12px] font-medium text-muted disabled:opacity-40 disabled:cursor-not-allowed data-[state=active]:bg-panel data-[state=active]:text-ink data-[state=active]:shadow-sm [&_svg]:size-3.5",
        className,
      )}
      {...p}
    />
  );
}
export const TabsContent = TabsPrimitive.Content;
