"use client";

import { motion } from "motion/react";
import { cardHover } from "@/lib/motion-variants";

export type AgentRunStatus = "queued" | "running" | "succeeded" | "failed" | "awaiting_approval";

const STATUS_STYLES: Record<AgentRunStatus, string> = {
  queued: "bg-muted text-muted-foreground",
  running: "bg-primary/15 text-primary",
  succeeded: "bg-success/15 text-success",
  failed: "bg-danger/15 text-danger",
  awaiting_approval: "bg-warning/15 text-warning",
};

type Props = {
  agentName: string;
  status: AgentRunStatus;
  latestMessage?: string;
  startedAt?: string;
};

export function AgentStatusCard({ agentName, status, latestMessage, startedAt }: Props) {
  return (
    <motion.div {...cardHover} className="rounded-3xl border border-border bg-card/60 p-5">
      <div className="flex items-center justify-between">
        <div className="text-sm font-medium">{agentName}</div>
        <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_STYLES[status]}`}>
          {status.replace("_", " ")}
        </span>
      </div>
      {latestMessage && <p className="mt-3 text-sm text-muted-foreground line-clamp-2">{latestMessage}</p>}
      {startedAt && <div className="mt-2 text-xs text-muted-foreground">Started {startedAt}</div>}
    </motion.div>
  );
}
