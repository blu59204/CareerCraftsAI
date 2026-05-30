"use client";

import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const variants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-full border font-medium shadow-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      tone: {
        primary: "border-foreground bg-foreground text-background hover:opacity-90 dark:border-primary dark:bg-primary dark:text-primary-foreground",
        ghost: "border-border bg-card text-foreground hover:bg-muted",
        dark: "border-foreground bg-foreground text-background hover:opacity-90",
      },
      size: {
        sm: "h-9 px-4 text-sm",
        md: "h-11 px-6 text-sm",
        lg: "h-12 px-7 text-base",
      },
    },
    defaultVariants: { tone: "primary", size: "md" },
  },
);

export type LiquidGlassButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> &
  VariantProps<typeof variants>;

export const LiquidGlassButton = forwardRef<HTMLButtonElement, LiquidGlassButtonProps>(
  ({ className, tone, size, ...props }, ref) => (
    <button ref={ref} className={cn(variants({ tone, size }), className)} {...props} />
  ),
);
LiquidGlassButton.displayName = "LiquidGlassButton";
