"use client";

import { useState } from "react";
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
  Newspaper,
  Code2,
  Play,
  MessageSquare,
} from "lucide-react";
import { fadeUp, stagger } from "@/lib/motion-variants";
import { LiquidGlassButton } from "@/components/ui/LiquidGlassButton";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Data
// ---------------------------------------------------------------------------

const QUESTIONS: Question[] = [
  {
    id: "1",
    category: "Technical",
    difficulty: "Medium",
    text: "Explain the difference between useEffect and useLayoutEffect in React. When would you use each?",
  },
  {
    id: "2",
    category: "Behavioral",
    difficulty: "Easy",
    text: "Tell me about yourself and your journey as a developer.",
  },
  {
    id: "3",
    category: "Technical",
    difficulty: "Hard",
    text: "How would you optimize the performance of a React application with 10,000+ list items?",
  },
  {
    id: "4",
    category: "Company-Specific",
    difficulty: "Medium",
    text: "Why do you want to work at Stripe specifically?",
  },
  {
    id: "5",
    category: "Technical",
    difficulty: "Hard",
    text: "Design a system for real-time collaborative editing like Notion. Walk me through your architecture.",
  },
  {
    id: "6",
    category: "Behavioral",
    difficulty: "Medium",
    text: "Describe a time you disagreed with your team lead. How did you handle it?",
  },
  {
    id: "7",
    category: "Technical",
    difficulty: "Medium",
    text: "What's the difference between useMemo and useCallback? Give examples.",
  },
  {
    id: "8",
    category: "Behavioral",
    difficulty: "Easy",
    text: "Where do you see yourself in 5 years?",
  },
];

const STAR_STORIES: StarStory[] = [
  { id: "1", title: "Led migration from Webpack to Vite — cut build time 73%" },
  { id: "2", title: "Debugged production race condition affecting 500 users" },
];

const CATEGORY_TABS: Category[] = ["All", "Technical", "Behavioral", "Company-Specific"];

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="space-y-1.5">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-semibold tabular-nums">{value}%</span>
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

function QuestionCard({ question }: { question: Question }) {
  const [open, setOpen] = useState(false);
  const [answer, setAnswer] = useState("");

  const diffCfg = DIFFICULTY_CONFIG[question.difficulty];
  const catCfg = CATEGORY_CONFIG[question.category];

  return (
    <motion.div
      variants={fadeUp}
      layout
      className="rounded-3xl border border-border bg-card/60 p-6 transition-shadow hover:shadow-md"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap gap-2">
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${catCfg}`}
          >
            {question.category}
          </span>
          <span
            className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${diffCfg.className}`}
          >
            {diffCfg.label}
          </span>
        </div>
        <LiquidGlassButton
          tone="ghost"
          size="sm"
          onClick={() => setOpen((v) => !v)}
          className="shrink-0 gap-1.5"
        >
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
                <span className="text-xs text-muted-foreground">
                  {answer.length} characters
                </span>
                <button className="flex items-center gap-1.5 text-xs font-medium text-primary hover:underline">
                  <Sparkles className="h-3.5 w-3.5" />
                  Get AI feedback
                </button>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export default function InterviewPrepPage() {
  const [company, setCompany] = useState("Stripe");
  const [role, setRole] = useState("Frontend Engineer");
  const [activeTab, setActiveTab] = useState<Category>("All");

  const filtered =
    activeTab === "All" ? QUESTIONS : QUESTIONS.filter((q) => q.category === activeTab);

  return (
    <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
      {/* ---- Header ---- */}
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
          <LiquidGlassButton tone="primary" size="sm">
            <Sparkles className="h-4 w-4" />
            Generate questions
          </LiquidGlassButton>
        </div>
      </motion.div>

      {/* ---- Target job row ---- */}
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
        <LiquidGlassButton tone="primary" size="sm">
          <Sparkles className="h-3.5 w-3.5" />
          Analyze
        </LiquidGlassButton>
      </motion.div>

      {/* ---- Two-column layout ---- */}
      <motion.div variants={fadeUp} className="grid gap-6 lg:grid-cols-[3fr_2fr]">
        {/* ---- LEFT: question list ---- */}
        <div className="space-y-4">
          {/* Header + tabs */}
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold">Interview Questions</span>
              <span className="rounded-full bg-secondary px-2 py-0.5 text-xs font-semibold text-secondary-foreground">
                {filtered.length}
              </span>
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

          {/* Question cards */}
          <motion.div layout className="space-y-3">
            <AnimatePresence mode="popLayout">
              {filtered.map((q) => (
                <QuestionCard key={q.id} question={q} />
              ))}
            </AnimatePresence>
          </motion.div>
        </div>

        {/* ---- RIGHT: prep assistant ---- */}
        <div className="space-y-4">
          {/* AI Prep Score */}
          <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-5">
            <div className="flex items-center gap-2">
              <BarChart3 className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold">AI Prep Score</span>
            </div>

            <div className="flex items-end gap-3">
              <span className="text-5xl font-semibold tabular-nums leading-none">72</span>
              <span className="mb-1 text-lg text-muted-foreground">%</span>
              <span className="mb-1 rounded-full bg-amber-500/15 border border-amber-500/30 px-2 py-0.5 text-xs font-medium text-amber-600">
                Good
              </span>
            </div>

            <div className="space-y-3 pt-1">
              <ScoreBar label="Technical" value={68} />
              <ScoreBar label="Behavioral" value={78} />
            </div>
          </div>

          {/* STAR Story Builder */}
          <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <BookOpen className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold">STAR Story Builder</span>
            </div>
            <p className="text-xs text-muted-foreground">Build answer frameworks</p>

            <div className="space-y-2">
              {STAR_STORIES.map((story) => (
                <div
                  key={story.id}
                  className="rounded-2xl border border-border bg-background/40 p-4 space-y-2"
                >
                  <p className="text-xs font-medium leading-snug">{story.title}</p>
                  <div className="flex flex-wrap gap-1.5">
                    {["Situation", "Task", "Action", "Result"].map((step) => (
                      <span
                        key={step}
                        className="rounded-full border border-border px-2 py-0.5 text-[10px] text-muted-foreground"
                      >
                        {step}
                      </span>
                    ))}
                  </div>
                </div>
              ))}

              <LiquidGlassButton tone="ghost" size="sm" className="w-full gap-1.5 mt-1">
                <Plus className="h-3.5 w-3.5" />
                Add new story
              </LiquidGlassButton>
            </div>
          </div>

          {/* Company Research */}
          <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-4">
            <div className="flex items-center gap-2">
              <Newspaper className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm font-semibold">Company Research</span>
            </div>

            <div className="space-y-3">
              <p className="text-xs text-muted-foreground leading-relaxed">
                Founded 2010 · Payments infrastructure · 7,000+ employees
              </p>

              <div>
                <p className="text-xs font-medium mb-2">Recent news</p>
                <div className="flex flex-wrap gap-1.5">
                  {["Stripe IPO 2025", "MCP launch", "Africa expansion"].map((news) => (
                    <span
                      key={news}
                      className="rounded-full border border-border bg-secondary px-2.5 py-0.5 text-xs text-secondary-foreground"
                    >
                      {news}
                    </span>
                  ))}
                </div>
              </div>

              <div>
                <div className="flex items-center gap-1.5 mb-2">
                  <Code2 className="h-3.5 w-3.5 text-muted-foreground" />
                  <p className="text-xs font-medium">Tech stack</p>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {["Next.js", "Ruby", "Go", "Sorbet"].map((tech) => (
                    <span
                      key={tech}
                      className="rounded-full bg-primary/10 border border-primary/20 px-2.5 py-0.5 text-xs font-medium text-primary"
                    >
                      {tech}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </div>
        </div>
      </motion.div>

      {/* ---- Mock interview banner ---- */}
      <motion.div
        variants={fadeUp}
        className="rounded-3xl border border-border bg-card/60 p-6"
      >
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
