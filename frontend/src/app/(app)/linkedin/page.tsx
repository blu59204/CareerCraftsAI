"use client";

import Link from "next/link";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
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
  X,
  Save,
} from "lucide-react";
import { apiClient } from "@/lib/api";

interface AgentRun {
  id: string;
  agent_type: string;
  status: string;
  output: Record<string, unknown> | null;
  duration_ms: number | null;
  started_at: string;
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

interface ProfileForm {
  headline: string;
  summary: string;
  location: string;
  website: string;
}

function EditProfileModal({ onClose }: { onClose: () => void }) {
  const [form, setForm] = useState<ProfileForm>({
    headline: "Full-stack Developer | React · Python · FastAPI",
    summary: "Building scalable web applications with modern stacks. Passionate about clean code and great user experiences.",
    location: "Bangalore, India",
    website: "",
  });
  const set = (k: keyof ProfileForm) => (
    e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>
  ) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    // No PATCH endpoint exists yet — edits are preview-only until LinkedIn OAuth is connected.
    // Show an honest message instead of a fake "saved" toast.
    toast.info("Connect LinkedIn OAuth in Settings to push these changes to your profile.");
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-md rounded-3xl border border-border bg-card p-6 shadow-xl"
      >
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Linkedin className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">Edit Profile</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-secondary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>
        <form onSubmit={handleSave} className="space-y-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Headline</label>
            <input
              value={form.headline}
              onChange={set("headline")}
              placeholder="Full-stack Developer | React · Python"
              className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-muted-foreground">Summary / About</label>
            <textarea
              value={form.summary}
              onChange={set("summary")}
              rows={4}
              placeholder="Write a compelling summary…"
              className="w-full resize-none rounded-2xl border border-border bg-background/60 px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Location</label>
              <input
                value={form.location}
                onChange={set("location")}
                placeholder="City, Country"
                className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-muted-foreground">Website</label>
              <input
                value={form.website}
                onChange={set("website")}
                placeholder="yoursite.com"
                className="h-10 w-full rounded-2xl border border-border bg-background/60 px-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
              />
            </div>
          </div>
          <div className="flex items-center gap-2 rounded-2xl border border-border bg-card/40 px-3 py-2">
            <Linkedin className="h-3.5 w-3.5 text-muted-foreground" />
            <span className="text-xs text-muted-foreground">
              <Link href="/settings/account" className="text-primary underline hover:no-underline">
                Connect LinkedIn OAuth in Settings
              </Link>{" "}
              to push changes live
            </span>
          </div>
          <div className="flex gap-2 pt-1">
            <LiquidGlassButton tone="primary" size="sm" className="flex-1">
              <Save className="h-3.5 w-3.5" /> Save changes
            </LiquidGlassButton>
            <LiquidGlassButton tone="ghost" size="sm" type="button" onClick={onClose}>
              Cancel
            </LiquidGlassButton>
          </div>
        </form>
      </motion.div>
    </div>
  );
}

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
  const [editOpen, setEditOpen] = useState(false);

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
      toast.success("LinkedIn analysis started");
      setTimeout(() => qc.invalidateQueries({ queryKey: ["linkedin-run"] }), 5000);
    },
    onError: () => {
      toast.error("Agent unavailable — backend not connected");
    },
  });

  const { sections, recommendations, overallScore } = parseOutput(lastRun ?? null);

  const isRunning = analysisMutation.isPending;

  return (
    <>
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
            <LiquidGlassButton tone="ghost" size="sm" onClick={() => setEditOpen(true)}>
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

        {/* Two-column layout */}
        {!isLoading && lastRun && (
          <motion.div variants={fadeUp} className="flex gap-4">
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
                      <button
                        onClick={() => setEditOpen(true)}
                        className="shrink-0 rounded-full border border-border bg-background/60 px-3 py-1.5 text-xs font-medium text-foreground transition-colors hover:bg-primary/10 hover:text-primary"
                      >
                        Optimize
                      </button>
                    </div>
                  ))}
                </div>
              </div>
            </div>

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
                          <button
                            onClick={() => {
                              toast.success("Opening editor for this section");
                              setEditOpen(true);
                            }}
                            className="mt-2 flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                          >
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

      <AnimatePresence>
        {editOpen && <EditProfileModal onClose={() => setEditOpen(false)} />}
      </AnimatePresence>
    </>
  );
}
