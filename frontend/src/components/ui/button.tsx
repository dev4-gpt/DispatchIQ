import { forwardRef, type ButtonHTMLAttributes } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

// shadcn/ui-style Button (hand-written: the shadcn registry was unreachable from the build environment).
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-md text-[13px] font-medium transition-colors disabled:pointer-events-none disabled:opacity-50 [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        primary: "bg-committed text-white hover:bg-blue-800",
        danger: "bg-emergency text-white hover:bg-red-800",
        approve: "bg-ok text-white hover:bg-green-800",
        outline: "border border-line bg-panel text-ink hover:bg-canvas",
        ghost: "text-ink hover:bg-canvas",
      },
      size: { sm: "h-8 px-2.5", md: "h-9 px-3", icon: "size-8" },
    },
    defaultVariants: { variant: "outline", size: "md" },
  },
);

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof buttonVariants> {}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, type = "button", ...props }, ref) => (
  <button ref={ref} type={type} className={cn(buttonVariants({ variant, size }), className)} {...props} />
));
Button.displayName = "Button";
