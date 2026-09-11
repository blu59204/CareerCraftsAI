"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  Briefcase,
  Calendar,
  TrendingUp,
  Bell,
  Target,
  Search,
  FileText,
  Mic,
  Building2,
} from "lucide-react";
import { ResumeScoreCard } from "@/components/ui/ResumeScoreCard";
import { JobMatchCard } from "@/components/ui/JobMatchCard";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";
import { Button } from "@/components/ui/button";
import { apiClient } from "@/lib/api";
import { useAgentStore } from "@/store/agentStore";
import { useRouter } from "next/navigation";

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

function MetricCard({
  label,
  value,
  icon,
  progress,
  loading,
  trend,
}: {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  progress: number;
  loading?: boolean;
  trend?: "up" | "down" | "neutral";
}) {
  const pct = Math.max(0, Math.min(100, progress));

  if (loading) {
    return (
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="h-3 w-16 rounded bg-muted animate-pulse" />
        <div className="mt-3 h-8 w-12 rounded bg-muted animate-pulse" />
      </div>
    );
  }

  return (
    <div className="group rounded-xl border border-border bg-card p-5 transition-colors hover:border-primary/20">
      <div className="flex items-center justify-between">
        <p className="text-xs uppercase tracking-wider text-muted-foreground">{label}</p>
        <span className="text-muted-foreground/60">{icon}</span>
      </div>
      <div className="mt-2 flex items-baseline gap-2">
        <p className="text-3xl font-semibold tracking-tight text-foreground">{value}</p>
        {trend && trend !== "neutral" && (
          <span className={`text-xs ${trend === "up" ? "text-green-400" : "text-red-400"}`}>
            {trend === "up" ? "↑" : "↓"}
          </span>
        )}
      </div>
      <div className="mt-3 h-1.5 w-full rounded-full bg-muted">
        <div
          className="h-full rounded-full bg-primary transition-all duration-700"
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

const quickActions = [
  { label: "Search Jobs", icon: Search, taskType: "job_search", ctx: { query: "", location: "Remote" } },
  { label: "Optimize Resume", icon: FileText, taskType: "resume_optimize", ctx: {} },
  { label: "Mock Interview", icon: Mic, taskType: "interview_coach", ctx: { role: "Software Engineer" } },
  { label: "Research Company", icon: Building2, taskType: "company_research", ctx: {} },
];

export default function DashboardPage() {
  const qc = useQueryClient();
  const router = useRouter();
  const initRun = useAgentStore((s) => s.initRun);
  const setActiveRun = useAgentStore((s) => s.setActiveRun);

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
      return ((Array.isArray(data) ? data : data.runs ?? []) as PendingApproval[]).filter((r) => r.status === "awaiting_approval");
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

  const triggerAgent = async (taskType: string, ctx: Record<string, unknown>) => {
    const { data } = await apiClient.post("/agents/run", { task_type: taskType, context: ctx });
    const runId = (data as { run_id: string }).run_id;
    initRun(runId);
    setActiveRun(runId);
    router.push("/agents");
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
      className="space-y-6"
    >
      {/* Header */}
      <div className="flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-4xl font-semibold tracking-tight text-foreground">Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            {new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}
          </p>
        </div>
      </div>

      {/* Pending Approvals — HIGH VISIBILITY */}
      {pendingApprovals.length > 0 && (
        <motion.div
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          className="space-y-3 rounded-xl border border-primary/30 bg-primary/5 p-5"
        >
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-primary animate-pulse" />
            <span className="text-sm font-medium text-primary">
              {pendingApprovals.length} action{pendingApprovals.length > 1 ? "s" : ""} require approval
            </span>
          </div>
          <div className="space-y-3">
            {pendingApprovals.map((run) => (
              <ApprovalCard
                key={run.id}
                title={`${run.agent_type.replace(/_/g, " ")} action pending`}
                summary={run.output?.subject ?? run.output?.type ?? "Review required"}
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

      {/* Quick Actions */}
      <div className="flex flex-wrap gap-2">
        {quickActions.map((action) => (
          <Button
            key={action.label}
            variant="outline"
            size="sm"
            onClick={() => triggerAgent(action.taskType, action.ctx)}
            className="gap-2 text-xs"
          >
            <action.icon className="h-3.5 w-3.5" />
            {action.label}
          </Button>
        ))}
      </div>

      {/* KPI Cards */}
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <MetricCard
          label="Applications"
          value={isLoading ? "—" : (stats?.applications_count ?? 0)}
          icon={<Briefcase className="h-4 w-4" />}
          progress={Math.min(100, (stats?.applications_count ?? 0) * 5)}
          loading={isLoading}
        />
        <MetricCard
          label="Interviews"
          value={isLoading ? "—" : (stats?.interviews_count ?? 0)}
          icon={<Calendar className="h-4 w-4" />}
          progress={Math.min(100, (stats?.interviews_count ?? 0) * 10)}
          loading={isLoading}
        />
        <MetricCard
          label="Avg Match"
          value={isLoading ? "—" : `${Math.round(stats?.avg_match_score ?? 0)}%`}
          icon={<Target className="h-4 w-4" />}
          progress={stats?.avg_match_score ?? 0}
          loading={isLoading}
        />
        <MetricCard
          label="Follow-ups Due"
          value={isLoading ? "—" : (stats?.followups_due ?? 0)}
          icon={<Bell className="h-4 w-4" />}
          progress={Math.min(100, (stats?.followups_due ?? 0) * 20)}
          loading={isLoading}
          trend={(stats?.followups_due ?? 0) > 0 ? "up" : "neutral"}
        />
      </div>

      {/* Resume + Job Matches */}
      <div className="grid gap-6 lg:grid-cols-2">
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
      <div className="rounded-xl border border-border bg-card p-5">
        <div className="mb-4 flex items-center gap-2">
          <TrendingUp className="h-4 w-4 text-muted-foreground" />
          <span className="text-sm font-medium text-foreground">Recent Agent Runs</span>
        </div>
        {isLoading ? (
          <div className="h-20 rounded-lg bg-muted animate-pulse" />
        ) : stats?.recent_agent_runs?.length ? (
          <div className="space-y-2">
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
          <div className="rounded-lg border border-dashed border-border p-6 text-center text-sm text-muted-foreground">
            No recent agent activity. Run your first agent to see results here.
          </div>
        )}
      </div>
    </motion.div>
  );
}
