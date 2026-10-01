import assert from "node:assert/strict";
import test from "node:test";
import { isCurrentAnalysis } from "./resume-state.ts";

test("upload score cannot be used for the saved tailored document", () => {
  const upload = { documentId: "upload", contentVersion: "old", jdText: "" };
  assert.equal(isCurrentAnalysis(upload, "tailored", "new", ""), false);
});
test("late analysis for old content or target is discarded", () => {
  const result = { documentId: "a", contentVersion: "old", jdText: "python" };
  assert.equal(isCurrentAnalysis(result, "a", "new", "python"), false);
  assert.equal(isCurrentAnalysis(result, "a", "old", "sql"), false);
  assert.equal(isCurrentAnalysis(result, "a", "old", "python"), true);
});
