"use client";

import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";
import { motion } from "motion/react";
import {
  ArrowCounterClockwise,
  Briefcase,
  Buildings,
  ChatCircleText,
  CircleNotch,
  Lightbulb,
  PaperPlaneTilt,
  Play,
  Target,
  Trophy,
} from "@phosphor-icons/react";
import { toast } from "sonner";
import { apiClient, getApiErrorMessage, UserFacingError } from "@/lib/api";
import { waitForAgentRun } from "@/lib/agent-run";
import {
  Bezel,
  Eyebrow,
  Field,
  Hairline,
  Input,
  IslandButton,
  PanelTitle,
  Reveal,
  RevealGroup,
  Segmented,
  StatusPill,
  Textarea,
  listItem,
} from "@/components/vanguard";
import { DictationButton } from "./DictationButton";
import { ScoreRing, scoreTone } from "./ScoreRing";

type QuestionType = "behavioral" | "technical" | "situational";

interface Question {
  type: string;
  question: string;
  context?: string;
}

interface AnswerFeedback {
  score: number;
  rating: string;
  tips: string[];
}

interface SessionSummary {
  overall_score: number;
  count: number;
  rating: string;
}

/** Client-side fallback mirroring compute_session_summary in the backend. */
function summarize(feedbacks: AnswerFeedback[]): SessionSummary {
  const scores = feedbacks.map((fb) => Number(fb.score) || 0);
  const overall = scores.length ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) : 0;
  const rating = overall > 75 ? "excellent" : overall > 50 ? "good" : overall > 25 ? "fair" : "poor";
  return { overall_score: overall, count: scores.length, rating };
}

const QUESTION_TYPES: ReadonlyArray<{ value: QuestionType; label: string }> = [
  { value: "behavioral", label: "Behavioral" },
  { value: "technical", label: "Technical" },
  { value: "situational", label: "Situational" },
];

const PRINCIPLES: ReadonlyArray<{ title: string; body: string }> = [
  { title: "Clarity", body: "Lead with the outcome, then the path you took to get there." },
  { title: "Relevance", body: "Tie every example back to the role you are interviewing for." },
  { title: "Depth", body: "Name the trade-offs, the numbers and what you would change next time." },
];

function countWords(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

/**
 * Feedback recap. Each entry keeps a single "Qn: score/100 (rating)" text
 * node — the live journey test asserts "Q1:" and "/100" are each unique.
 */
function FeedbackList({ feedbacks }: { feedbacks: AnswerFeedback[] }) {
  return (
    <section aria-labelledby="coach-feedback-heading" className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <Eyebrow className="mb-3">Scored answers</Eyebrow>
          <h2 id="coach-feedback-heading" className="font-geist text-2xl font-semibold tracking-[-0.03em] text-foreground">
            Previous Feedback
          </h2>
        </div>
        <span className="text-xs tabular-nums text-muted-foreground">{feedbacks.length} answered</span>
      </div>
      <RevealGroup className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {feedbacks.map((fb, i) => (
          <motion.div key={i} variants={listItem} className={i === 0 && feedbacks.length % 2 === 1 ? "md:col-span-2" : undefined}>
            <Bezel size="md" coreClassName="flex gap-5 p-5 md:p-6">
              <ScoreRing value={fb.score} size={60} label={`Answer ${i + 1} score`} />
              <div className="min-w-0 flex-1">
                <p className="font-geist text-[15px] font-semibold capitalize tabular-nums tracking-[-0.015em] text-foreground">
                  Q{i + 1}: {fb.score}/100 <span className="font-normal text-muted-foreground">({fb.rating})</span>
                </p>
                {fb.tips.length > 0 ? (
                  <ul className="mt-3 space-y-2">
                    {fb.tips.map((tip, j) => (
                      <li key={j} className="flex gap-2.5 text-sm leading-6 text-muted-foreground">
                        <Lightbulb size={15} weight="light" aria-hidden className="mt-1 shrink-0 text-foreground/60" />
                        <span>{tip}</span>
                      </li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </Bezel>
          </motion.div>
        ))}
      </RevealGroup>
    </section>
  );
}

/**
 * Live Interview Coach session: start → answer → score → next question →
 * summary. Logic moved intact from the former /interview page.
 */
export function MockInterviewPanel() {
  const [role, setRole] = useState("");
  const [company, setCompany] = useState("");
  const [questionType, setQuestionType] = useState<QuestionType>("behavioral");
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentQuestion, setCurrentQuestion] = useState<Question | null>(null);
  const [questionIndex, setQuestionIndex] = useState(0);
  const [answer, setAnswer] = useState("");
  const [feedbacks, setFeedbacks] = useState<AnswerFeedback[]>([]);
  const [summary, setSummary] = useState<SessionSummary | null>(null);

  const startSession = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<{ run_id: string }>("/interview/session/start", {
        role,
        company: company || undefined,
        question_type: questionType,
      });
      const run = await waitForAgentRun(data.run_id);
      const output = (run.output ?? {}) as { session_id?: string; questions?: Question[] };
      if (run.status === "failed" || !output.session_id || !output.questions?.length) {
        throw new UserFacingError("We couldn’t start the session. Check your active AI model in Settings and try again.");
      }
      return { sessionId: output.session_id, question: output.questions[0] };
    },
    onSuccess: ({ sessionId: id, question }) => {
      setSessionId(id);
      setCurrentQuestion(question);
      setQuestionIndex(0);
      toast.success("Session started!");
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Failed to start session")),
  });

  const submitAnswer = useMutation({
    mutationFn: async () => {
      const { data } = await apiClient.post<{ run_id: string }>(`/interview/session/${sessionId}/answer`, {
        question_index: questionIndex,
        answer_text: answer,
      });
      const run = await waitForAgentRun(data.run_id);
      if (run.status === "failed") {
        throw new UserFacingError("We couldn’t score that answer. Please try again.");
      }
      // The agent saved the score on the session; read it back for the next
      // question, or the summary once every question has an answer.
      const { data: session } = await apiClient.get<{
        questions: Question[] | null;
        summary: SessionSummary | null;
        status: string | null;
      }>(`/interview/session/${sessionId}/summary`);
      const questions = session.questions ?? [];
      return {
        feedback: run.output as unknown as AnswerFeedback,
        nextQuestion: questions[questionIndex + 1] ?? null,
        summary: session.summary,
      };
    },
    onSuccess: ({ feedback, nextQuestion, summary: sessionSummary }) => {
      setFeedbacks((prev) => [...prev, feedback]);
      setAnswer("");
      if (nextQuestion) {
        setCurrentQuestion(nextQuestion);
        setQuestionIndex(questionIndex + 1);
      } else {
        setSummary(sessionSummary ?? summarize(feedbacks.concat(feedback)));
        setCurrentQuestion(null);
      }
    },
    onError: (error) => toast.error(getApiErrorMessage(error, "Failed to submit answer")),
  });

  const handleSubmitAnswer = () => {
    if (answer.trim().split(/\s+/).length < 10) {
      toast.error("Please write at least 10 words");
      return;
    }
    submitAnswer.mutate();
  };

  const handleStart = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!role.trim() || startSession.isPending) return;
    startSession.mutate();
  };

  const resetSession = () => {
    setSessionId(null);
    setCurrentQuestion(null);
    setQuestionIndex(0);
    setAnswer("");
    setFeedbacks([]);
    setSummary(null);
  };

  const words = countWords(answer);
  const averageScore = feedbacks.length > 0 ? Math.round(feedbacks.reduce((sum, fb) => sum + (Number(fb.score) || 0), 0) / feedbacks.length) : null;

  /* ── Session complete ─────────────────────────────────────────────── */
  if (summary) {
    return (
      <div className="space-y-16 md:space-y-20">
        <Reveal>
          <Bezel lifted tone="primary" coreClassName="grid grid-cols-1 gap-10 p-8 md:grid-cols-12 md:items-center md:p-12">
            <div className="md:col-span-7">
              <div className="flex items-center gap-3">
                <span aria-hidden className="grid h-12 w-12 place-items-center rounded-full bg-warning/10 text-warning ring-1 ring-warning/25">
                  <Trophy size={22} weight="light" />
                </span>
                <Eyebrow tone="primary">Session summary</Eyebrow>
              </div>
              <h2 className="mt-6 font-geist text-4xl font-semibold tracking-[-0.04em] text-foreground md:text-5xl">Session Complete</h2>
              <p className="mt-4 max-w-[46ch] text-[15px] capitalize leading-7 text-muted-foreground">
                {summary.rating} · {summary.count} questions answered
              </p>
              <div className="mt-8 flex flex-wrap gap-3">
                <IslandButton onClick={resetSession} icon={<ArrowCounterClockwise size={15} weight="light" />}>
                  Practice again
                </IslandButton>
              </div>
            </div>
            <div className="flex flex-col items-start gap-3 md:col-span-5 md:items-center">
              <ScoreRing value={summary.overall_score} size={168} stroke={9} label="Overall score" />
              <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">Overall · out of 100</p>
            </div>
          </Bezel>
        </Reveal>
        {feedbacks.length > 0 ? <FeedbackList feedbacks={feedbacks} /> : null}
      </div>
    );
  }

  /* ── Setup ────────────────────────────────────────────────────────── */
  if (!sessionId) {
    return (
      <div className="grid grid-cols-1 gap-10 lg:grid-cols-12 lg:gap-14">
        <Reveal className="lg:col-span-5">
          <Eyebrow>Live practice loop</Eyebrow>
          <p className="mt-6 max-w-[16ch] text-balance font-geist text-4xl font-semibold leading-[1.02] tracking-[-0.04em] text-foreground md:text-5xl">
            Rehearse under real pressure.
          </p>
          <p className="mt-5 max-w-[46ch] text-[15px] leading-7 text-muted-foreground">
            The coach asks one question at a time, scores each answer and adapts the next question to how you did.
          </p>
          <Hairline className="my-8" />
          <ul className="space-y-5">
            {PRINCIPLES.map((p, i) => (
              <li key={p.title} className="flex gap-4">
                <span className="font-geist-mono text-xs tabular-nums text-muted-foreground/70">0{i + 1}</span>
                <div>
                  <p className="text-sm font-semibold tracking-[-0.01em] text-foreground">{p.title}</p>
                  <p className="mt-1 text-sm leading-6 text-muted-foreground">{p.body}</p>
                </div>
              </li>
            ))}
          </ul>
        </Reveal>

        <Reveal delay={0.08} className="lg:col-span-7">
          <Bezel lifted coreClassName="p-6 md:p-10">
            <form onSubmit={handleStart} className="space-y-7" aria-describedby="coach-setup-hint">
              <PanelTitle title="Set up your session" icon={<Target size={16} weight="light" />} />
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <Field label="Target role" hint="Required">
                  {(id) => (
                    <Input
                      id={id}
                      type="text"
                      placeholder="Target Role *"
                      value={role}
                      onChange={(e) => setRole(e.target.value)}
                      required
                      autoComplete="organization-title"
                      leading={<Briefcase size={16} weight="light" />}
                    />
                  )}
                </Field>
                <Field label="Company">
                  {(id) => (
                    <Input
                      id={id}
                      type="text"
                      placeholder="Company (optional)"
                      value={company}
                      onChange={(e) => setCompany(e.target.value)}
                      autoComplete="organization"
                      leading={<Buildings size={16} weight="light" />}
                    />
                  )}
                </Field>
              </div>
              <div className="space-y-2">
                <p id="coach-question-type" className="pl-1 text-[12px] font-medium tracking-[-0.005em] text-muted-foreground">
                  Question type
                </p>
                <Segmented
                  asTabs={false}
                  ariaLabel="Question type"
                  value={questionType}
                  onChange={setQuestionType}
                  options={QUESTION_TYPES}
                />
              </div>
              <Hairline />
              <div className="flex flex-col-reverse gap-4 sm:flex-row sm:items-center sm:justify-between">
                <p id="coach-setup-hint" className="text-xs leading-5 text-muted-foreground">
                  Answers need at least 10 words to be scored.
                </p>
                <IslandButton
                  type="submit"
                  size="lg"
                  disabled={!role.trim() || startSession.isPending}
                  trailing={startSession.isPending ? <CircleNotch size={17} weight="light" className="animate-spin" /> : <Play size={17} weight="light" />}
                >
                  {startSession.isPending ? "Starting..." : "Start Session"}
                </IslandButton>
              </div>
            </form>
          </Bezel>
        </Reveal>
      </div>
    );
  }

  /* ── Active session ───────────────────────────────────────────────── */
  return (
    <div className="space-y-16 md:space-y-20">
      {currentQuestion ? (
        <div className="grid grid-cols-1 gap-8 lg:grid-cols-12 lg:gap-14">
          <Reveal className="lg:col-span-4">
            <div className="lg:sticky lg:top-24">
              <Eyebrow tone="primary">In session</Eyebrow>
              <p className="mt-6 font-geist text-5xl font-semibold tabular-nums leading-none tracking-[-0.05em] text-foreground md:text-6xl">
                Question {feedbacks.length + 1}
              </p>
              <dl className="mt-8 space-y-4 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Role</dt>
                  <dd className="truncate font-medium text-foreground">{role}</dd>
                </div>
                {company ? (
                  <div className="flex items-center justify-between gap-4">
                    <dt className="text-muted-foreground">Company</dt>
                    <dd className="truncate font-medium text-foreground">{company}</dd>
                  </div>
                ) : null}
              </dl>
              <Hairline className="my-4" />
              <dl className="space-y-4 text-sm">
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Answered</dt>
                  <dd className="font-medium tabular-nums text-foreground">{feedbacks.length}</dd>
                </div>
                <div className="flex items-center justify-between gap-4">
                  <dt className="text-muted-foreground">Average score</dt>
                  <dd className="font-medium tabular-nums text-foreground">{averageScore ?? "—"}</dd>
                </div>
              </dl>
              {averageScore !== null ? (
                <div className="mt-6">
                  <StatusPill tone={scoreTone(averageScore)}>
                    {averageScore >= 80 ? "Strong pace" : averageScore >= 60 ? "Solid — keep going" : "Room to sharpen"}
                  </StatusPill>
                </div>
              ) : null}
            </div>
          </Reveal>

          <Reveal delay={0.06} className="lg:col-span-8">
            <Bezel lifted coreClassName="p-6 md:p-10">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill tone="primary" icon={<ChatCircleText size={12} weight="light" />}>
                  <span className="capitalize">{currentQuestion.type || questionType}</span>
                </StatusPill>
              </div>
              <p
                data-testid="interview-question"
                className="mt-6 text-balance font-geist text-2xl font-medium leading-[1.25] tracking-[-0.025em] text-foreground md:text-[2rem]"
              >
                {currentQuestion.question}
              </p>
              {currentQuestion.context ? (
                <p className="mt-4 max-w-[62ch] text-sm leading-6 text-muted-foreground">{currentQuestion.context}</p>
              ) : null}

              <Hairline className="my-8" />

              <label htmlFor="coach-answer" className="block pl-1 text-[12px] font-medium tracking-[-0.005em] text-muted-foreground">
                Your answer
              </label>
              <Textarea
                id="coach-answer"
                trayClassName="mt-2"
                value={answer}
                onChange={(e) => setAnswer(e.target.value)}
                placeholder="Type your answer (minimum 10 words)..."
                rows={7}
                className="min-h-44 resize-none"
                aria-describedby="coach-answer-count"
              />
              <div className="mt-3">
                <DictationButton current={answer} onText={setAnswer} />
              </div>
              <div className="mt-5 flex flex-col-reverse gap-4 sm:flex-row sm:items-center sm:justify-between">
                <p id="coach-answer-count" aria-live="polite" className="text-xs tabular-nums text-muted-foreground">
                  <span className={words >= 10 ? "text-success" : undefined}>{words}</span> words · minimum 10
                </p>
                <IslandButton
                  onClick={handleSubmitAnswer}
                  disabled={submitAnswer.isPending}
                  trailing={submitAnswer.isPending ? <CircleNotch size={15} weight="light" className="animate-spin" /> : <PaperPlaneTilt size={15} weight="light" />}
                >
                  {submitAnswer.isPending ? "Submitting..." : "Submit Answer"}
                </IslandButton>
              </div>
            </Bezel>
          </Reveal>
        </div>
      ) : null}

      {feedbacks.length > 0 ? <FeedbackList feedbacks={feedbacks} /> : null}
    </div>
  );
}
