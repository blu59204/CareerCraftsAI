import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Bezel } from "./Bezel";

/** Semantic status pill with an optional live dot. */
export type StatusTone = "neutral" | "primary" | "success" | "warning" | "danger";

const STATUS: Record<StatusTone, { pill: string; dot: string }> = {
  neutral: { pill: "bg-foreground/[0.04] text-muted-foreground ring-foreground/[0.08] dark:bg-white/[0.05] dark:ring-white/10", dot: "bg-muted-foreground" },
  primary: { pill: "bg-primary/10 text-primary ring-primary/20", dot: "bg-primary" },
  success: { pill: "bg-success/10 text-success ring-success/25", dot: "bg-success" },
  warning: { pill: "bg-warning/10 text-warning ring-warning/25", dot: "bg-warning" },
  danger: { pill: "bg-danger/10 text-danger ring-danger/25", dot: "bg-danger" },
};

export function StatusPill({
  tone = "neutral",
  children,
  live = false,
  icon,
  className,
}: {
  tone?: StatusTone;
  children: ReactNode;
  /** Pulsing dot for in-progress states. */
  live?: boolean;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <span className={cn("inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium ring-1", STATUS[tone].pill, className)}>
      {icon ? (
        <span aria-hidden className="grid place-items-center">{icon}</span>
      ) : (
        <span aria-hidden className="relative flex h-1.5 w-1.5">
          {live ? <span className={cn("absolute inset-0 animate-ping rounded-full opacity-60 motion-reduce:hidden", STATUS[tone].dot)} /> : null}
          <span className={cn("relative h-1.5 w-1.5 rounded-full", STATUS[tone].dot)} />
        </span>
      )}
      {children}
    </span>
  );
}

/** Big tabular metric. Use inside a Bezel or a StatStrip. */
export function Stat({ label, value, hint, className }: { label: ReactNode; value: ReactNode; hint?: ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0", className)}>
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">{label}</p>
      <p className="mt-3 font-geist text-4xl font-semibold tabular-nums tracking-[-0.04em] text-foreground md:text-5xl">{value}</p>
      {hint ? <p className="mt-2 text-xs text-muted-foreground">{hint}</p> : null}
    </div>
  );
}

/** Horizontal strip of stats in a single bezel, hairline-divided. Collapses to 2 cols on mobile. */
export function StatStrip({ items, className }: { items: Array<{ label: ReactNode; value: ReactNode; hint?: ReactNode }>; className?: string }) {
  return (
    <Bezel className={className} coreClassName="grid grid-cols-2 gap-px overflow-hidden bg-foreground/[0.06] dark:bg-white/[0.06] md:grid-flow-col md:auto-cols-fr md:grid-cols-none">
      {items.map((item, i) => (
        <div key={i} className="bg-card px-5 py-6 md:px-7 md:py-8">
          <Stat {...item} />
        </div>
      ))}
    </Bezel>
  );
}

/** Empty / zero state with an icon medallion, copy and an optional action. */
export function EmptyPanel({
  icon,
  title,
  description,
  action,
  className,
  compact = false,
}: {
  icon?: ReactNode;
  title: ReactNode;
  description?: ReactNode;
  action?: ReactNode;
  className?: string;
  compact?: boolean;
}) {
  return (
    <div className={cn("flex flex-col items-center text-center", compact ? "px-4 py-8" : "px-6 py-16 md:py-20", className)}>
      {icon ? (
        <span aria-hidden className="grid h-14 w-14 place-items-center rounded-full bg-foreground/[0.04] text-foreground/70 ring-1 ring-foreground/[0.06] shadow-bezel-core dark:bg-white/[0.05] dark:ring-white/10 dark:shadow-bezel-core-dark">
          {icon}
        </span>
      ) : null}
      <p className={cn("font-geist font-semibold tracking-[-0.02em] text-foreground", icon && "mt-5", compact ? "text-sm" : "text-lg")}>{title}</p>
      {description ? <p className="mt-2 max-w-[42ch] text-sm leading-6 text-muted-foreground">{description}</p> : null}
      {action ? <div className="mt-6">{action}</div> : null}
    </div>
  );
}

/** Shimmer placeholder block that matches bezel radii. */
export function Skeleton({ className }: { className?: string }) {
  return <div aria-hidden className={cn("shimmer rounded-[1.25rem]", className)} />;
}

/** Hairline divider. */
export function Hairline({ className, vertical = false }: { className?: string; vertical?: boolean }) {
  return <div aria-hidden className={cn(vertical ? "w-px self-stretch" : "h-px w-full", "bg-foreground/[0.07] dark:bg-white/[0.07]", className)} />;
}

/** Inline notice (HITL reminders, warnings, errors). */
export function Notice({ tone = "neutral", icon, children, className }: { tone?: StatusTone; icon?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <div role={tone === "danger" ? "alert" : undefined} className={cn("flex items-start gap-3 rounded-2xl px-4 py-3.5 text-sm leading-6 ring-1", STATUS[tone].pill, className)}>
      {icon ? <span aria-hidden className="mt-0.5 shrink-0">{icon}</span> : null}
      <div className="min-w-0">{children}</div>
    </div>
  );
}
