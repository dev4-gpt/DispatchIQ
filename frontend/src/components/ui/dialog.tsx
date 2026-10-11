import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import type { ComponentProps, ReactNode } from "react";
import { cn } from "@/lib/utils";

export const Dialog = DialogPrimitive.Root;
export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;

export function DialogContent({
  className,
  children,
  title,
  description,
  side,
  ...p
}: ComponentProps<typeof DialogPrimitive.Content> & {
  title: string;
  description?: ReactNode;
  side?: "right";
}) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="fixed inset-0 z-[1000] bg-ink/30" />
      <DialogPrimitive.Content
        className={cn(
          "fixed z-[1001] bg-panel shadow-xl focus:outline-none",
          side === "right"
            ? "inset-y-0 right-0 flex w-[min(420px,100vw)] flex-col border-l border-line"
            : "left-1/2 top-1/2 w-[min(520px,calc(100vw-32px))] -translate-x-1/2 -translate-y-1/2 rounded-[12px] border border-line p-5",
          className,
        )}
        {...p}
      >
        <div
          className={cn(
            "flex items-start justify-between gap-3",
            side === "right" && "border-b border-line px-4 py-3",
          )}
        >
          <div>
            <DialogPrimitive.Title className="text-[16px] font-semibold">
              {title}
            </DialogPrimitive.Title>
            {description && (
              <DialogPrimitive.Description className="mt-0.5 text-[12px] text-muted">
                {description}
              </DialogPrimitive.Description>
            )}
          </div>
          <DialogPrimitive.Close
            aria-label="Close"
            className="rounded p-1 text-muted hover:bg-canvas"
          >
            <X className="size-4" />
          </DialogPrimitive.Close>
        </div>
        {children}
      </DialogPrimitive.Content>
    </DialogPrimitive.Portal>
  );
}
