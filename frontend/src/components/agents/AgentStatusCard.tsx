"use client";

import { motion } from "motion/react";
import { CheckCircle2, Clock3, Loader2, TriangleAlert } from "lucide-react";
import { cardHover } from "@/lib/motion-variants";

export type AgentRunStatus = "queued" | "running" | "succeeded" | "completed" | "failed" | "awaiting_approval";

const STATUS_STYLES: Record<AgentRunStatus, string> = {
  queued: "border-muted bg-muted/20 text-muted-foreground",
  running: "border-primary/30 bg-primary/10 text-primary",
  succeeded: "border-success/30 bg-success/10 text-success",
  completed: "border-success/30 bg-success/10 text-success",
  failed: "border-danger/30 bg-danger/10 text-danger",
  awaiting_approval: "border-warning/30 bg-warning/10 text-warning",
};

const STATUS_ICONS: Record<AgentRunStatus, typeof Clock3> = {
  queued: Clock3,
  running: Loader2,
  succeeded: CheckCircle2,
  completed: CheckCircle2,
  failed: TriangleAlert,
  awaiting_approval: Clock3,
};

type Props = {
  agentName: string;
  status: AgentRunStatus;
  latestMessage?: string;
  startedAt?: string;
};

export function AgentStatusCard({ agentName, status, latestMessage, startedAt }: Props) {
  const normalizedStatus: AgentRunStatus = STATUS_ICONS[status] ? status : "queued";
  const StatusIcon = STATUS_ICONS[normalizedStatus];
  return (
    <motion.div {...cardHover} className="rounded-xl border border-border bg-background/45 p-3">
      <div className="flex items-start gap-3">
        <span className={`mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border ${STATUS_STYLES[normalizedStatus]}`}>
          <StatusIcon className={`h-4 w-4 ${normalizedStatus === "running" ? "animate-spin" : ""}`} />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center justify-between gap-2">
            <div className="truncate text-sm font-medium">{agentName}</div>
            <span className={`shrink-0 rounded-full border px-2 py-0.5 text-[11px] ${STATUS_STYLES[normalizedStatus]}`}>
              {normalizedStatus.replace("_", " ")}
            </span>
          </div>
          {latestMessage && <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{latestMessage}</p>}
          {startedAt && <div className="mt-2 text-[11px] text-muted-foreground">Started {startedAt}</div>}
        </div>
      </div>
    </motion.div>
  );
}
