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
  X,
  MicOff,
  Lightbulb,
  HelpCircle,
} from "lucide-react";
import { toast } from "sonner";
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

interface VideoResult {
  video_id: string;
  title: string;
  channel: string;
  thumbnail: string;
  watch_url: string;
  description: string;
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

const MOCK_INTERVIEW_QUESTIONS = [
  "Tell me about yourself.",
  "What's your greatest technical challenge you've overcome?",
  "Where do you see yourself in 5 years?",
  "Describe a conflict with a teammate and how you resolved it.",
  "What excites you most about this role?",
];

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

function MockInterviewModal({ onClose }: { onClose: () => void }) {
  const [step, setStep] = useState(0);
  const [answer, setAnswer] = useState("");
  const [answers, setAnswers] = useState<string[]>([]);
  const [done, setDone] = useState(false);

  const currentQ = MOCK_INTERVIEW_QUESTIONS[step];

  const handleNext = () => {
    if (!answer.trim()) {
      toast.error("Enter an answer before continuing");
      return;
    }
    setAnswers((prev) => [...prev, answer]);
    setAnswer("");
    if (step + 1 >= MOCK_INTERVIEW_QUESTIONS.length) {
      setDone(true);
    } else {
      setStep((s) => s + 1);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-background/80 backdrop-blur-sm" onClick={onClose} />
      <motion.div
        initial={{ opacity: 0, scale: 0.96, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 8 }}
        transition={{ duration: 0.2 }}
        className="relative z-10 w-full max-w-lg rounded-3xl border border-border bg-card p-6 shadow-xl"
      >
        <div className="mb-5 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <MessageSquare className="h-4 w-4 text-primary" />
            <span className="text-sm font-semibold">Mock Interview</span>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded-full hover:bg-secondary"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {done ? (
          <div className="space-y-4 text-center">
            <div className="flex h-14 w-14 mx-auto items-center justify-center rounded-full bg-green-100">
              <Sparkles className="h-6 w-6 text-green-600" />
            </div>
            <p className="text-base font-semibold">Interview complete!</p>
            <p className="text-sm text-muted-foreground">
              You answered {answers.length} questions. Connect the backend to get AI-powered feedback on your responses.
            </p>
            <LiquidGlassButton tone="primary" size="sm" className="mx-auto" onClick={onClose}>
              Done
            </LiquidGlassButton>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>Question {step + 1} of {MOCK_INTERVIEW_QUESTIONS.length}</span>
              <div className="flex gap-1">
                {MOCK_INTERVIEW_QUESTIONS.map((_, i) => (
                  <span
                    key={i}
                    className={`h-1.5 w-5 rounded-full transition-colors ${i <= step ? "bg-primary" : "bg-muted"}`}
                  />
                ))}
              </div>
            </div>
            <div className="rounded-2xl bg-primary/5 p-4">
              <p className="text-sm font-medium leading-relaxed">{currentQ}</p>
            </div>
            <div className="flex items-center gap-2 rounded-2xl border border-border bg-background/40 px-3 py-2">
              <MicOff className="h-3.5 w-3.5 text-muted-foreground" />
              <span className="text-xs text-muted-foreground">Voice input coming soon — type your answer below</span>
            </div>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="Type your answer here…"
              rows={4}
              autoFocus
              className="w-full resize-none rounded-2xl border border-border bg-background/60 px-4 py-3 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-primary/30"
            />
            <div className="flex gap-2">
              <LiquidGlassButton tone="primary" size="sm" className="flex-1" onClick={handleNext}>
                {step + 1 >= MOCK_INTERVIEW_QUESTIONS.length ? "Finish" : "Next question"}
              </LiquidGlassButton>
              <LiquidGlassButton tone="ghost" size="sm" onClick={onClose}>
                Exit
              </LiquidGlassButton>
            </div>
          </div>
        )}
      </motion.div>
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
  const [mockOpen, setMockOpen] = useState(false);
  const [editingStoryId, setEditingStoryId] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");

  const { data: lastRun } = useQuery({
    queryKey: ["interview-prep-run"],
    queryFn: async () => {
      const { data } = await apiClient.get("/agents/runs?limit=50");
      const runs = (data as { agent_type: string; status: string; output: Record<string, unknown> | null }[])
        .filter((r) => r.agent_type === "interview_prep" && r.status === "completed");
      return runs[0] ?? null;
    },
  });

  // Map agent output fields to Question[] — handles both old `questions` and new split fields
  const aiQuestions: Question[] = (() => {
    if (!lastRun?.output) return [];
    const out = lastRun.output as Record<string, unknown>;

    // New output format: behavioral_questions + technical_questions
    const behavioralQs: Question[] = Array.isArray(out.behavioral_questions)
      ? (out.behavioral_questions as string[]).map((q, i) => ({
          id: `b${i}`,
          category: "Behavioral" as const,
          text: q,
          difficulty: "Medium" as Difficulty,
        }))
      : [];

    const technicalQs: Question[] = Array.isArray(out.technical_questions)
      ? (out.technical_questions as string[]).map((q, i) => ({
          id: `t${i}`,
          category: "Technical" as const,
          text: q,
          difficulty: "Medium" as Difficulty,
        }))
      : [];

    if (behavioralQs.length > 0 || technicalQs.length > 0) {
      return [...behavioralQs, ...technicalQs];
    }

    // Fallback: legacy `questions` array
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

  const elevatorPitch =
    lastRun?.output && typeof (lastRun.output as Record<string, unknown>).elevator_pitch === "string"
      ? (lastRun.output as Record<string, unknown>).elevator_pitch as string
      : null;

  const questionsToAsk =
    lastRun?.output && Array.isArray((lastRun.output as Record<string, unknown>).questions_to_ask)
      ? (lastRun.output as Record<string, unknown>).questions_to_ask as string[]
      : null;

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
      toast.success("Generating questions — check Agents page for results");
      setTimeout(() => qc.invalidateQueries({ queryKey: ["interview-prep-run"] }), 10000);
    },
    onError: () => {
      toast.error("Agent unavailable — backend not connected");
    },
  });

  const aiScore =
    lastRun?.output && typeof (lastRun.output as Record<string, unknown>).prep_score === "number"
      ? (lastRun.output as Record<string, unknown>).prep_score as number
      : null;

  const { data: videos, isLoading: loadingVideos } = useQuery<VideoResult[]>({
    queryKey: ["interview-videos", company, role],
    queryFn: async () => {
      const { data } = await apiClient.get("/interview-prep/videos", {
        params: { company, role },
      });
      return data as VideoResult[];
    },
    enabled: !!role,
    staleTime: 24 * 60 * 60 * 1000,
  });

  return (
    <>
      <motion.div initial="hidden" animate="show" variants={stagger} className="space-y-8">
        {/* Header */}
        <motion.div variants={fadeUp} className="flex items-start justify-between gap-4">
          <div>
            <div className="text-sm text-muted-foreground">Interview Prep</div>
            <h1 className="mt-1 text-3xl font-medium">Practice makes perfect.</h1>
          </div>
          <div className="flex shrink-0 gap-2">
            <LiquidGlassButton tone="ghost" size="sm" onClick={() => setMockOpen(true)}>
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
              {filtered.length === 0 && activeTab === "Company-Specific" && (
                <div className="rounded-3xl border border-dashed border-border bg-card/40 p-8 text-center">
                  <Building2 className="mx-auto h-8 w-8 text-muted-foreground/40" />
                  <p className="mt-3 text-sm font-medium">No company-specific questions yet</p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    Enter a company name above and generate questions to get tailored interview prep.
                  </p>
                  <LiquidGlassButton
                    tone="primary"
                    size="sm"
                    className="mt-4"
                    onClick={() => generateMutation.mutate()}
                    disabled={generateMutation.isPending}
                  >
                    <Sparkles className="h-4 w-4" />
                    Generate company questions
                  </LiquidGlassButton>
                </div>
              )}
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

            {/* Elevator pitch */}
            {elevatorPitch && (
              <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-3">
                <div className="flex items-center gap-2">
                  <Lightbulb className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-semibold">Elevator Pitch</span>
                </div>
                <p className="text-sm leading-relaxed text-muted-foreground">{elevatorPitch}</p>
              </div>
            )}

            {/* Questions to ask interviewer */}
            {questionsToAsk && questionsToAsk.length > 0 && (
              <div className="rounded-3xl border border-border bg-card/60 p-6 space-y-3">
                <div className="flex items-center gap-2">
                  <HelpCircle className="h-4 w-4 text-muted-foreground" />
                  <span className="text-sm font-semibold">Questions to Ask</span>
                </div>
                <p className="text-xs text-muted-foreground">Ask the interviewer these at the end</p>
                <ul className="space-y-2">
                  {questionsToAsk.map((q, i) => (
                    <li key={i} className="flex items-start gap-2 text-sm">
                      <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-primary/10 text-[10px] font-semibold text-primary">
                        {i + 1}
                      </span>
                      <span className="leading-snug">{q}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

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
                    {editingStoryId === story.id ? (
                      <input
                        autoFocus
                        value={editingTitle}
                        onChange={(e) => setEditingTitle(e.target.value)}
                        onBlur={() => {
                          setStories((s) => s.map((x) => x.id === story.id ? { ...x, title: editingTitle.trim() || x.title } : x));
                          setEditingStoryId(null);
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            setStories((s) => s.map((x) => x.id === story.id ? { ...x, title: editingTitle.trim() || x.title } : x));
                            setEditingStoryId(null);
                          }
                          if (e.key === "Escape") setEditingStoryId(null);
                        }}
                        className="w-full rounded-xl border border-primary/30 bg-background px-2 py-1 text-xs font-medium focus:outline-none focus:ring-2 focus:ring-primary/30"
                      />
                    ) : (
                      <p
                        className="cursor-pointer text-xs font-medium leading-snug transition-colors hover:text-primary"
                        title="Click to edit"
                        onClick={() => { setEditingStoryId(story.id); setEditingTitle(story.title); }}
                      >
                        {story.title}
                      </p>
                    )}
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

        {/* Watch & Prepare — YouTube videos */}
        {role && (
          <motion.div variants={fadeUp} className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-medium">Watch &amp; Prepare</h2>
              <span className="text-xs text-muted-foreground">Sourced from YouTube</span>
            </div>
            {loadingVideos ? (
              <div className="flex gap-4 overflow-x-auto pb-2">
                {Array.from({ length: 4 }).map((_, i) => (
                  <div key={i} className="w-64 shrink-0 h-40 rounded-2xl bg-muted animate-pulse" />
                ))}
              </div>
            ) : (videos ?? []).length > 0 ? (
              <div className="flex gap-4 overflow-x-auto pb-2">
                {(videos ?? []).map((v) => (
                  <a
                    key={v.video_id}
                    href={v.watch_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="group w-64 shrink-0 overflow-hidden rounded-2xl border border-border bg-card/60 transition-shadow hover:shadow-md"
                  >
                    <div className="relative">
                      <img src={v.thumbnail} alt={v.title} className="h-36 w-full object-cover" />
                      <div className="absolute inset-0 flex items-center justify-center bg-black/30 opacity-0 transition-opacity group-hover:opacity-100">
                        <Play className="h-8 w-8 text-white" />
                      </div>
                    </div>
                    <div className="p-3">
                      <p className="line-clamp-2 text-xs font-medium leading-snug">{v.title}</p>
                      <p className="mt-1 text-xs text-muted-foreground">{v.channel}</p>
                    </div>
                  </a>
                ))}
              </div>
            ) : null}
          </motion.div>
        )}

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
            <LiquidGlassButton
              tone="primary"
              size="lg"
              className="shrink-0 gap-2 sm:w-auto w-full"
              onClick={() => setMockOpen(true)}
            >
              <Play className="h-4 w-4" />
              Start mock interview
            </LiquidGlassButton>
          </div>
        </motion.div>
      </motion.div>

      <AnimatePresence>
        {mockOpen && <MockInterviewModal onClose={() => setMockOpen(false)} />}
      </AnimatePresence>
    </>
  );
}
