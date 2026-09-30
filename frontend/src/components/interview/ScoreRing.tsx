import { cn } from "@/lib/utils";

/**
 * Static SVG score ring shared by the Mock interview and Prep plan panels.
 * The ring is drawn once (no stroke animation — entrances are handled by the
 * parent's opacity/transform reveal). The numeric value is rendered in HTML
 * so it stays selectable and never includes a "/max" suffix: e2e journeys
 * assert a single "/100" text node per feedback entry.
 */
export type ScoreTone = "success" | "warning" | "danger" | "primary" | "neutral";

const TONE_STROKE: Record<ScoreTone, string> = {
  success: "text-success",
  warning: "text-warning",
  danger: "text-danger",
  primary: "text-primary",
  neutral: "text-muted-foreground",
};

/** Map a 0–100 score onto the semantic tones used across the interview screen. */
export function scoreTone(value: number): ScoreTone {
  if (value >= 80) return "success";
  if (value >= 60) return "warning";
  return "danger";
}

export function ScoreRing({
  value,
  max = 100,
  size = 64,
  stroke = 5,
  tone,
  suffix,
  label = "Score",
  className,
  valueClassName,
}: {
  value: number;
  max?: number;
  size?: number;
  stroke?: number;
  tone?: ScoreTone;
  /** Small unit rendered after the number (e.g. "%"). */
  suffix?: string;
  /** Accessible name prefix. */
  label?: string;
  className?: string;
  valueClassName?: string;
}) {
  const safe = Number.isFinite(value) ? Math.max(0, Math.min(value, max)) : 0;
  const pct = max > 0 ? safe / max : 0;
  const radius = (size - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const resolvedTone = tone ?? scoreTone(pct * 100);

  return (
    <div
      role="img"
      aria-label={`${label}: ${Math.round(safe)} out of ${max}`}
      className={cn("relative inline-grid shrink-0 place-items-center", className)}
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          className="stroke-foreground/[0.07] dark:stroke-white/10"
        />
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={stroke}
          strokeLinecap="round"
          stroke="currentColor"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - pct)}
          className={TONE_STROKE[resolvedTone]}
        />
      </svg>
      <span
        aria-hidden
        className={cn(
          "absolute inset-0 grid place-items-center font-geist font-semibold tabular-nums tracking-[-0.03em] text-foreground",
          size >= 120 ? "text-4xl" : size >= 80 ? "text-2xl" : "text-sm",
          valueClassName,
        )}
      >
        <span>
          {Math.round(safe)}
          {suffix ? <span className="ml-0.5 text-[0.55em] font-medium text-muted-foreground">{suffix}</span> : null}
        </span>
      </span>
    </div>
  );
}
