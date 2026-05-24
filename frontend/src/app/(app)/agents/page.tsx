"use client";

import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Bot, FileText, Search, Linkedin, Mail, Bell, Sparkles } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";
import { EmptyState } from "@/components/ui/EmptyState";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient } from "@/lib/api";

const AGENTS = [
  { key: "orchestrator", label: "Orchestrator", icon: Sparkles },
  { key: "resume", label: "Resume", icon: FileText },
  { key: "job", label: "Job Search", icon: Search },
  { key: "linkedin", label: "LinkedIn", icon: Linkedin },
  { key: "email", label: "Email", icon: Mail },
  { key: "followup", label: "Follow-up", icon: Bell },
];

interface AgentRun {
  id: string;
  agent_type: string;
  status: string;
  created_at: string;
  duration_ms: number | null;
}

function relativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function AgentsPage() {
  const [active, setActive] = useState("orchestrator");

  const { data: runs = [], isLoading: runsLoading } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=10");
      return data;
    },
  });

  const filteredRuns = active === "orchestrator"
    ? runs
    : runs.filter((r) => r.agent_type === active || r.agent_type === `${active}_optimize`);
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="grid gap-6 lg:grid-cols-[220px_1fr_320px]">
      <motion.aside variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-3">
        <div className="px-2 py-2 text-xs uppercase tracking-wide text-muted-foreground">Agents</div>
        <nav className="space-y-1">
          {AGENTS.map((a) => {
            const Icon = a.icon;
            const isActive = active === a.key;
            return (
              <button
                key={a.key}
                onClick={() => setActive(a.key)}
                className={`flex w-full items-center gap-2 rounded-2xl px-3 py-2 text-sm ${
                  isActive ? "bg-primary/15 text-foreground" : "text-muted-foreground hover:bg-card"
                }`}
              >
                <Icon className="h-4 w-4" />
                {a.label}
              </button>
            );
          })}
        </nav>
      </motion.aside>

      <motion.section variants={fadeUp} className="rounded-3xl border border-border bg-card/40 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Bot className="h-5 w-5 text-primary" />
            <div className="font-medium">{AGENTS.find((a) => a.key === active)?.label} Agent</div>
          </div>
          <LiquidGlassButton tone="primary" size="sm">Run</LiquidGlassButton>
        </div>
        <div className="mt-6 min-h-[400px] rounded-2xl border border-border bg-background/40 p-4">
          <EmptyState
            icon={<Sparkles className="h-6 w-6" />}
            title="Automate repetitive applications."
            description="Tell the orchestrator what role you're after. It'll route work across the resume, job, email, and follow-up agents."
            action={<LiquidGlassButton tone="primary">Start run</LiquidGlassButton>}
          />
        </div>
      </motion.section>

      <motion.aside variants={fadeUp} className="space-y-3">
        <div className="text-sm text-muted-foreground">Context</div>
        <div className="rounded-3xl border border-border bg-card/40 p-4 text-sm">
          <div className="text-xs text-muted-foreground">Resume</div>
          <div className="mt-1">resume-v3.pdf</div>
          <div className="mt-3 text-xs text-muted-foreground">Target role</div>
          <div className="mt-1">Frontend Engineer</div>
          <div className="mt-3 text-xs text-muted-foreground">Model</div>
          <div className="mt-1">Anthropic · claude-sonnet-4-6</div>
        </div>
        <div className="text-sm text-muted-foreground">Run history</div>
        {runsLoading ? (
          <>
            <div className="h-16 shimmer rounded-3xl" />
            <div className="h-16 shimmer rounded-3xl" />
          </>
        ) : filteredRuns.length === 0 ? (
          <div className="rounded-2xl border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
            No runs yet for this agent.
          </div>
        ) : (
          filteredRuns.map((run) => (
            <AgentStatusCard
              key={run.id}
              agentName={`${run.agent_type.charAt(0).toUpperCase() + run.agent_type.slice(1).replace(/_/g, " ")} Agent`}
              status={run.status === "completed" ? "succeeded" : run.status === "failed" ? "failed" : "running"}
              latestMessage={run.duration_ms ? `Completed in ${run.duration_ms}ms` : "In progress…"}
              startedAt={relativeTime(run.created_at)}
            />
          ))
        )}
        {runs.some((r) => r.status === "awaiting_approval") && (
          <ApprovalCard
            title="Action pending your approval"
            summary="An agent action requires your review before proceeding."
            onApprove={() => {}}
            onReject={() => {}}
          />
        )}
      </motion.aside>
    </motion.div>
  );
}
