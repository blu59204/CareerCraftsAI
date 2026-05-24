"use client";

import { motion } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { cn } from "@/lib/utils";
import {
  Linkedin,
  TrendingUp,
  Eye,
  Users,
  Zap,
  CheckCircle,
  AlertCircle,
  ChevronRight,
} from "lucide-react";

interface MetricItem {
  label: string;
  value: string;
  sub: string;
  icon: React.ReactNode;
  positive: boolean;
}

const METRICS: MetricItem[] = [
  {
    label: "Profile Score",
    value: "78/100",
    sub: "+5 this week",
    icon: <Zap className="h-4 w-4" />,
    positive: true,
  },
  {
    label: "Profile Views",
    value: "234",
    sub: "+12%",
    icon: <Eye className="h-4 w-4" />,
    positive: true,
  },
  {
    label: "Connection Requests",
    value: "8",
    sub: "pending",
    icon: <Users className="h-4 w-4" />,
    positive: true,
  },
  {
    label: "Keywords Matched",
    value: "23/40",
    sub: "17 gaps",
    icon: <TrendingUp className="h-4 w-4" />,
    positive: false,
  },
];

interface ProfileSection {
  name: string;
  score: number;
  excerpt: string;
  note: string;
  status: "strong" | "good" | "needs-work";
}

const SECTIONS: ProfileSection[] = [
  {
    name: "Headline",
    score: 85,
    excerpt: "Currently at XYZ | React Developer | …",
    note: "Strong but could be more targeted",
    status: "good",
  },
  {
    name: "Summary / About",
    score: 72,
    excerpt: "Passionate developer with 4 years…",
    note: "Needs more keywords",
    status: "needs-work",
  },
  {
    name: "Experience",
    score: 90,
    excerpt: "Senior Frontend Engineer at XYZ Corp",
    note: "Strong bullet points",
    status: "strong",
  },
  {
    name: "Skills",
    score: 65,
    excerpt: "React, JavaScript, CSS…",
    note: "Add 12 more relevant skills",
    status: "needs-work",
  },
  {
    name: "Education",
    score: 95,
    excerpt: "B.Tech Computer Science",
    note: "Complete",
    status: "strong",
  },
  {
    name: "Recommendations",
    score: 40,
    excerpt: "1 recommendation received",
    note: "Request 3+ recommendations",
    status: "needs-work",
  },
];

interface Recommendation {
  id: string;
  priority: "High" | "Medium";
  text: string;
}

const RECOMMENDATIONS: Recommendation[] = [
  {
    id: "1",
    priority: "High",
    text: "Add 'TypeScript' to skills — 8x more recruiter searches",
  },
  {
    id: "2",
    priority: "High",
    text: "Rewrite headline to include target role",
  },
  {
    id: "3",
    priority: "High",
    text: "Add project with GitHub link to featured section",
  },
  {
    id: "4",
    priority: "Medium",
    text: "Enable Open to Work (private to recruiters)",
  },
  {
    id: "5",
    priority: "Medium",
    text: "Post 1 article about your tech stack",
  },
];

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 85
      ? "bg-green-500"
      : score >= 70
      ? "bg-amber-500"
      : "bg-red-400";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <div
          className={cn("h-full rounded-full transition-all", color)}
          style={{ width: `${score}%` }}
        />
      </div>
      <span className="w-10 text-right text-xs font-medium text-foreground">
        {score}%
      </span>
    </div>
  );
}

function StatusChip({ status }: { status: ProfileSection["status"] }) {
  if (status === "strong") {
    return (
      <span className="flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
        <CheckCircle className="h-3 w-3" />
        Strong
      </span>
    );
  }
  if (status === "good") {
    return (
      <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">
        Good
      </span>
    );
  }
  return (
    <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
      <AlertCircle className="h-3 w-3" />
      Improve
    </span>
  );
}

export default function LinkedInPage() {
  return (
    <motion.div
      initial="hidden"
      animate="show"
      variants={stagger}
      className="space-y-8"
    >
      {/* Header */}
      <motion.div
        variants={fadeUp}
        className="flex items-start justify-between"
      >
        <div>
          <div className="text-sm text-muted-foreground">LinkedIn Agent</div>
          <h1 className="mt-1 text-3xl font-medium">Optimize your presence.</h1>
        </div>
        <div className="flex gap-2">
          <LiquidGlassButton tone="primary" size="sm">
            <Linkedin className="h-4 w-4" />
            Run Analysis
          </LiquidGlassButton>
          <LiquidGlassButton tone="ghost" size="sm">
            Edit Profile
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* Metric row */}
      <motion.div
        variants={fadeUp}
        className="grid gap-4 md:grid-cols-2 lg:grid-cols-4"
      >
        {METRICS.map((m) => (
          <div
            key={m.label}
            className="rounded-3xl border border-border bg-card/60 p-5"
          >
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">
                {m.label}
              </span>
              <span className="text-muted-foreground">{m.icon}</span>
            </div>
            <p className="mt-2 text-2xl font-semibold text-foreground">
              {m.value}
            </p>
            <p
              className={cn(
                "mt-0.5 text-xs",
                m.positive ? "text-green-600" : "text-amber-600"
              )}
            >
              {m.sub}
            </p>
          </div>
        ))}
      </motion.div>

      {/* Two-column layout */}
      <motion.div variants={fadeUp} className="flex gap-4">
        {/* Left: Profile sections (60%) */}
        <div className="flex-[3] space-y-4">
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <h2 className="mb-4 text-sm font-semibold text-foreground">
              Profile Sections
            </h2>
            <div className="divide-y divide-border">
              {SECTIONS.map((section) => (
                <div
                  key={section.name}
                  className="flex items-center gap-4 py-3 first:pt-0 last:pb-0"
                >
                  {/* Name */}
                  <div className="w-40 shrink-0">
                    <p className="text-sm font-medium text-foreground">
                      {section.name}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-muted-foreground">
                      {section.excerpt}
                    </p>
                  </div>

                  {/* Score bar */}
                  <div className="flex-1">
                    <ScoreBar score={section.score} />
                    <p className="mt-1 text-xs text-muted-foreground">
                      {section.note}
                    </p>
                  </div>

                  {/* Status chip */}
                  <div className="shrink-0">
                    <StatusChip status={section.status} />
                  </div>

                  {/* Optimize button */}
                  <button className="shrink-0 rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/10 hover:text-primary">
                    Optimize
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right: AI Recommendations (40%) */}
        <div className="flex-[2]">
          <div className="rounded-3xl border border-border bg-card/60 p-6">
            <h2 className="mb-4 text-sm font-semibold text-foreground">
              AI Recommendations
            </h2>
            <div className="space-y-3">
              {RECOMMENDATIONS.map((rec, i) => (
                <div
                  key={rec.id}
                  className="flex items-start gap-3 rounded-2xl border border-border bg-background/50 p-3"
                >
                  {/* Number */}
                  <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                    {i + 1}
                  </span>

                  <div className="min-w-0 flex-1">
                    {/* Priority badge */}
                    <span
                      className={cn(
                        "rounded-full px-2 py-0.5 text-xs font-medium",
                        rec.priority === "High"
                          ? "bg-red-100 text-red-700"
                          : "bg-amber-100 text-amber-700"
                      )}
                    >
                      {rec.priority}
                    </span>
                    <p className="mt-1.5 text-xs leading-relaxed text-foreground">
                      {rec.text}
                    </p>
                    <button className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                      Apply <ChevronRight className="h-3 w-3" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </motion.div>

      {/* Bottom banner */}
      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 px-5 py-4">
          <Zap className="h-4 w-4 shrink-0 text-primary" />
          <p className="text-sm text-muted-foreground">
            The LinkedIn Agent monitors your profile weekly and suggests improvements.
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
