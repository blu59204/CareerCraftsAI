"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  atsScore: number;
  keywordCoverage: number;
  missingKeywords: string[];
};

export function ResumeScoreCard({ atsScore, keywordCoverage, missingKeywords }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-border bg-card/60 p-6">
      <div className="flex items-baseline justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Resume score</div>
          <div className="mt-2 text-4xl font-medium">{atsScore}/100</div>
        </div>
        <div className="text-right text-sm text-muted-foreground">
          <div>Keyword coverage</div>
          <div className="mt-1 font-medium text-foreground">{keywordCoverage}%</div>
        </div>
      </div>
      <div className="mt-4 h-2 w-full overflow-hidden rounded-full bg-muted">
        <div className="h-full bg-primary" style={{ width: `${keywordCoverage}%` }} />
      </div>
      {missingKeywords.length > 0 && (
        <div className="mt-6">
          <div className="text-xs text-muted-foreground">Missing keywords</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {missingKeywords.slice(0, 8).map((k) => (
              <span key={k} className="rounded-full border border-border bg-card px-3 py-1 text-xs">
                {k}
              </span>
            ))}
          </div>
        </div>
      )}
    </motion.div>
  );
}
