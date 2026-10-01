import { z } from "zod";

export const profileResultSchema = z.object({
  run_id: z.string(), status: z.string(), warnings: z.array(z.string()),
  sections: z.array(z.object({
    section: z.enum(["headline", "about", "experience", "skills"]),
    before: z.string(), after: z.string(), reason: z.string(),
    source_quotes: z.array(z.string()), gaps: z.array(z.string()),
  })),
});
export type ProfileResult = z.infer<typeof profileResultSchema>;

export const estimateSchema = z.object({
  label: z.string(), mode: z.enum(["general", "target_job"]), estimator_version: z.string(),
  content_version: z.string(), target_hash: z.string(), composite_score: z.number().min(0).max(100),
  sub_scores: z.record(z.string(), z.object({ score: z.number().min(0).max(100).nullable(), weight: z.number(), applicable: z.boolean(), evidence: z.string() })),
  issues: z.array(z.object({ code: z.string(), section: z.string(), severity: z.enum(["info", "warning", "error"]), message: z.string(), suggestion: z.string() })),
  match_method: z.string(), matched_keywords: z.array(z.string()), missing_keywords: z.array(z.string()), suggestions: z.array(z.string()),
});
export const scoreAnalysisSchema = z.object({
  composite_score: z.number().min(0).max(100), matched_keywords: z.array(z.string()),
  missing_keywords: z.array(z.string()), suggestions: z.array(z.string()),
  content_version: z.string(), estimate: estimateSchema,
});
const entry = z.object({ index: z.number(), heading: z.string(), section: z.string(), role: z.string(), employer: z.string(), location: z.string(), start: z.string(), end: z.string(), issues: z.array(z.enum(["missing_employer", "truncated_employer", "missing_dates"])) });
export const tailoredResumeSchema = z.object({
  document_id: z.string(), template: z.enum(["modern", "classic", "technical"]),
  resume_markdown: z.string(), content_version: z.string(), revision: z.number(),
  ats_score: z.number().nullable(), estimate: estimateSchema.nullable(),
  summary: z.string().nullable(), keywords_matched: z.array(z.string()), keywords_missing: z.array(z.string()),
  changes_made: z.array(z.string()), warnings: z.array(z.string()),
  contact_suggestions: z.record(z.string(), z.string()), display_name: z.string(),
  page_target: z.union([z.literal(1), z.literal(2)]), page_count: z.number().nullable(),
  review: z.object({ contact: z.object({ email: z.string(), phone: z.string(), location: z.string(), linkedin: z.string(), github: z.string(), portfolio: z.string() }), experience: z.array(entry), education: z.array(entry), has_education_section: z.boolean(), issues: z.array(z.object({ code: z.enum(["missing_email", "missing_phone", "missing_employer", "truncated_employer", "missing_dates", "missing_education"]), message: z.string(), index: z.number().optional() })) }),
});

// Mirrors backend services/github_profile.analyze(): skills are evidence
// objects and description may be null.
const project = z.object({
  name: z.string().nullish(), title: z.string().nullish(),
  reason: z.string().nullish(), description: z.string().nullish(),
  url: z.string().nullish(),
}).passthrough();
export const githubProfileSchema = z.object({
  skills: z.array(z.object({ name: z.string() }).passthrough()), top_repos: z.array(project),
  suggested_projects: z.array(z.union([z.string(), project])),
});
