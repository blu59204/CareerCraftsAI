"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  jobs: { id: string; company: string; role: string; matchPercent: number; location?: string; jobUrl?: string | null }[];
};

export function JobMatchCard({ jobs }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-border bg-card/60 p-6">
      <div className="flex items-center justify-between">
        <div className="text-sm text-muted-foreground">Top job matches</div>
        <Link href="/applications" className="text-xs text-primary hover:underline">
          View all
        </Link>
      </div>
      {jobs.length > 0 ? (
        <ul className="mt-4 space-y-3">
          {jobs.slice(0, 4).map((j) => {
            const content = (
              <>
                <div className="min-w-0">
                  <div className="truncate text-sm font-medium">{j.role}</div>
                  <div className="truncate text-xs text-muted-foreground">
                    {j.company}
                    {j.location ? ` · ${j.location}` : ""}
                  </div>
                </div>
                <span className="shrink-0 rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
                  {j.matchPercent}%
                </span>
              </>
            );
            const itemClass = "flex items-center justify-between gap-2 rounded-2xl border border-border/60 bg-card/40 px-4 py-3 transition-colors hover:bg-card/70";
            return j.jobUrl ? (
              <li key={j.id}>
                <a href={j.jobUrl} target="_blank" rel="noopener noreferrer" className={itemClass}>
                  {content}
                </a>
              </li>
            ) : (
              <li key={j.id} className={itemClass}>
                {content}
              </li>
            );
          })}
        </ul>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
          No saved jobs yet. Run Search Jobs to find matches.
        </div>
      )}
    </motion.div>
  );
}
