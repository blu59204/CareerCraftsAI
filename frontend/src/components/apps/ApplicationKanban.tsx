"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

export type AppStage = "saved" | "applied" | "viewed" | "interview" | "offer" | "rejected";

export type ApplicationItem = {
  id: string;
  company: string;
  role: string;
  matchPercent: number;
  stage: AppStage;
  nextFollowUp?: string;
};

const COLUMNS: { stage: AppStage; label: string }[] = [
  { stage: "saved", label: "Saved" },
  { stage: "applied", label: "Applied" },
  { stage: "viewed", label: "Viewed" },
  { stage: "interview", label: "Interview" },
  { stage: "offer", label: "Offer" },
  { stage: "rejected", label: "Rejected" },
];

type Props = {
  items: ApplicationItem[];
  onSelect: (id: string) => void;
  onStageChange?: (id: string, newStage: AppStage) => void;
};

export function ApplicationKanban({ items, onSelect, onStageChange: _onStageChange }: Props) {
  return (
    <div className="grid grid-cols-2 gap-4 md:grid-cols-3 lg:grid-cols-6">
      {COLUMNS.map((col) => {
        const colItems = items.filter((it) => it.stage === col.stage);
        return (
          <div key={col.stage} className="rounded-3xl border border-border bg-card/40 p-4">
            <div className="mb-3 flex items-center justify-between text-xs text-muted-foreground">
              <span>{col.label}</span>
              <span>{colItems.length}</span>
            </div>
            <div className="space-y-3">
              {colItems.map((it) => (
                <motion.button
                  key={it.id}
                  type="button"
                  onClick={() => onSelect(it.id)}
                  {...cardHover}
                  className="w-full rounded-2xl border border-border bg-card p-3 text-left"
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-medium">{it.company}</span>
                    <span className="rounded-full bg-primary/15 px-2 py-0.5 text-[10px] text-primary">{it.matchPercent}%</span>
                  </div>
                  <div className="mt-1 text-xs text-muted-foreground">{it.role}</div>
                  {it.nextFollowUp && (
                    <div className="mt-2 text-[10px] text-warning">Follow up {it.nextFollowUp}</div>
                  )}
                </motion.button>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
