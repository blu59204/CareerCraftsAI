import assert from "node:assert/strict";
import test from "node:test";
import { reviewRows, scoreTrend } from "./interview-history.ts";

test("answers and scores are matched to their question, not their position", () => {
  const rows = reviewRows({
    id: "s",
    questions: [{ question: "Q1" }, { question: "Q2" }, { question: "Q3" }],
    // Q2 was answered first, then Q1; Q3 was skipped.
    answers: [
      { question_index: 1, answer_text: "second" },
      { question_index: 0, answer_text: "first" },
    ],
    scores: [70, 90],
  });
  assert.deepEqual(
    rows.map((r) => [r.question, r.answer, r.score]),
    [
      ["Q1", "first", 90],
      ["Q2", "second", 70],
      ["Q3", null, null],
    ],
  );
});

test("trend compares the first and latest completed sessions", () => {
  const item = (started_at, status, overall_score) => ({
    id: started_at, role: "r", company: null, status, overall_score,
    question_count: 3, answered_count: 3, started_at, completed_at: null,
  });
  assert.equal(scoreTrend([item("2026-01-03", "completed", 82), item("2026-01-01", "completed", 60)]), 22);
  assert.equal(scoreTrend([item("2026-01-01", "completed", 60), item("2026-01-02", "in_progress", null)]), null);
});
