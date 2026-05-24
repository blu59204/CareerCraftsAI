"use client";

import { motion } from "motion/react";
import { Briefcase, Calendar, Target, Bell } from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { MetricCard } from "@/components/ui/MetricCard";
import { ResumeScoreCard } from "@/components/ui/ResumeScoreCard";
import { JobMatchCard } from "@/components/ui/JobMatchCard";
import { AgentStatusCard } from "@/components/agents/AgentStatusCard";
import { ApprovalCard } from "@/components/agents/ApprovalCard";

// TODO Phase 4: replace mock data with TanStack Query hooks that call apiClient.
const METRICS = [
  { label: "Applications", value: 24, trend: { delta: "+4 this week", direction: "up" as const }, icon: <Briefcase className="h-4 w-4" /> },
  { label: "Interviews", value: 3, trend: { delta: "+1 this week", direction: "up" as const }, icon: <Calendar className="h-4 w-4" /> },
  { label: "Avg match", value: "78%", trend: { delta: "+5%", direction: "up" as const }, icon: <Target className="h-4 w-4" /> },
  { label: "Follow-ups due", value: 5, icon: <Bell className="h-4 w-4" /> },
];

const JOBS = [
  { id: "1", company: "Acme Co", role: "Frontend Engineer", matchPercent: 92, location: "Remote" },
  { id: "2", company: "BetaCorp", role: "Full-stack Developer", matchPercent: 87, location: "Bangalore" },
  { id: "3", company: "Gamma", role: "Junior SDE", matchPercent: 81, location: "Hyderabad" },
];

export default function DashboardPage() {
  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      <motion.div variants={fadeUp}>
        <div className="text-sm text-muted-foreground">{new Date().toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" })}</div>
        <h1 className="mt-1 text-3xl font-medium">Welcome back.</h1>
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        {METRICS.map((m) => (
          <MetricCard key={m.label} {...m} />
        ))}
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 lg:grid-cols-2">
        <ResumeScoreCard atsScore={78} keywordCoverage={64} missingKeywords={["TypeScript", "AWS", "Docker", "CI/CD"]} />
        <JobMatchCard jobs={JOBS} />
      </motion.div>

      <motion.div variants={fadeUp} className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-4">
          <div className="text-sm text-muted-foreground">Recent agent runs</div>
          <AgentStatusCard agentName="Resume Agent" status="succeeded" latestMessage="Tailored resume for BetaCorp Full-stack role." startedAt="2 min ago" />
          <AgentStatusCard agentName="Job Search Agent" status="running" latestMessage="Scanning LinkedIn — 12 leads so far." startedAt="just now" />
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
