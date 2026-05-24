"use client";

import { forwardRef } from "react";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const variants = cva(
  "inline-flex items-center justify-center gap-2 rounded-full font-medium transition-all liquid-glass focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50 disabled:pointer-events-none",
  {
    variants: {
      tone: {
        primary: "bg-primary text-primary-foreground hover:opacity-95",
        ghost: "bg-card/40 text-foreground hover:bg-card/70",
        dark: "bg-foreground text-background hover:opacity-90",
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
