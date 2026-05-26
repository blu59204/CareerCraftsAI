"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { motion } from "motion/react";
import { Briefcase, Calendar, Target, Bell } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { MetricCard } from "@/components/ui/MetricCard";
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
  output: { type?: string; subject?: string; body?: string } | null;
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
      return (data as PendingApproval[]).filter((r: { status?: string }) => r.status === "awaiting_approval");
    },
    refetchInterval: 10000,
  });

  const { data: resumeData } = useQuery<{ ats_score: number | null; keyword_score: number | null; missing_keywords: string[] }>({
    queryKey: ["dashboard-ats"],
    queryFn: async () => {
      const { data } = await apiClient.get("/rag/documents?doc_type=resume");
      const docs = data as Array<{ is_primary: boolean; ats_score: number | null; ats_data: { keyword_score?: number; missing_keywords?: string[] } | null }>;
      const primary = docs?.find((d) => d.is_primary) ?? docs?.[0];
      return {
        ats_score: primary?.ats_score ?? null,
        keyword_score: primary?.ats_data?.keyword_score ?? null,
        missing_keywords: primary?.ats_data?.missing_keywords ?? [],
      };
    },
  });

  const metrics = [
    {
      label: "Applications",
      value: isLoading ? "—" : (stats?.applications_count ?? 0),
      icon: <Briefcase className="h-4 w-4" />,
      href: "/applications",
    },
    {
      label: "Interviews",
      value: isLoading ? "—" : (stats?.interviews_count ?? 0),
      icon: <Calendar className="h-4 w-4" />,
      href: "/applications",
    },
    {
      label: "Avg match",
      value: isLoading ? "—" : `${Math.round(stats?.avg_match_score ?? 0)}%`,
      icon: <Target className="h-4 w-4" />,
      href: "/jobs",
    },
    {
      label: "Follow-ups due",
      value: isLoading ? "—" : (stats?.followups_due ?? 0),
      icon: <Bell className="h-4 w-4" />,
      href: "/email",
    },
  ];

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</div>
        <h1 className="mt-1 text-3xl font-medium">Welcome back.</h1>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {isLoading
          ? Array.from({ length: 4 }).map((_, i) => (
              <div key={i} className="h-28 rounded-2xl bg-muted animate-pulse" />
            ))
          : metrics.map((m) => <MetricCard key={m.label} {...m} />)}
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 lg:grid-cols-2">
        <ResumeScoreCard atsScore={resumeData?.ats_score ?? 0} keywordCoverage={resumeData?.keyword_score ?? 0} missingKeywords={resumeData?.missing_keywords ?? ["TypeScript", "AWS", "Docker", "CI/CD"]} />
        <JobMatchCard jobs={jobMatches.map((j) => ({ id: j.id, company: j.company, role: j.role, matchPercent: j.match_score, location: j.location }))} />
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">Recent agent runs</div>
          {isLoading ? (
            <div className="h-20 rounded-2xl bg-muted animate-pulse" />
          ) : stats?.recent_agent_runs.length ? (
            stats.recent_agent_runs.map((run) => (
              <AgentStatusCard
                key={run.id}
                agentName={run.agent_type}
                status={run.status as "running" | "succeeded" | "failed"}
                latestMessage=""
                startedAt={run.started_at ? new Date(run.started_at).toLocaleString() : ""}
              />
            ))
          ) : (
            <AgentStatusCard agentName="No recent runs" status="succeeded" latestMessage="" startedAt="" />
          )}
        </div>
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">Pending approvals</div>
          {pendingApprovals.length === 0 ? (
            <div className="rounded-2xl border border-dashed border-border p-4 text-center text-sm text-muted-foreground">
              No pending approvals.
            </div>
          ) : (
            pendingApprovals.map((run) => (
              <ApprovalCard
                key={run.id}
                title={`${run.agent_type.replace(/_/g, " ")} action pending`}
                summary={run.output?.subject ?? run.output?.type ?? "Review required before proceeding."}
                onApprove={async () => {
                  await apiClient.post(`/agents/${run.id}/approve`, { approved: true });
                  qc.invalidateQueries({ queryKey: ["pending-approvals"] });
                }}
                onReject={async () => {
                  await apiClient.post(`/agents/${run.id}/approve`, { approved: false });
                  qc.invalidateQueries({ queryKey: ["pending-approvals"] });
                }}
              />
            ))
          )}
        </div>
      </motion.div>
    </motion.div>
  );
}
