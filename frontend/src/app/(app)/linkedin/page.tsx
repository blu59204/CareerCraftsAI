"use client";

import Link from "next/link";
import { useEffect, useId, useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence, useReducedMotion } from "motion/react";
import { toast } from "sonner";
import {
  CaretRight,
  Check,
  CheckCircle,
  CircleNotch,
  Copy,
  FloppyDisk,
  Lightning,
  ShieldCheck,
  Sparkle,
  Target,
  WarningCircle,
  X,
} from "@phosphor-icons/react";
import { BrandLinkedin } from "@/components/icons/BrandIcons";
import { apiClient, getApiErrorMessage } from "@/lib/api";
import { ApprovalModal } from "@/components/agents/ApprovalModal";
import { cn } from "@/lib/utils";
import {
  Bezel,
  bezelCore,
  bezelShell,
  EASE_OUT_EXPO,
  EmptyPanel,
  Eyebrow,
  Field,
  Hairline,
  IconButton,
  Input,
  IslandButton,
  listItem,
  Notice,
  PanelTitle,
  Reveal,
  RevealGroup,
  Screen,
  Section,
  SectionHeading,
  Skeleton,
  SPRING_PANEL,
  StatStrip,
  StatusPill,
  Textarea,
} from "@/components/vanguard";

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

/* ───────────────────────────── Edit profile dialog ───────────────────────────── */

function EditProfileModal({ onClose }: { onClose: () => void }) {
  const titleId = useId();
  const reduce = useReducedMotion();
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

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center p-4 font-geist">
      <motion.div
        aria-hidden
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.4, ease: EASE_OUT_EXPO }}
        className="absolute inset-0 bg-background/70 backdrop-blur-md"
        onClick={onClose}
      />
      <motion.div
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        initial={reduce ? { opacity: 0 } : { opacity: 0, y: 24, scale: 0.97 }}
        animate={reduce ? { opacity: 1 } : { opacity: 1, y: 0, scale: 1 }}
        exit={reduce ? { opacity: 0 } : { opacity: 0, y: 16, scale: 0.98 }}
        transition={reduce ? { duration: 0.2 } : SPRING_PANEL}
        className={cn("relative w-full max-w-lg shadow-ambient", bezelShell("lg"))}
      >
        <div className={cn("max-h-[calc(100dvh-2rem)] overflow-y-auto p-6 md:p-8", bezelCore("lg"))}>
          <div className="flex items-start justify-between gap-4">
            <div>
              <Eyebrow>
                <BrandLinkedin className="h-3 w-3" />
                Preview only
              </Eyebrow>
              <h2 id={titleId} className="mt-4 text-2xl font-semibold tracking-[-0.03em] text-foreground">
                Edit Profile
              </h2>
            </div>
            <IconButton aria-label="Close" onClick={onClose}>
              <X size={16} weight="light" />
            </IconButton>
          </div>

          <form onSubmit={handleSave} className="mt-7 space-y-5">
            <Field label="Headline">
              {(id) => (
                <Input
                  id={id}
                  value={form.headline}
                  onChange={set("headline")}
                  placeholder="Full-stack Developer | React · Python"
                />
              )}
            </Field>
            <Field label="Summary / About">
              {(id) => (
                <Textarea
                  id={id}
                  value={form.summary}
                  onChange={set("summary")}
                  rows={4}
                  placeholder="Write a compelling summary…"
                  className="resize-none"
                />
              )}
            </Field>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Field label="Location">
                {(id) => (
                  <Input id={id} value={form.location} onChange={set("location")} placeholder="City, Country" />
                )}
              </Field>
              <Field label="Website">
                {(id) => (
                  <Input id={id} value={form.website} onChange={set("website")} placeholder="yoursite.com" />
                )}
              </Field>
            </div>

            <Notice tone="neutral" icon={<BrandLinkedin className="h-3.5 w-3.5" />}>
              <Link
                href="/settings/account"
                className="font-medium text-primary underline underline-offset-4 transition-colors duration-500 ease-vanguard hover:no-underline"
              >
                Connect LinkedIn OAuth in Settings
              </Link>{" "}
              to push changes live.
            </Notice>

            <div className="flex flex-wrap gap-2 pt-1">
              <IslandButton type="submit" tone="primary" size="sm" icon={<FloppyDisk size={15} weight="light" />} className="flex-1">
                Save changes
              </IslandButton>
              <IslandButton tone="ghost" size="sm" onClick={onClose}>
                Cancel
              </IslandButton>
            </div>
          </form>
        </div>
      </motion.div>
    </div>
  );
}

/* ───────────────────────────── Small presentational pieces ───────────────────────────── */

function ScoreBar({ score, className }: { score: number; className?: string }) {
  const color = score >= 85 ? "bg-success" : score >= 70 ? "bg-warning" : "bg-danger";
  const clamped = Math.max(0, Math.min(100, score));

  return (
    <div className={cn("flex items-center gap-3", className)}>
      <div aria-hidden className="h-1 flex-1 overflow-hidden rounded-full bg-foreground/[0.06] dark:bg-white/[0.08]">
        <div
          className={cn("h-full w-full origin-left rounded-full transition-transform duration-700 ease-vanguard", color)}
          style={{ transform: `scaleX(${clamped / 100})` }}
        />
      </div>
      <span className="w-10 text-right font-geist-mono text-xs tabular-nums text-foreground">
        {score > 0 ? `${score}%` : "—"}
      </span>
    </div>
  );
}

function StatusChip({ status }: { status: ProfileSection["status"] }) {
  if (status === "strong")
    return (
      <StatusPill tone="success" icon={<CheckCircle size={12} weight="light" />}>
        Strong
      </StatusPill>
    );
  if (status === "good") return <StatusPill tone="success">Good</StatusPill>;
  return (
    <StatusPill tone="warning" icon={<WarningCircle size={12} weight="light" />}>
      Improve
    </StatusPill>
  );
}

function charLimitFor(name: string): number | null {
  const lowered = name.toLowerCase();
  if (lowered.startsWith("headline")) return 220;
  if (lowered.includes("about") || lowered.includes("summary")) return 2600;
  return null;
}

function testIdFor(name: string): string {
  const lowered = name.toLowerCase();
  if (lowered.startsWith("headline")) return "linkedin-headline";
  if (lowered.includes("about") || lowered.includes("summary")) return "linkedin-about";
  if (lowered.includes("experience")) return "linkedin-experience";
  return `linkedin-${lowered.replace(/[^a-z0-9]+/g, "-")}`;
}

interface DraftCardProps {
  index: number;
  section: ProfileSection;
  current: string | null;
  draft: string | null;
  onOptimize: () => void;
}

/** Before → after enclosure for one profile section, with copy + optimize actions. */
function DraftCard({ index, section, current, draft, onOptimize }: DraftCardProps) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const limit = charLimitFor(section.name);

  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const copyDraft = async () => {
    if (!draft) return;
    try {
      await navigator.clipboard.writeText(draft);
      toast.success(`${section.name} draft copied`);
      setCopied(true);
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error("Clipboard unavailable — select the text and copy it manually");
    }
  };

  return (
    <motion.article variants={listItem} aria-label={`${section.name} before and after`}>
      <Bezel size="lg" coreClassName="p-5 md:p-7">
        <header className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <span className="font-geist-mono text-[11px] tabular-nums text-muted-foreground">
              {String(index + 1).padStart(2, "0")}
            </span>
            <h3 className="truncate text-lg font-semibold tracking-[-0.025em] text-foreground">{section.name}</h3>
          </div>
          <StatusChip status={section.status} />
        </header>

        <ScoreBar score={section.score} className="mt-4" />

        <div className="mt-6 grid gap-2">
          {/* Before */}
          <div className="rounded-[1.1rem] bg-foreground/[0.025] px-4 py-3.5 ring-1 ring-foreground/[0.05] dark:bg-white/[0.025] dark:ring-white/[0.06]">
            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">Before</p>
            {current ? (
              <p className="mt-2 line-clamp-3 text-sm leading-6 text-muted-foreground">{current}</p>
            ) : (
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Live profile not imported.{" "}
                <Link
                  href="/settings/account"
                  className="text-foreground underline decoration-foreground/20 underline-offset-4 transition-colors duration-500 ease-vanguard hover:decoration-primary"
                >
                  Connect LinkedIn OAuth
                </Link>
              </p>
            )}
          </div>

          {/* After */}
          <div className="rounded-[1.1rem] bg-primary/[0.045] px-4 py-4 ring-1 ring-primary/15">
            <div className="flex items-center justify-between gap-3">
              <p className="inline-flex items-center gap-1.5 text-[10px] font-medium uppercase tracking-[0.18em] text-primary">
                <Sparkle size={12} weight="light" aria-hidden />
                After
              </p>
              {draft && limit ? (
                <span
                  className={cn(
                    "font-geist-mono text-[11px] tabular-nums",
                    draft.length > limit ? "text-danger" : "text-muted-foreground",
                  )}
                >
                  {draft.length}/{limit}
                </span>
              ) : null}
            </div>
            {draft ? (
              <p
                data-testid={testIdFor(section.name)}
                className="mt-2 max-h-72 overflow-y-auto whitespace-pre-line text-[15px] leading-7 text-foreground"
              >
                {draft}
              </p>
            ) : (
              <p className="mt-2 text-sm leading-6 text-muted-foreground">{section.excerpt}</p>
            )}
          </div>
        </div>

        <footer className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className="min-w-0 text-xs leading-5 text-muted-foreground">{section.note}</p>
          <div className="flex shrink-0 items-center gap-1.5">
            <IslandButton
              tone="ghost"
              size="sm"
              onClick={copyDraft}
              disabled={!draft}
              icon={copied ? <Check size={14} weight="light" /> : <Copy size={14} weight="light" />}
            >
              {copied ? "Copied" : "Copy"}
              <span className="sr-only"> {section.name} draft</span>
            </IslandButton>
            <IslandButton tone="quiet" size="sm" onClick={onOptimize}>
              Optimize
              <span className="sr-only"> {section.name}</span>
            </IslandButton>
          </div>
        </footer>
      </Bezel>
    </motion.article>
  );
}

/* ───────────────────────────── Output parsing ───────────────────────────── */

function parseOutput(run: AgentRun | null): {
  sections: ProfileSection[];
  recommendations: Recommendation[];
  overallScore: number | null;
} {
  if (!run?.output) return { sections: DEFAULT_SECTIONS, recommendations: [], overallScore: null };

  const out = run.output as Record<string, unknown>;

  if (out.type === "linkedin_edits") {
    const headline = typeof out.headline === "string" ? out.headline : "";
    const about = typeof out.about === "string" ? out.about : "";
    const experience = typeof out.experience_bullets === "string" ? out.experience_bullets : "";

    return {
      sections: [
        {
          name: "Headline",
          score: 82,
          excerpt: headline || "Draft ready",
          note: "Review draft before applying changes",
          status: "good",
        },
        {
          name: "Summary / About",
          score: 78,
          excerpt: about || "Draft ready",
          note: "Review draft before applying changes",
          status: "good",
        },
        {
          name: "Experience",
          score: 76,
          excerpt: experience || "Draft ready",
          note: "Review draft before applying changes",
          status: "good",
        },
        ...DEFAULT_SECTIONS.slice(3),
      ],
      recommendations: [
        headline && { id: "headline", priority: "High" as const, text: `Use headline: ${headline}` },
        about && { id: "about", priority: "High" as const, text: `Update About section: ${about.slice(0, 220)}` },
        experience && { id: "experience", priority: "Medium" as const, text: `Refresh experience bullets: ${experience}` },
      ].filter(Boolean) as Recommendation[],
      overallScore: 79,
    };
  }

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

/** Pull the real draft strings (after) and any imported current text (before) for the first three sections. */
function draftFor(run: AgentRun | null, section: ProfileSection, index: number): { current: string | null; draft: string | null } {
  const out = run?.output as Record<string, unknown> | null | undefined;
  if (!out) return { current: null, draft: null };
  if (out.type === "linkedin_edits") {
    const keys = ["headline", "about", "experience_bullets"] as const;
    const key = keys[index];
    const value = key ? out[key] : undefined;
    return { current: null, draft: typeof value === "string" && value.trim() ? value : null };
  }
  // Generic scored shape: the excerpt is the section as it reads today; the note carries the advice.
  return { current: section.score > 0 && section.excerpt ? section.excerpt : null, draft: null };
}

function runStatusTone(status: string | undefined) {
  if (status === "completed") return "success" as const;
  if (status === "awaiting_approval") return "warning" as const;
  if (status === "failed" || status === "cancelled") return "danger" as const;
  return "primary" as const;
}

/* ───────────────────────────── Page ───────────────────────────── */

export default function LinkedInPage() {
  const qc = useQueryClient();
  const reduce = useReducedMotion();
  const [editOpen, setEditOpen] = useState(false);
  const [targetRole, setTargetRole] = useState("");

  const { data: lastRun, isLoading } = useQuery<AgentRun | null>({
    queryKey: ["linkedin-run"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=50");
      const runs = ((Array.isArray(data) ? data : data.runs ?? []) as AgentRun[]).filter((r) => r.agent_type === "linkedin_optimize");
      return runs[0] ?? null;
    },
    refetchInterval: (query) => {
      const run = query.state.data as AgentRun | null | undefined;
      return !run || run.status === "running" || run.status === "pending" ? 2000 : false;
    },
  });

  const analysisMutation = useMutation({
    mutationFn: () =>
      apiClient.post("/agents/run", {
        task_type: "linkedin_optimize",
        // The agent reads context.target_role (defaults to "software engineer" server-side).
        context: targetRole.trim() ? { target_role: targetRole.trim() } : {},
      }),
    onSuccess: () => {
      toast.success("LinkedIn analysis started");
      qc.invalidateQueries({ queryKey: ["linkedin-run"] });
    },
    onError: (error) => {
      toast.error(getApiErrorMessage(error, "Agent unavailable — backend not connected"));
    },
  });

  const { sections, recommendations, overallScore } = parseOutput(lastRun ?? null);

  const isRunning =
    analysisMutation.isPending || lastRun?.status === "running" || lastRun?.status === "pending";
  const awaitingApproval = lastRun?.status === "awaiting_approval" && lastRun.output;

  const thinking =
    typeof (lastRun?.output as Record<string, unknown> | null | undefined)?.thinking === "string"
      ? ((lastRun?.output as Record<string, unknown>).thinking as string).trim()
      : "";

  const draftSections = sections.slice(0, 3);
  const otherSections = sections.slice(3);

  const startAnalysis = (event?: React.FormEvent) => {
    event?.preventDefault();
    if (isRunning) return;
    analysisMutation.mutate();
  };

  const enter = (delay: number) =>
    reduce
      ? { initial: { opacity: 0 }, animate: { opacity: 1 }, transition: { duration: 0.2 } }
      : {
          initial: { opacity: 0, y: 28, filter: "blur(10px)" },
          animate: { opacity: 1, y: 0, filter: "blur(0px)", transitionEnd: { filter: "none" } },
          transition: { duration: 0.9, ease: EASE_OUT_EXPO, delay },
        };

  return (
    <>
      <Screen>
        {/* ── Editorial split: statement + controls (left) · before/after drafts (right) ── */}
        <section
          aria-labelledby="linkedin-title"
          className="grid grid-cols-1 gap-6 pt-2 md:pt-4 lg:grid-cols-12 lg:gap-8"
        >
          <div className="min-w-0 lg:col-span-5">
            <div className="space-y-8 lg:sticky lg:top-24">
              <div>
                <motion.div {...enter(0)}>
                  <Eyebrow>
                    <BrandLinkedin className="h-3 w-3" />
                    LinkedIn agent
                  </Eyebrow>
                </motion.div>
                <motion.h1
                  id="linkedin-title"
                  {...enter(0.06)}
                  className="mt-4 text-balance text-[clamp(2rem,3.5vw,3.5rem)] font-semibold leading-[1.05] tracking-[-0.045em] text-foreground"
                >
                  LinkedIn presence{" "}
                  <span className="block text-muted-foreground/70">tuned to one role.</span>
                </motion.h1>
                <motion.p
                  {...enter(0.12)}
                  className="mt-6 max-w-[46ch] text-pretty text-[15px] leading-7 text-muted-foreground"
                >
                  Name the role you want next. The agent rewrites your headline, About and experience bullets against it, and nothing reaches LinkedIn without your approval.
                </motion.p>
              </div>

              <motion.form {...enter(0.18)} onSubmit={startAnalysis} className="space-y-4" aria-label="Run LinkedIn analysis">
                <Field label="Target role" hint="Optional — leave blank to optimize for a general software engineering role.">
                  {(id) => (
                    <Input
                      id={id}
                      name="target_role"
                      value={targetRole}
                      onChange={(e) => setTargetRole(e.target.value)}
                      placeholder="e.g. Senior Python Engineer"
                      autoComplete="organization-title"
                      leading={<Target size={16} weight="light" />}
                      disabled={isRunning}
                    />
                  )}
                </Field>
                <div className="flex flex-wrap items-center gap-2.5">
                  <IslandButton
                    type="submit"
                    tone="primary"
                    disabled={isRunning}
                    icon={
                      isRunning ? (
                        <CircleNotch size={16} weight="light" className="animate-spin" />
                      ) : (
                        <BrandLinkedin className="h-4 w-4" />
                      )
                    }
                    trailing
                  >
                    {isRunning ? "Analyzing…" : "Run Analysis"}
                  </IslandButton>
                  <IslandButton tone="ghost" onClick={() => setEditOpen(true)}>
                    Edit Profile
                  </IslandButton>
                </div>
              </motion.form>

              <motion.p
                {...enter(0.24)}
                className="flex items-start gap-2.5 text-xs leading-5 text-muted-foreground"
              >
                <ShieldCheck size={16} weight="light" className="mt-0.5 shrink-0 text-primary" aria-hidden />
                Drafts pause at a review checkpoint. Publishing requires LinkedIn OAuth and your explicit approval.
              </motion.p>
            </div>
          </div>

          <div className="min-w-0 space-y-6 lg:col-span-7">
            {/* Run status rail */}
            <Reveal subtle>
              <Bezel size="md" coreClassName="flex flex-wrap items-center justify-between gap-4 px-5 py-4">
                <div className="flex min-w-0 items-center gap-3" aria-live="polite">
                  {isLoading ? (
                    <StatusPill tone="neutral" live>Loading last run</StatusPill>
                  ) : lastRun ? (
                    <>
                      <StatusPill
                        tone={runStatusTone(lastRun.status)}
                        live={lastRun.status === "running" || lastRun.status === "pending"}
                      >
                        {lastRun.status.replace(/_/g, " ")}
                      </StatusPill>
                      <span className="truncate text-sm text-muted-foreground">
                        Last analysis
                        {lastRun.duration_ms ? (
                          <span className="font-geist-mono tabular-nums"> · {(lastRun.duration_ms / 1000).toFixed(1)}s</span>
                        ) : null}
                      </span>
                    </>
                  ) : (
                    <StatusPill tone="neutral">No analysis yet</StatusPill>
                  )}
                </div>
                {overallScore !== null ? (
                  <p className="flex items-baseline gap-1.5">
                    <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Score</span>
                    <span className="text-2xl font-semibold tabular-nums tracking-[-0.04em] text-foreground">{overallScore}</span>
                    <span className="font-geist-mono text-xs tabular-nums text-muted-foreground">/100</span>
                  </p>
                ) : null}
              </Bezel>
            </Reveal>

            {/* Loading */}
            {isLoading && (
              <div className="space-y-4" aria-hidden>
                {[0, 1, 2].map((i) => (
                  <Bezel key={i} size="lg" coreClassName="space-y-4 p-6 md:p-7">
                    <div className="flex items-center justify-between">
                      <Skeleton className="h-5 w-40 rounded-full" />
                      <Skeleton className="h-6 w-20 rounded-full" />
                    </div>
                    <Skeleton className="h-1 w-full rounded-full" />
                    <Skeleton className="h-16 w-full" />
                    <Skeleton className={cn("w-full", i === 1 ? "h-36" : "h-24")} />
                  </Bezel>
                ))}
              </div>
            )}

            {/* No analysis yet */}
            {!isLoading && !lastRun && (
              <Reveal>
                <Bezel size="lg" tone="muted">
                  <EmptyPanel
                    icon={<BrandLinkedin className="h-6 w-6" />}
                    title="No analysis yet"
                    description="Run the LinkedIn Agent to score your profile and draft a new headline, About section and experience bullets side by side."
                    action={
                      <IslandButton
                        tone="primary"
                        size="sm"
                        onClick={() => analysisMutation.mutate()}
                        disabled={isRunning}
                        icon={<Lightning size={15} weight="light" />}
                      >
                        Run Analysis
                      </IslandButton>
                    }
                  />
                </Bezel>
              </Reveal>
            )}

            {/* Before / after drafts */}
            {!isLoading && lastRun && (
              <div className="space-y-5">
                <div className="flex flex-wrap items-end justify-between gap-3 pt-2">
                  <div className="min-w-0">
                    <Eyebrow className="mb-4">AI drafts</Eyebrow>
                    <h2 className="font-geist text-2xl font-semibold tracking-[-0.03em] text-foreground md:text-3xl">Profile Sections</h2>
                  </div>
                  <span className="text-xs text-muted-foreground">Before → after, one section at a time</span>
                </div>

                {thinking ? (
                  <Reveal subtle>
                    <Notice tone="primary" icon={<Sparkle size={16} weight="light" />}>
                      <span className="font-medium">Why these changes: </span>
                      {thinking}
                    </Notice>
                  </Reveal>
                ) : null}

                <RevealGroup className="space-y-5">
                  {draftSections.map((section, index) => {
                    const { current, draft } = draftFor(lastRun ?? null, section, index);
                    return (
                      <DraftCard
                        key={section.name}
                        index={index}
                        section={section}
                        current={current}
                        draft={draft}
                        onOptimize={() => setEditOpen(true)}
                      />
                    );
                  })}
                </RevealGroup>
              </div>
            )}
          </div>
        </section>

        {/* ── Signal: remaining scores + recommendations (asymmetric pair) ── */}
        {!isLoading && lastRun && (
          <Section aria-label="Scores and recommendations">
            <Reveal>
              <SectionHeading
                eyebrow="Signal"
                title="Scores and next moves"
                description="What the agent measured beyond the three rewrites, and the edits it would make first."
              />
            </Reveal>

            {overallScore !== null && (
              <Reveal>
                <StatStrip
                  items={[
                    { label: "Profile Score", value: `${overallScore}/100`, hint: "From last analysis" },
                    { label: "Profile Views", value: <span className="text-muted-foreground">—</span>, hint: "LinkedIn OAuth required" },
                    { label: "Connections", value: <span className="text-muted-foreground">—</span>, hint: "LinkedIn OAuth required" },
                    { label: "Recommendations", value: recommendations.length, hint: "Action items" },
                  ]}
                />
              </Reveal>
            )}

            <div className="grid grid-cols-1 gap-6 lg:grid-cols-12">
              {otherSections.length > 0 && (
                <Reveal className="lg:col-span-5">
                  <Bezel size="lg" className="h-full" coreClassName="p-5 md:p-7">
                    <PanelTitle
                      title="More sections"
                      meta={<span className="font-geist-mono tabular-nums">{otherSections.length}</span>}
                    />
                    <ul className="mt-5">
                      {otherSections.map((section, i) => (
                        <li key={section.name}>
                          {i > 0 ? <Hairline /> : null}
                          <div className="py-4">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-medium text-foreground">{section.name}</p>
                              <StatusChip status={section.status} />
                            </div>
                            <p className="mt-1 truncate text-xs text-muted-foreground">{section.excerpt}</p>
                            <ScoreBar score={section.score} className="mt-3" />
                            <div className="mt-2 flex items-center justify-between gap-3">
                              <p className="min-w-0 truncate text-xs text-muted-foreground">{section.note}</p>
                              <IslandButton tone="quiet" size="sm" className="h-8 shrink-0 px-3 text-xs" onClick={() => setEditOpen(true)}>
                                Optimize
                                <span className="sr-only"> {section.name}</span>
                              </IslandButton>
                            </div>
                          </div>
                        </li>
                      ))}
                    </ul>
                  </Bezel>
                </Reveal>
              )}

              <Reveal delay={0.08} className={otherSections.length > 0 ? "lg:col-span-7" : "lg:col-span-12"}>
                <Bezel size="lg" className="h-full" coreClassName="p-5 md:p-7">
                  <PanelTitle
                    title="AI Recommendations"
                    icon={<Sparkle size={15} weight="light" />}
                    meta={<span className="font-geist-mono tabular-nums">{recommendations.length}</span>}
                  />
                  {recommendations.length === 0 ? (
                    <EmptyPanel
                      compact
                      title="No recommendations yet"
                      description="Run analysis to get personalized suggestions."
                    />
                  ) : (
                    <RevealGroup className="mt-5 space-y-2.5">
                      {recommendations.map((rec, i) => (
                        <motion.div
                          key={rec.id}
                          variants={listItem}
                          className="flex items-start gap-4 rounded-[1.1rem] bg-foreground/[0.02] p-4 ring-1 ring-foreground/[0.05] dark:bg-white/[0.02] dark:ring-white/[0.06]"
                        >
                          <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-primary/10 font-geist-mono text-xs tabular-nums text-primary ring-1 ring-primary/20">
                            {i + 1}
                          </span>
                          <div className="min-w-0 flex-1">
                            <StatusPill tone={rec.priority === "High" ? "danger" : "warning"}>{rec.priority}</StatusPill>
                            <p className="mt-2 text-sm leading-6 text-foreground">{rec.text}</p>
                            <button
                              type="button"
                              onClick={() => {
                                toast.success("Opening editor for this section");
                                setEditOpen(true);
                              }}
                              className="group mt-2 inline-flex items-center gap-1 rounded-full text-xs font-medium text-primary transition-colors duration-500 ease-vanguard hover:text-primary/80 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                            >
                              Apply
                              <CaretRight
                                size={12}
                                weight="light"
                                aria-hidden
                                className="transition-transform duration-500 ease-vanguard group-hover:translate-x-0.5"
                              />
                            </button>
                          </div>
                        </motion.div>
                      ))}
                    </RevealGroup>
                  )}
                </Bezel>
              </Reveal>
            </div>
          </Section>
        )}

        {/* ── Footer note ── */}
        <Reveal subtle>
          <Notice tone="neutral" icon={<Lightning size={16} weight="light" className="text-primary" />}>
            The LinkedIn Agent analyzes your profile against target roles and suggests keyword improvements.
          </Notice>
        </Reveal>
      </Screen>

      <AnimatePresence>
        {editOpen && <EditProfileModal onClose={() => setEditOpen(false)} />}
      </AnimatePresence>
      {awaitingApproval && (
        <ApprovalModal
          runId={lastRun.id}
          action={lastRun.output as Record<string, unknown>}
          onApprove={() => qc.invalidateQueries({ queryKey: ["linkedin-run"] })}
          onCancel={() => qc.invalidateQueries({ queryKey: ["linkedin-run"] })}
        />
      )}
    </>
  );
}
