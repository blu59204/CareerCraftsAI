type JobAtsAnalysis = {
  composite_score: number;
  matched_keywords: string[];
  missing_keywords: string[];
  suggestions: string[];
};

type ResumeDocumentAts = {
  ats_score: number | null;
  ats_data: {
    matched_keywords?: string[];
    missing_keywords?: string[];
  } | null;
};

export function getResumeInsightData(
  jobAnalysis: JobAtsAnalysis | null,
  resume: ResumeDocumentAts | null,
) {
  if (jobAnalysis) {
    return {
      score: jobAnalysis.composite_score,
      scoreLabel: "Estimated ATS compatibility",
      matched: jobAnalysis.matched_keywords,
      missing: jobAnalysis.missing_keywords,
      suggestions: jobAnalysis.suggestions,
    };
  }

  return {
    score: resume?.ats_score ?? null,
    scoreLabel: resume?.ats_score != null ? "Estimated ATS compatibility" : "Estimated ATS compatibility",
    matched: [],
    missing: [],
    suggestions: [],
  };
}
