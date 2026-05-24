"use client";

import { useState } from "react";
import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { ApplicationKanban, type ApplicationItem } from "@/components/apps/ApplicationKanban";
import { ApplicationDrawer } from "@/components/apps/ApplicationDrawer";

// TODO wire to apiClient.applications.list()
const MOCK: ApplicationItem[] = [
  { id: "1", company: "Acme", role: "Frontend Engineer", matchPercent: 92, stage: "saved" },
  { id: "2", company: "BetaCorp", role: "Full-stack Dev", matchPercent: 87, stage: "applied", nextFollowUp: "in 2 days" },
  { id: "3", company: "Gamma", role: "Junior SDE", matchPercent: 81, stage: "viewed" },
  { id: "4", company: "Delta", role: "Backend Engineer", matchPercent: 74, stage: "interview" },
  { id: "5", company: "Epsilon", role: "DevOps", matchPercent: 69, stage: "rejected" },
];

export default function ApplicationsPage() {
  const [items] = useState<ApplicationItem[]>(MOCK);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const selected = items.find((i) => i.id === selectedId) ?? null;

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-6">
      <motion.div variants={fadeUp} className="flex items-center justify-between">
        <div>
          <div className="text-sm text-muted-foreground">Pipeline</div>
          <h1 className="mt-1 text-3xl font-medium">Applications</h1>
        </div>
        <div className="flex gap-2">
          <input
            placeholder="Filter by company or role…"
            className="h-10 rounded-full border border-border bg-card/40 px-4 text-sm placeholder:text-muted-foreground"
          />
        </div>
      </motion.div>

      <motion.div variants={fadeUp}>
        <ApplicationKanban items={items} onSelect={setSelectedId} />
      </motion.div>

      <ApplicationDrawer
        application={selected}
        open={selected !== null}
        onClose={() => setSelectedId(null)}
      />
    </motion.div>
  );
}
