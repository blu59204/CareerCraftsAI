import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/utils";

/**
 * Double-Bezel (Doppelrand) enclosure: an outer tray (hairline ring, faint
 * tint, padding) holding an inner core with its own surface, top highlight
 * and a concentric radius (outer radius − padding).
 *
 * size  lg → outer 2rem / p-1.5 / inner calc(2rem-0.375rem)
 *       md → outer 1.5rem / p-1 / inner calc(1.5rem-0.25rem)
 *       sm → outer 1.25rem / p-1 / inner calc(1.25rem-0.25rem)
 *
 * tone  default → card surface; muted → recessed surface (inputs, logs);
 *       primary → brand-tinted core for the one hero/active panel;
 *       danger  → destructive zone.
 */
export type BezelSize = "lg" | "md" | "sm";
export type BezelTone = "default" | "muted" | "primary" | "danger";

const SHELL: Record<BezelSize, string> = {
  lg: "rounded-[2rem] p-1.5",
  md: "rounded-[1.5rem] p-1",
  sm: "rounded-[1.25rem] p-1",
};
const CORE: Record<BezelSize, string> = {
  lg: "rounded-[calc(2rem-0.375rem)]",
  md: "rounded-[calc(1.5rem-0.25rem)]",
  sm: "rounded-[calc(1.25rem-0.25rem)]",
};
const SHELL_TONE: Record<BezelTone, string> = {
  default: "bg-foreground/[0.025] ring-1 ring-foreground/[0.06] dark:bg-white/[0.025] dark:ring-white/[0.08]",
  muted: "bg-foreground/[0.02] ring-1 ring-foreground/[0.05] dark:bg-white/[0.02] dark:ring-white/[0.06]",
  primary: "bg-primary/[0.06] ring-1 ring-primary/15",
  danger: "bg-danger/[0.05] ring-1 ring-danger/20",
};
const CORE_TONE: Record<BezelTone, string> = {
  default: "bg-card shadow-bezel-core dark:shadow-bezel-core-dark",
  muted: "bg-muted/50 shadow-bezel-core dark:bg-background/60 dark:shadow-bezel-core-dark",
  primary: "bg-card shadow-bezel-core dark:shadow-bezel-core-dark bg-[radial-gradient(120%_80%_at_0%_0%,hsl(var(--primary)/0.10),transparent_60%)]",
  danger: "bg-card shadow-bezel-core dark:shadow-bezel-core-dark",
};

export interface BezelProps extends HTMLAttributes<HTMLDivElement> {
  size?: BezelSize;
  tone?: BezelTone;
  /** Classes for the inner core (padding, layout). Outer `className` styles the shell. */
  coreClassName?: string;
  /** Add the soft ambient lift shadow to the shell. */
  lifted?: boolean;
}

export const Bezel = forwardRef<HTMLDivElement, BezelProps>(
  ({ size = "lg", tone = "default", className, coreClassName, lifted = false, children, ...props }, ref) => (
    <div ref={ref} className={cn("min-w-0 max-w-full", SHELL[size], SHELL_TONE[tone], lifted && "shadow-ambient", className)} {...props}>
      <div className={cn("relative h-full min-w-0", CORE[size], CORE_TONE[tone], coreClassName)}>{children}</div>
    </div>
  ),
);
Bezel.displayName = "Bezel";

/** Class strings for elements that need bezel styling without the wrapper component (e.g. motion.button). */
export const bezelShell = (size: BezelSize = "md", tone: BezelTone = "default") => cn(SHELL[size], SHELL_TONE[tone]);
export const bezelCore = (size: BezelSize = "md", tone: BezelTone = "default") => cn(CORE[size], CORE_TONE[tone]);
