import { Bezel } from "@/components/vanguard/Bezel";
import { Hairline } from "@/components/vanguard/Display";

type Props = {
  matched: string[];
  missing: string[];
};

function KeywordGroup({ label, keywords, tone }: { label: string; keywords: string[]; tone: "matched" | "missing" }) {
  return (
    <div>
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
        {label} <span className="tabular-nums">({keywords.length})</span>
      </p>
      {keywords.length ? (
        <ul className="mt-3 flex flex-wrap gap-1.5">
          {keywords.map((k) => (
            <li
              key={k}
              className={
                tone === "matched"
                  ? "rounded-full bg-success/10 px-2.5 py-1 text-xs text-success ring-1 ring-success/20"
                  : "rounded-full bg-foreground/[0.03] px-2.5 py-1 text-xs text-foreground/80 ring-1 ring-foreground/[0.08] dark:bg-white/[0.04] dark:ring-white/10"
              }
            >
              {k}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-xs text-muted-foreground">None</p>
      )}
    </div>
  );
}

export function KeywordCoverage({ matched, missing }: Props) {
  const total = matched.length + missing.length;
  const pct = total === 0 ? 0 : Math.round((matched.length / total) * 100);
  return (
    <Bezel coreClassName="p-5 md:p-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Keyword coverage</p>
          <p className="mt-1 text-xs text-muted-foreground">
            <span className="tabular-nums">{matched.length}</span> of <span className="tabular-nums">{total}</span> job keywords found
          </p>
        </div>
        <p className="font-geist text-4xl font-semibold leading-none tracking-[-0.04em] text-foreground tabular-nums">
          {pct}
          <span className="text-lg text-muted-foreground">%</span>
        </p>
      </div>
      <div
        role="progressbar"
        aria-label="Keyword coverage"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={pct}
        className="mt-4 h-1.5 w-full overflow-hidden rounded-full bg-foreground/[0.06] dark:bg-white/[0.08]"
      >
        <div
          className="h-full w-full origin-left rounded-full bg-primary transition-transform duration-700 ease-vanguard"
          style={{ transform: `scaleX(${pct / 100})` }}
        />
      </div>
      <div className="mt-6 space-y-5">
        <KeywordGroup label="Missing" keywords={missing} tone="missing" />
        <Hairline />
        <KeywordGroup label="Matched" keywords={matched} tone="matched" />
      </div>
    </Bezel>
  );
}
