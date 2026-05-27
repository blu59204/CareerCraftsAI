"use client";

import Link from "next/link";
import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

type Props = {
  jobs: { id: string; company: string; role: string; matchPercent: number; location?: string }[];
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
      <ul className="mt-4 space-y-3">
        {jobs.slice(0, 4).map((j) => (
          <li key={j.id} className="flex items-center justify-between rounded-2xl border border-border/60 bg-card/40 px-4 py-3">
            <div>
              <div className="text-sm font-medium">{j.role}</div>
              <div className="text-xs text-muted-foreground">
                {j.company}
                {j.location ? ` · ${j.location}` : ""}
              </div>
            </div>
            <span className="rounded-full bg-primary/15 px-2.5 py-1 text-xs font-medium text-primary">
              {j.matchPercent}%
            </span>
          </li>
        ))}
      </ul>
    </motion.div>
  );
}
