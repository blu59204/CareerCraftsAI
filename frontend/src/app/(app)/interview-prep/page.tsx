"use client";

import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { motion, AnimatePresence } from "motion/react";
import {
  Mic,
  Building2,
  BriefcaseBusiness,
  Sparkles,
  ChevronDown,
  ChevronUp,
  Plus,
  BarChart3,
  BookOpen,
  Code2,
  Play,
  MessageSquare,
  Loader2,
} from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";
import { apiClient } from "@/lib/api";

type Category = "All" | "Technical" | "Behavioral" | "Company-Specific";
type Difficulty = "Easy" | "Medium" | "Hard";

interface Question {
  id: string;
  category: Exclude<Category, "All">;
  text: string;
  difficulty: Difficulty;
}

interface StarStory {
  id: string;
  title: string;
}

const BASE_QUESTIONS: Question[] = [
  { id: "b1", category: "Technical", difficulty: "Medium", text: "Explain the difference between useEffect and useLayoutEffect in React. When would you use each?" },
  { id: "b2", category: "Behavioral", difficulty: "Easy", text: "Tell me about yourself and your journey as a developer." },
  { id: "b3", category: "Technical", difficulty: "Hard", text: "How would you optimize the performance of a React application with 10,000+ list items?" },
  { id: "b4", category: "Behavioral", difficulty: "Medium", text: "Describe a time you disagreed with your team lead. How did you handle it?" },
  { id: "b5", category: "Technical", difficulty: "Medium", text: "What's the difference between useMemo and useCallback? Give examples." },
  { id: "b6", category: "Behavioral", difficulty: "Easy", text: "Where do you see yourself in 5 years?" },
];

const BASE_STAR_STORIES: StarStory[] = [
  { id: "s1", title: "Led migration from Webpack to Vite — cut build time 73%" },
  { id: "s2", title: "Debugged production race condition affecting 500 users" },
];

const CATEGORY_TABS: Category[] = ["All", "Technical", "Behavioral", "Company-Specific"];

const DIFFICULTY_CONFIG: Record<Difficulty, { label: string; className: string }> = {
  Easy: { label: "Easy", className: "bg-emerald-500/15 text-emerald-600 border-emerald-500/30" },
  Medium: { label: "Medium", className: "bg-amber-500/15 text-amber-600 border-amber-500/30" },
  Hard: { label: "Hard", className: "bg-red-500/15 text-red-500 border-red-500/30" },
};

const CATEGORY_CONFIG: Record<Exclude<Category, "All">, string> = {
  Technical: "bg-blue-500/15 text-blue-600 border-blue-500/30",
  Behavioral: "bg-violet-500/15 text-violet-600 border-violet-500/30",
  "Company-Specific": "bg-orange-500/15 text-orange-600 border-orange-500/30",
};

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums">{value > 0 ? `${value}%` : "—"}</span>
      </div>
      <div className="h-1.5 w-full overflow-hidden rounded-full bg-secondary">
        <motion.div
          initial={{ width: 0 }}
          animate={{ width: `${value}%` }}
          transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1], delay: 0.4 }}
          className="h-full rounded-full bg-primary"
        />
      </div>
    </div>
  );
}

function QuestionCard({ question, company, role }: { question: Question; company: string; role: string }) {
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [gettingFeedback, setGettingFeedback] = useState(false);

  const diffCfg = DIFFICULTY_CONFIG[question.difficulty];
  const catCfg = CATEGORY_CONFIG[question.category];

  async function handleFeedback() {
    if (!answer.trim() || gettingFeedback) return;
    setGettingFeedback(true);
    setFeedback(null);
    try {
      const { data } = await apiClient.post("/agents/run", {
        task_type: "interview_prep",
        context: {
          mode: "feedback",
          question: question.text,
          answer,
          company,
          role,
        },
      });
      setFeedback(
        `Run started (ID: ${data.run_id}). Check Agents page for your feedback when complete.`
      );
    } catch {
      setFeedback("Could not connect to agent. Try again.");
    } finally {
      setGettingFeedback(false);
    }
  }

  return (
    <motion.div
      variants={fadeUp}
      layout
      className="rounded-3xl border border-border bg-card/60 p-6 transition-shadow hover:shadow-md"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${catCfg}`}>
            {question.category}
          </span>
          <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${diffCfg.className}`}>
            {diffCfg.label}
          </span>
        </div>
        <LiquidGlassButton tone="ghost" size="sm" onClick={() => setOpen((v) => !v)} className="shrink-0 gap-1.5">
          {open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          Practice
        </LiquidGlassButton>
      </div>

      <p className="mt-3 text-sm font-medium leading-relaxed">{question.text}</p>

      <AnimatePresence initial={false}>
        {open && (
          <motion.div
            key="answer-area"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3, ease: "easeInOut" }}
            className="overflow-hidden"
          >
            <div className="mt-4 space-y-3">
              <textarea
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer here — think out loud, structure matters…"
                rows={4}
                className="w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground/60 focus:outline-none focus:ring-2 focus:ring-ring"
              />
              <div className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{answer.length} characters</span>
                <button
                  onClick={handleFeedback}
                  disabled={gettingFeedback || !answer.trim()}
                  className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline disabled:opacity-40"
                >
                  {gettingFeedback ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <Sparkles className="h-3.5 w-3.5" />
                  )}
                  Get AI feedback
                </button>
              </div>
              {feedback && (
                <p className="rounded-xl bg-primary/5 px-3 py-2 text-xs text-muted-foreground">{feedback}</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function InterviewPrepPage() {
  const qc = useQueryClient();
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [activeTab, setActiveTab] = useState<Category>("All");
  const [stories, setStories] = useState<StarStory[]>(BASE_STAR_STORIES);

  const { data: lastRun } = useQuery({
    queryKey: ["interview-prep-run"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=50");
      const runs = (data as { agent_type: string; status: string; output: Record<string, unknown> | null }[])
        .filter((r) => r.agent_type === "interview_prep" && r.status === "completed");
      return runs[0] ?? null;
    },
  });

  const aiQuestions: Question[] = (() => {
    if (!lastRun?.output) return [];
    const out = lastRun.output as Record<string, unknown>;
    if (Array.isArray(out.questions)) {
      return (out.questions as Question[]).map((q, i) => ({
        ...q,
        id: `ai-${i}`,
        category: (q.category as Exclude<Category, "All">) || "Company-Specific",
        difficulty: (q.difficulty as Difficulty) || "Medium",
      }));
    }
    return [];
  })();

  const allQuestions = [...aiQuestions, ...BASE_QUESTIONS];

  const filtered =
    activeTab === "All" ? allQuestions : allQuestions.filter((q) => q.category === activeTab);

  const generateMutation = useMutation({
    mutationFn: () =>
      apiClient.post("/agents/run", {
        task_type: "interview_prep",
        context: {
          mode: "generate",
          company: company || "any company",
          role: role || "Software Engineer",
          count: 8,
        },
      }),
    onSuccess: () => {
      setTimeout(() => qc.invalidateQueries({ queryKey: ["interview-prep-run"] }), 10000);
    },
  });

  const aiScore =
    lastRun?.output && typeof (lastRun.output as Record<string, unknown>).prep_score === "number"
      ? (lastRun.output as Record<string, unknown>).prep_score as number
      : null;

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* Header */}
      <motion.div variants={fadeUp} className="flex items-start justify-between gap-4">
        <div>
          <div className="text-sm text-muted-foreground">Interview Prep</div>
          <h1 className="mt-1 text-3xl font-medium">Practice makes perfect.</h1>
        </div>
        <div className="flex shrink-0 gap-2">
          <LiquidGlassButton tone="ghost" size="sm">
            <Mic className="h-4 w-4" />
            Mock interview
          </LiquidGlassButton>
          <LiquidGlassButton
            tone="primary"
            size="sm"
            onClick={() => generateMutation.mutate()}
            disabled={generateMutation.isPending}
          >
            {generateMutation.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            {generateMutation.isPending ? "Generating…" : "Generate questions"}
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* Target job row */}
      <motion.div
        variants={fadeUp}
        className="flex flex-wrap items-center gap-3 rounded-3xl border border-border bg-card/60 p-5"
      >
        <div className="relative flex-1 min-w-36">
          <Building2 className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            placeholder="Company"
            className="h-10 w-full rounded-full border border-border bg-background/60 pl-10 pr-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <div className="relative flex-1 min-w-44">
          <BriefcaseBusiness className="absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <input
            value={role}
            onChange={(e) => setRole(e.target.value)}
            placeholder="Role"
            className="h-10 w-full rounded-full border border-border bg-background/60 pl-10 pr-4 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring"
          />
        </div>
        <LiquidGlassButton
          tone="primary"
          size="sm"
          onClick={() => generateMutation.mutate()}
          disabled={generateMutation.isPending}
        >
          <Sparkles className="h-3.5 w-3.5" />
          Analyze
        </LiquidGlassButton>
      </motion.div>

      {/* Generation progress */}
      {generateMutation.isPending && (
        <motion.div variants={fadeUp} className="flex items-center gap-3 rounded-2xl border border-border bg-card/40 px-5 py-3 text-sm text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin text-primary" />
          Generating role-specific questions for {role || "your target role"}…
        </motion.div>
      )}

      {/* Two-column layout */}
      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        {/* LEFT: question list */}
        <div className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">Interview Questions</span>
              <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-semibold text-secondary-foreground">
                {filtered.length}
              </span>
              {aiQuestions.length > 0 && (
                <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                  {aiQuestions.length} AI-generated
                </span>
              )}
            </div>
            <div className="flex flex-wrap gap-1.5">
              {CATEGORY_TABS.map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-colors ${
                    activeTab === tab
                      ? "border-primary bg-primary text-primary-foreground"
                      : "border-border bg-card/40 text-muted-foreground hover:bg-card/70"
                  }`}
                >
                  {tab}
                </button>
              ))}
            </div>
          </div>

          <motion.div layout className="space-y-3">
            <AnimatePresence mode="popLayout">
              {filtered.map((q) => (
                <QuestionCard key={q.id} question={q} company={company} role={role} />
              ))}
            </AnimatePresence>
          </motion.div>
        </div>

        {/* RIGHT: prep assistant */}
        <div className="space-y-4">
          {/* AI Prep Score */}
          <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-5">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold">AI Prep Score</span>
            </div>
            {aiScore !== null ? (
              <>
                <div className="flex items-end gap-3">
                  <span className="text-5xl font-semibold tabular-nums leading-none">{aiScore}</span>
                  <span className="mb-1 text-lg text-muted-foreground">%</span>
                  <span className={`mb-1 rounded-full border px-2 py-0.5 text-xs font-medium ${
                    aiScore >= 80 ? "bg-green-500/15 border-green-500/30 text-green-600"
                    : aiScore >= 60 ? "bg-amber-500/15 border-amber-500/30 text-amber-600"
                    : "bg-red-500/15 border-red-500/30 text-red-500"
                  }`}>
                    {aiScore >= 80 ? "Strong" : aiScore >= 60 ? "Good" : "Needs Work"}
                  </span>
                </div>
                <div className="space-y-3 pt-1">
                  <ScoreBar label="Technical" value={
                    (lastRun?.output as Record<string, unknown>)?.technical_score as number ?? 0
                  } />
                  <ScoreBar label="Behavioral" value={
                    (lastRun?.output as Record<string, unknown>)?.behavioral_score as number ?? 0
                  } />
                </div>
              </>
            ) : (
              <p className="text-sm text-muted-foreground">
                Generate questions and practice answers to see your prep score.
              </p>
            )}
          </div>

          {/* STAR Story Builder */}
          <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold">STAR Story Builder</span>
            </div>
            <p className="text-xs text-muted-foreground">Build answer frameworks</p>
            <div className="space-y-2">
              {stories.map((story) => (
                <div key={story.id} className="rounded-2xl border border-border bg-background/40 p-4 space-y-2">
                  <p className="text-xs font-medium leading-snug">{story.title}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {["Situation", "Task", "Action", "Result"].map((step) => (
                      <span key={step} className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground">
                        {step}
                      </span>
                    ))}
                  </div>
                </div>
              ))}
              <LiquidGlassButton
                tone="ghost"
                size="sm"
                className="w-full gap-1.5 mt-1"
                onClick={() => setStories((s) => [...s, { id: `s${Date.now()}`, title: "New story — click to edit" }])}
              >
                <Plus className="h-3.5 w-3.5" />
                Add new story
              </LiquidGlassButton>
            </div>
          </div>

          {/* Company Research — dynamic based on company input */}
          {company && (
            <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
              <div className="flex items-center gap-2">
                <Code2 className="h-4 w-4 text-muted-foreground" />
                <span className="text-sm font-semibold">Company: {company}</span>
              </div>
              <p className="text-xs text-muted-foreground leading-relaxed">
                Generate questions targeting <span className="font-medium text-foreground">{company}</span> to get
                company-specific interview preparation.
              </p>
              <LiquidGlassButton
                tone="ghost"
                size="sm"
                className="w-full"
                onClick={() => generateMutation.mutate()}
                disabled={generateMutation.isPending}
              >
                <Sparkles className="h-3.5 w-3.5" />
                Generate {company}-specific questions
              </LiquidGlassButton>
            </div>
          )}
        </div>
      </motion.div>

      {/* Mock interview banner */}
      <motion.div variants={fadeUp} className="rounded-3xl border border-border bg-card/60 p-6">
        <div className="flex flex-col items-center gap-4 text-center sm:flex-row sm:text-left sm:justify-between">
          <div className="space-y-1">
            <div className="flex items-center justify-center gap-2 sm:justify-start">
              <MessageSquare className="h-4 w-4 text-primary" />
              <span className="text-sm font-semibold">20-minute mock interview</span>
            </div>
            <p className="text-sm text-muted-foreground max-w-md">
              AI will ask questions and evaluate your answers in real time — scored on clarity, structure, and depth.
            </p>
          </div>
          <LiquidGlassButton tone="primary" size="lg" className="shrink-0 gap-2 sm:w-auto w-full">
            <Play className="h-4 w-4" />
            Start mock interview
          </LiquidGlassButton>
        </div>
      </motion.div>
    </motion.div>
  );
}
