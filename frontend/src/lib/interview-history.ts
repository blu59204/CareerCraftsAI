export interface InterviewSessionItem {
  id: string;
  role: string;
  company: string | null;
  status: string;
  overall_score: number | null;
  question_count: number;
  answered_count: number;
  started_at: string;
  completed_at: string | null;
}

export interface StoredQuestion {
  question?: string;
  type?: string;
}

export interface StoredAnswer {
  question_index: number;
  answer_text: string;
}

export interface InterviewSessionDetail {
  id: string;
  questions: StoredQuestion[];
  answers: StoredAnswer[];
  scores: number[];
}

/** One question with the member's answer and score, in question order. */
export interface ReviewRow {
  index: number;
  question: string;
  answer: string | null;
  score: number | null;
}

/**
 * Pair each stored answer and score with its question. Answers and scores are
 * parallel arrays in the order answered, which can differ from question order
 * (and a retried answer replaces its earlier one), so match on question_index.
 */
export function reviewRows(detail: InterviewSessionDetail): ReviewRow[] {
  const answers = detail.answers ?? [];
  return (detail.questions ?? []).map((question, index) => {
    const at = answers.findIndex((entry) => entry.question_index === index);
    return {
      index,
      question: question.question ?? "Question unavailable",
      answer: at >= 0 ? answers[at].answer_text : null,
      score: at >= 0 && typeof detail.scores?.[at] === "number" ? detail.scores[at] : null,
    };
  });
}

/** Average score change from the oldest to the newest completed session, or null. */
export function scoreTrend(sessions: InterviewSessionItem[]): number | null {
  const scored = sessions
    .filter((s) => s.status === "completed" && s.overall_score !== null)
    .sort((a, b) => a.started_at.localeCompare(b.started_at));
  if (scored.length < 2) return null;
  return (scored[scored.length - 1].overall_score as number) - (scored[0].overall_score as number);
}
