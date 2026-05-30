"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Briefcase, Calendar, Target, Bell, TrendingUp } from "lucide-react";
import { ResumeScoreCard } from "@/components/ui/ResumeScoreCard";
import { JobMatchCard } from "@/components/ui/JobMatchCard";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";
import { apiClient } from "@/lib/api";

interface DashboardStats {
  applications_count: number;
  interviews_count: number;
  avg_match_score: number;
  followups_due: number;
  recent_agent_runs: Array<{
    id: string;
    agent_type: string;
    status: string;
    started_at: string | null;
  }>;
}

interface JobApplication {
  id: string;
  company: string;
  role: string;
  match_score: number;
  location: string;
}

interface PendingApproval {
  id: string;
  agent_type: string;
  status: string;
  output: { type?: string; subject?: string; body?: string } | null;
}

function MetricOrb({
  label,
  value,
  icon,
  progress,
  loading,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  progress: number;
  loading?: boolean;
}) {
  const R = 26;
  const C = 2 * Math.PI * R;
  const pct = Math.max(0, Math.min(100, progress));

  if (loading) {
    return (
      <div className="glass-panel flex items-center justify-between gap-4 rounded-2xl p-5">
        <div className="min-w-0 flex-1">
          <div className="h-3 w-16 rounded bg-muted animate-pulse" />
          <div className="mt-2 h-8 w-12 rounded bg-muted animate-pulse" />
        </div>
        <div className="orbit-loader !h-16 !w-16" />
      </div>
    );
  }

  return (
    <div className="glass-panel depth-hover flex items-center justify-between gap-4 rounded-2xl p-5">
      <div className="min-w-0 flex-1">
        <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
        <p className="mt-1 font-display text-3xl font-semibold text-foreground">{value}</p>
      </div>
      <div className="relative grid h-16 w-16 shrink-0 place-items-center">
        <svg width="64" height="64" viewBox="0 0 64 64" className="-rotate-90">
          <circle cx="32" cy="32" r={R} fill="none" stroke="hsl(var(--border))" strokeWidth="4" />
          <circle
            cx="32"
            cy="32"
            r={R}
            fill="none"
            stroke="hsl(var(--primary))"
            strokeWidth="4"
            strokeLinecap="round"
            strokeDasharray={C}
            strokeDashoffset={C - (pct / 100) * C}
            style={{
              transition: "stroke-dashoffset 1s cubic-bezier(0.16, 1, 0.3, 1)",
              filter: "drop-shadow(0 0 6px hsl(var(--primary) / 0.6))",
            }}
          />
        </svg>
        <span className="absolute grid place-items-center text-primary">{icon}</span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const qc = useQueryClient();
  const { data: stats, isLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/stats");
      return data as DashboardStats;
    },
  });

  const { data: jobMatches = [] } = useQuery<JobApplication[]>({
    queryKey: ["dashboard-jobs"],
    queryFn: async () => {
      const { data } = await apiClient.get("/jobs/applications?status=saved&limit=3");
      return data;
    },
  });

  const { data: pendingApprovals = [] } = useQuery<PendingApproval[]>({
    queryKey: ["pending-approvals"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=20");
      return (data as PendingApproval[]).filter((r) => r.status === "awaiting_approval");
    },
    refetchInterval: 10000,
  });

  const { data: resumeData } = useQuery<{
    ats_score: number | null;
    keyword_score: number | null;
    missing_keywords: string[];
  }>({
    queryKey: ["dashboard-ats"],
    queryFn: async () => {
      const { data } = await apiClient.get("/rag/documents?doc_type=resume");
      const docs = data as Array<{
        is_primary: boolean;
        ats_score: number | null;
        ats_data: { keyword_score?: number; missing_keywords?: string[] } | null;
      }>;
      const primary = docs?.find((d) => d.is_primary) ?? docs?.[0];
      return {
        ats_score: primary?.ats_score ?? null,
        keyword_score: primary?.ats_data?.keyword_score ?? null,
        missing_keywords: primary?.ats_data?.missing_keywords ?? [],
      };
    },
  });

  const appCount = stats?.applications_count ?? 0;
  const intCount = stats?.interviews_count ?? 0;
  const avgMatch = stats?.avg_match_score ?? 0;
  const followups = stats?.followups_due ?? 0;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex items-end justify-between gap-4">
        <div>
          <div className="flex items-center gap-2">
            <span className="signal-dot h-1.5 w-1.5 rounded-full bg-accent" />
            <span className="text-xs uppercase tracking-wider text-muted-foreground">
              Dashboard UI
            </span>
          </div>
          <h1 className="mt-2 font-display text-4xl font-semibold text-foreground">
            Welcome back.
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {new Date().toLocaleDateString("en-US", {
              weekday: "long",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
      </div>

      {/* Metric Orbs */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricOrb
          label="Applications"
          value={isLoading ? "—" : appCount}
          icon={<Briefcase className="h-5 w-5" />}
          progress={Math.min(100, appCount * 5)}
          loading={isLoading}
        />
        <MetricOrb
          label="Interviews"
          value={isLoading ? "—" : intCount}
          icon={<Calendar className="h-5 w-5" />}
          progress={Math.min(100, intCount * 10)}
          loading={isLoading}
        />
        <MetricOrb
          label="Avg Match"
          value={isLoading ? "—" : `${Math.round(avgMatch)}%`}
          icon={<Target className="h-5 w-5" />}
          progress={avgMatch}
          loading={isLoading}
        />
        <MetricOrb
          label="Follow-ups"
          value={isLoading ? "—" : followups}
          icon={<Bell className="h-5 w-5" />}
          progress={Math.min(100, followups * 20)}
          loading={isLoading}
        />
      </div>

      {/* Pending Approvals — HIGH VISIBILITY */}
      {pendingApprovals.length > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ delay: 0.2 }}
          className="glass-panel-strong glow-primary space-y-3 rounded-2xl border border-primary/40 p-5"
        >
          <div className="flex items-center gap-2">
            <span className="signal-dot h-2 w-2 rounded-full bg-primary" />
            <span className="text-sm font-medium uppercase tracking-wider text-primary">
              Human Gate — {pendingApprovals.length} action{pendingApprovals.length > 1 ? "s" : ""}{" "}
              require approval
            </span>
          </div>
          <div className="space-y-3">
            {pendingApprovals.map((run) => (
              <ApprovalCard
                key={run.id}
                title={`${run.agent_type.replace(/_/g, " ")} action pending`}
                summary={
                  run.output?.subject ?? run.output?.type ?? "Review required before proceeding."
                }
                onApprove={async () => {
                  await apiClient.post(`/agents/${run.id}/approve`, { approved: true });
                  qc.invalidateQueries({ queryKey: ["pending-approvals"] });
                }}
                onReject={async () => {
                  await apiClient.post(`/agents/${run.id}/approve`, { approved: false });
                  qc.invalidateQueries({ queryKey: ["pending-approvals"] });
                }}
              />
            ))}
          </div>
        </motion.div>
      )}

      {/* Resume + Job Matches */}
      <div className="grid gap-4 lg:grid-cols-2">
        <ResumeScoreCard
          atsScore={resumeData?.ats_score ?? 0}
          keywordCoverage={resumeData?.keyword_score ?? 0}
          missingKeywords={
            resumeData?.missing_keywords ?? ["TypeScript", "AWS", "Docker", "CI/CD"]
          }
        />
        <JobMatchCard
          jobs={jobMatches.map((j) => ({
            id: j.id,
            company: j.company,
            role: j.role,
            matchPercent: j.match_score,
            location: j.location,
          }))}
        />
      </div>

      {/* Recent Agent Runs */}
      <div className="glass-panel space-y-4 rounded-2xl p-5">
        <div className="flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-muted-foreground">Recent agent runs</span>
        </div>
        {isLoading ? (
          <div className="h-20 rounded-xl bg-muted animate-pulse" />
        ) : stats?.recent_agent_runs.length ? (
          <div className="space-y-3">
            {stats.recent_agent_runs.map((run) => (
              <AgentStatusCard
                key={run.id}
                agentName={run.agent_type}
                status={
                  run.status === "completed"
                    ? "succeeded"
                    : (run.status as "running" | "succeeded" | "failed" | "awaiting_approval")
                }
                latestMessage=""
                startedAt={run.started_at ? new Date(run.started_at).toLocaleString() : ""}
              />
            ))}
          </div>
        ) : (
          <div className="rounded-xl border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
            No recent runs.
          </div>
        )}
      </div>
    </motion.div>
  );
}
