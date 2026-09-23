import assert from "node:assert/strict";
import test from "node:test";

import { getResumeInsightData } from "./resume-insights.ts";

test("job-specific ATS analysis replaces generic upload metrics", () => {
  const result = getResumeInsightData(
    {
      composite_score: 82,
      matched_keywords: ["Python"],
      missing_keywords: ["AWS"],
      suggestions: ["Add AWS only if it reflects real experience."],
    },
    {
      ats_score: 61,
      ats_data: { matched_keywords: ["React"], missing_keywords: ["Docker"] },
    },
  );

  assert.deepEqual(result, {
    score: 82,
    scoreLabel: "Job match",
    matched: ["Python"],
    missing: ["AWS"],
    suggestions: ["Add AWS only if it reflects real experience."],
  });
});

test("without a job analysis, only the real baseline score is shown", () => {
  assert.deepEqual(
    getResumeInsightData(null, {
      ats_score: 61,
      ats_data: { matched_keywords: ["React"], missing_keywords: ["Docker"] },
    }),
    { score: 61, scoreLabel: "Baseline ATS", matched: [], missing: [], suggestions: [] },
  );
});

test("missing resume data does not invent scores, keywords, or suggestions", () => {
  assert.deepEqual(getResumeInsightData(null, null), {
    score: null,
    scoreLabel: "ATS score",
    matched: [],
    missing: [],
    suggestions: [],
  });
});
