"use client";

import { useQuery } from "@tanstack/react-query";
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
    created_at: string | null;
  }>;
}

const JOBS = [
  { id: "1", company: "Acme Co", role: "Frontend Engineer", matchPercent: 92, location: "Remote" },
  { id: "2", company: "BetaCorp", role: "Full-stack Developer", matchPercent: 87, location: "Bangalore" },
  { id: "3", company: "Gamma", role: "Junior SDE", matchPercent: 81, location: "Hyderabad" },
];

export default function DashboardPage() {
  const { data: stats, isLoading } = useQuery<DashboardStats>({
    queryKey: ["dashboard-stats"],
    queryFn: async () => {
      const { data } = await apiClient.get("/users/me/stats");
      return data as DashboardStats;
    },
  });

  const metrics = [
    {
      label: "Applications",
      value: isLoading ? "—" : (stats?.applications_count ?? 0),
      trend: { delta: "", direction: "up" as const },
      icon: <Briefcase className="h-4 w-4" />,
    },
    {
      label: "Interviews",
      value: isLoading ? "—" : (stats?.interviews_count ?? 0),
      trend: { delta: "", direction: "up" as const },
      icon: <Calendar className="h-4 w-4" />,
    },
    {
      label: "Avg match",
      value: isLoading ? "—" : `${Math.round(stats?.avg_match_score ?? 0)}%`,
      trend: { delta: "", direction: "up" as const },
      icon: <Target className="h-4 w-4" />,
    },
    {
      label: "Follow-ups due",
      value: isLoading ? "—" : (stats?.followups_due ?? 0),
      icon: <Bell className="h-4 w-4" />,
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
        <ResumeScoreCard atsScore={78} keywordCoverage={64} missingKeywords={["TypeScript", "AWS", "Docker", "CI/CD"]} />
        <JobMatchCard jobs={JOBS} />
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
                startedAt={run.created_at ? new Date(run.created_at).toLocaleString() : ""}
              />
            ))
          ) : (
            <AgentStatusCard agentName="No recent runs" status="succeeded" latestMessage="" startedAt="" />
          )}
        </div>
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">Pending approvals</div>
          <ApprovalCard
            title="Send follow-up to Acme recruiter"
            summary="Subject: Following up on Frontend Engineer application — drafted in plain, friendly tone."
            onApprove={() => {}}
            onReject={() => {}}
          />
        </div>
      </motion.div>
    </motion.div>
  );
}
