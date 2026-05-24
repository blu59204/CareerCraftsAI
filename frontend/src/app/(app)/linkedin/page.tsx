"use client";

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
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
  Loader2,
  Sparkles,
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface AgentRun {
  id: string;
  agent_type: string;
  status: string;
  output: Record<string, unknown> | null;
  duration_ms: number | null;
  created_at: string;
}

interface ProfileSection {
  name: string;
  score: number;
  excerpt: string;
  note: string;
  status: "strong" | "good" | "needs-work";
}

interface Recommendation {
  id: string;
  priority: "High" | "Medium";
  text: string;
}

const DEFAULT_SECTIONS: ProfileSection[] = [
  { name: "Headline", score: 0, excerpt: "Run analysis to score", note: "Pending analysis", status: "needs-work" },
  { name: "Summary / About", score: 0, excerpt: "Run analysis to score", note: "Pending analysis", status: "needs-work" },
  { name: "Experience", score: 0, excerpt: "Run analysis to score", note: "Pending analysis", status: "needs-work" },
  { name: "Skills", score: 0, excerpt: "Run analysis to score", note: "Pending analysis", status: "needs-work" },
  { name: "Education", score: 0, excerpt: "Run analysis to score", note: "Pending analysis", status: "needs-work" },
  { name: "Recommendations", score: 0, excerpt: "Run analysis to score", note: "Pending analysis", status: "needs-work" },
];

function ScoreBar({ score }: { score: number }) {
  const color =
    score >= 85 ? "bg-green-500" : score >= 70 ? "bg-amber-500" : "bg-red-400";

  return (
    <div className="flex items-center gap-2">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <div className={cn("h-full rounded-full transition-all", color)} style={{ width: `${score}%` }} />
      </div>
      <span className="w-10 text-right text-xs font-medium text-foreground">
        {score > 0 ? `${score}%` : "—"}
      </span>
    </div>
  );
}

function StatusChip({ status }: { status: ProfileSection["status"] }) {
  if (status === "strong")
    return (
      <span className="flex items-center gap-1 rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-700">
        <CheckCircle className="h-3 w-3" />Strong
      </span>
    );
  if (status === "good")
    return <span className="rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-700">Good</span>;
  return (
    <span className="flex items-center gap-1 rounded-full bg-amber-100 px-2.5 py-0.5 text-xs font-medium text-amber-700">
      <AlertCircle className="h-3 w-3" />Improve
    </span>
  );
}

function parseOutput(run: AgentRun | null): {
  sections: ProfileSection[];
  recommendations: Recommendation[];
  overallScore: number | null;
} {
  if (!run?.output) return { sections: DEFAULT_SECTIONS, recommendations: [], overallScore: null };

  const out = run.output as Record<string, unknown>;

  const sections: ProfileSection[] = Array.isArray(out.sections)
    ? (out.sections as ProfileSection[])
    : DEFAULT_SECTIONS;

  const recommendations: Recommendation[] = Array.isArray(out.recommendations)
    ? (out.recommendations as Recommendation[])
    : typeof out.suggestions === "string"
    ? out.suggestions
        .split("\n")
        .filter(Boolean)
        .slice(0, 5)
        .map((text, i) => ({ id: String(i + 1), priority: i < 3 ? "High" : "Medium", text } as Recommendation))
    : [];

  const overallScore =
    typeof out.overall_score === "number"
      ? out.overall_score
      : sections.length > 0 && sections[0].score > 0
      ? Math.round(sections.reduce((s, sec) => s + sec.score, 0) / sections.length)
      : null;

  return { sections, recommendations, overallScore };
}

export default function LinkedInPage() {
  const qc = useQueryClient();

  const { data: lastRun, isLoading } = useQuery<AgentRun | null>({
    queryKey: ["linkedin-run"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=50");
      const runs = (data as AgentRun[]).filter((r) => r.agent_type === "linkedin_optimize");
      return runs[0] ?? null;
    },
  });

  const analysisMutation = useMutation({
    mutationFn: () =>
      apiClient.post("/agents/run", { task_type: "linkedin_optimize", context: {} }),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ["linkedin-run"] }), 5000);
    },
  });

  const { sections, recommendations, overallScore } = parseOutput(lastRun ?? null);

  const isRunning =
    analysisMutation.isPending ||
    (lastRun?.status === "running" && !analysisMutation.isSuccess);

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-start justify-between">
        <div>
          <div className="text-sm text-muted-foreground">LinkedIn Agent</div>
          <h1 className="mt-1 text-3xl font-medium">Optimize your presence.</h1>
        </div>
        <div className="flex gap-2">
          <LiquidGlassButton
            tone="primary"
            size="sm"
            onClick={() => analysisMutation.mutate()}
            disabled={isRunning}
          >
            {isRunning ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Linkedin className="h-4 w-4" />
            )}
            {isRunning ? "Analyzing…" : "Run Analysis"}
          </LiquidGlassButton>
          <LiquidGlassButton tone="ghost" size="sm">
            Edit Profile
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* Last run banner */}
      {!isLoading && lastRun && (
        <motion.div variants={fadeUp} className="flex items-center gap-3 rounded-2xl border border-border bg-card/40 px-5 py-3 text-sm text-muted-foreground">
          <Sparkles className="h-4 w-4 shrink-0 text-primary" />
          Last analysis: {lastRun.status === "completed" ? "completed" : lastRun.status}
          {lastRun.duration_ms && ` · ${(lastRun.duration_ms / 1000).toFixed(1)}s`}
        </motion.div>
      )}

      {/* No analysis yet — CTA */}
      {!isLoading && !lastRun && (
        <motion.div variants={fadeUp} className="rounded-3xl border border-dashed border-border bg-card/40 p-8 text-center">
          <Linkedin className="mx-auto h-8 w-8 text-muted-foreground/40" />
          <p className="mt-3 text-sm font-medium">No analysis yet</p>
          <p className="mt-1 text-xs text-muted-foreground">
            Run the LinkedIn Agent to score your profile sections and get AI recommendations.
          </p>
          <LiquidGlassButton
            tone="primary"
            size="sm"
            className="mt-4"
            onClick={() => analysisMutation.mutate()}
            disabled={isRunning}
          >
            <Zap className="h-4 w-4" />
            Run Analysis
          </LiquidGlassButton>
        </motion.div>
      )}

      {/* Overall score metric */}
      {overallScore !== null && (
        <motion.div variants={fadeUp} className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-3xl border border-border bg-card/60 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Profile Score</span>
              <Zap className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="mt-2 text-2xl font-semibold">{overallScore}/100</p>
            <p className="mt-0.5 text-xs text-green-600">From last analysis</p>
          </div>
          <div className="rounded-3xl border border-border bg-card/60 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Profile Views</span>
              <Eye className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="mt-2 text-2xl font-semibold text-muted-foreground">—</p>
            <p className="mt-0.5 text-xs text-muted-foreground">LinkedIn OAuth required</p>
          </div>
          <div className="rounded-3xl border border-border bg-card/60 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Connections</span>
              <Users className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="mt-2 text-2xl font-semibold text-muted-foreground">—</p>
            <p className="mt-0.5 text-xs text-muted-foreground">LinkedIn OAuth required</p>
          </div>
          <div className="rounded-3xl border border-border bg-card/60 p-5">
            <div className="flex items-center justify-between">
              <span className="text-xs font-medium text-muted-foreground">Recommendations</span>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </div>
            <p className="mt-2 text-2xl font-semibold">{recommendations.length}</p>
            <p className="mt-0.5 text-xs text-muted-foreground">Action items</p>
          </div>
        </motion.div>
      )}

      {/* Loading skeletons */}
      {isLoading && (
        <motion.div variants={fadeUp} className="space-y-4">
          <div className="h-32 shimmer rounded-3xl" />
          <div className="h-64 shimmer rounded-3xl" />
        </motion.div>
      )}

      {/* Two-column layout — only show when we have a run */}
      {!isLoading && lastRun && (
        <motion.div variants={fadeUp} className="flex gap-4">
          {/* Left: Profile sections */}
          <div className="flex-[3] space-y-4">
            <div className="rounded-3xl border border-border bg-card/60 p-6">
              <h2 className="mb-4 text-sm font-semibold text-foreground">Profile Sections</h2>
              <div className="divide-y divide-border">
                {sections.map((section) => (
                  <div key={section.name} className="flex items-center gap-4 py-3 first:pt-0 last:pb-0">
                    <div className="w-40 shrink-0">
                      <p className="text-sm font-medium text-foreground">{section.name}</p>
                      <p className="mt-0.5 truncate text-xs text-muted-foreground">{section.excerpt}</p>
                    </div>
                    <div className="flex-1">
                      <ScoreBar score={section.score} />
                      <p className="mt-1 text-xs text-muted-foreground">{section.note}</p>
                    </div>
                    <div className="shrink-0">
                      <StatusChip status={section.status} />
                    </div>
                    <button className="shrink-0 rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/10 hover:text-primary">
                      Optimize
                    </button>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Right: AI Recommendations */}
          <div className="flex-[2]">
            <div className="rounded-3xl border border-border bg-card/60 p-6">
              <h2 className="mb-4 text-sm font-semibold text-foreground">AI Recommendations</h2>
              {recommendations.length === 0 ? (
                <p className="text-sm text-muted-foreground">
                  No recommendations yet. Run analysis to get personalized suggestions.
                </p>
              ) : (
                <div className="space-y-3">
                  {recommendations.map((rec, i) => (
                    <div key={rec.id} className="flex items-start gap-3 rounded-2xl border border-border bg-background/50 p-3">
                      <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                        {i + 1}
                      </span>
                      <div className="min-w-0 flex-1">
                        <span className={cn(
                          "rounded-full px-2 py-0.5 text-xs font-medium",
                          rec.priority === "High" ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                        )}>
                          {rec.priority}
                        </span>
                        <p className="mt-1.5 text-xs leading-relaxed text-foreground">{rec.text}</p>
                        <button className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline">
                          Apply <ChevronRight className="h-3 w-3" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </motion.div>
      )}

      {/* Bottom banner */}
      <motion.div variants={fadeUp}>
        <div className="flex items-center gap-3 rounded-2xl border border-border bg-card/60 px-5 py-4">
          <Zap className="h-4 w-4 shrink-0 text-primary" />
          <p className="text-sm text-muted-foreground">
            The LinkedIn Agent analyzes your profile against target roles and suggests keyword improvements.
          </p>
        </div>
      </motion.div>
    </motion.div>
  );
}
