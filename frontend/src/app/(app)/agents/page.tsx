"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Bot, FileText, Search, Linkedin, Mail, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { AgentStatusStream } from "@/components/agents/AgentStatusStream";
import { EmptyState } from "@/components/ui/EmptyState";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient } from "@/lib/api";

// BUG 4: map UI keys to backend VALID_TASKS
// "orchestrator" and "followup" have no backend equivalent — removed from list
const AGENTS = [
  { key: "resume_optimize", label: "Resume", icon: FileText },
  { key: "job_search", label: "Job Search", icon: Search },
  { key: "linkedin_optimize", label: "LinkedIn", icon: Linkedin },
  { key: "email", label: "Email", icon: Mail },
  { key: "interview_prep", label: "Interview Prep", icon: Sparkles },
];

// BUG 6: interface matches backend AgentRunResponse (started_at, not created_at)
interface AgentRun {
  id: string;
  agent_type: string;
  status: string;
  started_at: string;
  duration_ms: number | null;
}

interface UserMe {
  full_name: string | null;
  active_model?: string | null;
}

interface RagDocument {
  filename: string;
  doc_type: string;
  is_primary: boolean;
}

function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export default function AgentsPage() {
  const [active, setActive] = useState("resume_optimize");
  const [activeRunId, setActiveRunId] = useState<string | null>(null);
  const qc = useQueryClient();

  const runMutation = useMutation({
    mutationFn: () =>
      apiClient.post<{ run_id: string }>("/agents/run", { task_type: active, context: {} }),
    onSuccess: (res) => {
      toast.success(`${AGENTS.find((a) => a.key === active)?.label} Agent started`);
      setActiveRunId(res.data.run_id);
      setTimeout(() => qc.invalidateQueries({ queryKey: ["agent-runs"] }), 3000);
    },
    onError: () => toast.error("Agent unavailable — backend not connected"),
  });

  const { data: runs = [], isLoading: runsLoading } = useQuery<AgentRun[]>({
    queryKey: ["agent-runs"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=10");
      return data;
    },
  });

  // BUG 19: fetch context sidebar from API
  const { data: userMe } = useQuery<UserMe>({
    queryKey: ["user-me"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me");
      return data;
    },
  });

  const { data: ragDocs = [] } = useQuery<RagDocument[]>({
    queryKey: ["rag-documents"],
    queryFn: async () => {
      const { data } = await apiClient.get("/rag/documents");
      return data;
    },
  });

  // BUG 19: fetch active model from /users/me/models
  const { data: userModels = [] } = useQuery<{ id: string; provider: string; model_name: string | null; is_active: boolean }[]>({
    queryKey: ["user-models"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/models");
      return data;
    },
  });

  const activeModel = userModels.find((m) => m.is_active);
  const primaryResume = ragDocs.find((d) => d.doc_type === "resume" && d.is_primary);
  const filteredRuns = runs.filter(
    (r) => r.agent_type === active
  );

  // BUG 7: find the awaiting run to pass run_id to approval
  const awaitingRun = runs.find((r) => r.status === "awaiting_approval");

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
          <LiquidGlassButton
            tone="primary"
            size="sm"
            disabled={runMutation.isPending}
            onClick={() => runMutation.mutate()}
          >
            {runMutation.isPending ? "Running…" : "Run"}
          </LiquidGlassButton>
        </div>
        <div className="mt-6 min-h-[400px] rounded-2xl border border-border bg-background/40 p-4">
          {/* BUG 12: mount AgentStatusStream when a run is active */}
          {activeRunId ? (
            <AgentStatusStream
              runId={activeRunId}
              onApprove={() => {
                qc.invalidateQueries({ queryKey: ["agent-runs"] });
                setActiveRunId(null);
              }}
              onCancel={() => {
                qc.invalidateQueries({ queryKey: ["agent-runs"] });
                setActiveRunId(null);
              }}
            />
          ) : (
            <EmptyState
              icon={<Sparkles className="h-6 w-6" />}
              title="Automate repetitive applications."
              description="Select an agent and click Run to start. Live progress will appear here."
              action={
                <LiquidGlassButton
                  tone="primary"
                  disabled={runMutation.isPending}
                  onClick={() => runMutation.mutate()}
                >
                  {runMutation.isPending ? "Running…" : "Start run"}
                </LiquidGlassButton>
              }
            />
          )}
        </div>
      </motion.section>

      <motion.aside variants={fadeUp} className="space-y-3">
        {/* BUG 19: dynamic context sidebar */}
        <div className="text-sm text-muted-foreground">Context</div>
        <div className="rounded-3xl border border-border bg-card/40 p-4 text-sm">
          <div className="text-xs text-muted-foreground">Resume</div>
          <div className="mt-1">{primaryResume?.filename ?? "No resume uploaded"}</div>
          <div className="mt-3 text-xs text-muted-foreground">Model</div>
          <div className="mt-1">{activeModel?.model_name ?? activeModel?.provider ?? "—"}</div>
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
              startedAt={relativeTime(run.started_at)}
            />
          ))
        )}

        {/* BUG 7: wire approval callbacks with actual run_id — only show if NOT the same as activeRunId to avoid duplicates */}
        {awaitingRun && awaitingRun.id !== activeRunId && (
          <AgentStatusStream
            runId={awaitingRun.id}
            onApprove={() => qc.invalidateQueries({ queryKey: ["agent-runs"] })}
            onCancel={() => qc.invalidateQueries({ queryKey: ["agent-runs"] })}
          />
        )}
      </motion.aside>
    </motion.div>
  );
}
