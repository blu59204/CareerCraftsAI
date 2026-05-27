type Props = {
  matched: string[];
  missing: string[];
};

export function KeywordCoverage({ matched, missing }: Props) {
  const total = matched.length + missing.length;
  const pct = total === 0 ? 0 : Math.round((matched.length / total) * 100);
  return (
    <div className="rounded-3xl border border-border bg-card/60 p-6">
      <div className="flex items-baseline justify-between">
        <div className="text-sm text-muted-foreground">Keyword coverage</div>
        <div className="text-2xl font-medium">{pct}%</div>
      </div>
      <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary" style={{ width: `${pct}%` }} />
      </div>
      <div className="mt-6 grid grid-cols-2 gap-4">
        <div>
          <div className="text-xs text-muted-foreground">Matched ({matched.length})</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {matched.map((k) => (
              <span key={k} className="rounded-full bg-success/15 px-2.5 py-1 text-xs text-success">{k}</span>
            ))}
          </div>
        </div>
        <div>
          <div className="text-xs text-muted-foreground">Missing ({missing.length})</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {missing.map((k) => (
              <span key={k} className="rounded-full bg-muted px-2.5 py-1 text-xs text-muted-foreground">{k}</span>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
