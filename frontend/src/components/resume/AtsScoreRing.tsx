type Props = { score: number; size?: number };

/**
 * Hairline ATS gauge: a thin brand-green arc on a faint track, with a large
 * tabular score in the centre. Static SVG (no stroke animation) so it stays
 * server-safe and never animates layout properties.
 */
export function AtsScoreRing({ score, size = 160 }: Props) {
  const clamped = Math.max(0, Math.min(100, score));
  const stroke = Math.max(4, Math.round(size / 28));
  const r = (size - stroke * 2 - 6) / 2;
  const circ = 2 * Math.PI * r;
  const dash = (clamped / 100) * circ;
  const center = size / 2;
  const innerR = r - stroke * 2 - 4;

  return (
    <div
      data-testid="ats-score"
      role="img"
      aria-label={`ATS score ${score} out of 100`}
      className="relative inline-grid shrink-0 place-items-center"
      style={{ width: size, height: size }}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="-rotate-90" aria-hidden="true">
        <circle cx={center} cy={center} r={r} stroke="hsl(var(--foreground) / 0.07)" strokeWidth={stroke} fill="none" />
        {innerR > 0 ? (
          <circle cx={center} cy={center} r={innerR} stroke="hsl(var(--foreground) / 0.05)" strokeWidth={1} fill="none" strokeDasharray="1 5" />
        ) : null}
        <circle
          cx={center}
          cy={center}
          r={r}
          stroke="hsl(var(--primary))"
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circ - dash}`}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <span
          className="font-geist font-semibold leading-none tracking-[-0.05em] text-foreground tabular-nums"
          style={{ fontSize: Math.round(size * 0.27) }}
        >
          {score}
        </span>
        <span className="mt-2 text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">ATS Score</span>
      </div>
    </div>
  );
}
