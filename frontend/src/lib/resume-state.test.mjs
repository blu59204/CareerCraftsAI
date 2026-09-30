import assert from "node:assert/strict";
import test from "node:test";
import { selectResumeScore, isCurrentAnalysis } from "./resume-state.ts";

test("saved edited snapshot replaces upload score", () => {
  assert.equal(selectResumeScore({ ats_score: 91 }, { ats_score: 60 }).ats_score, 91);
});
test("late analysis for old content or target is discarded", () => {
  const result = { documentId: "a", contentVersion: "old", jdText: "python" };
  assert.equal(isCurrentAnalysis(result, "a", "new", "python"), false);
  assert.equal(isCurrentAnalysis(result, "a", "old", "sql"), false);
  assert.equal(isCurrentAnalysis(result, "a", "old", "python"), true);
});
