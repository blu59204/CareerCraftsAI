// Shared types for the tailored-resume review / fix flow.
// Mirrors backend/app/api/v1/resume.py and backend/app/services/resume_structure.py.

export type ResumeTemplateId = "modern" | "classic" | "technical";

/** Contact line fields. All strings; "" when absent. */
export interface ContactFields {
  email: string;
  phone: string;
  location: string;
  linkedin: string;
  github: string;
  portfolio: string;
}

export type ContactFieldKey = keyof ContactFields;

/** Per-entry issue codes found on a parsed experience/education entry. */
export type ReviewEntryIssueCode = "missing_employer" | "truncated_employer" | "missing_dates";

/** Resume-wide issue codes reported by review_resume(). */
export type ReviewIssueCode =
  | "missing_email"
  | "missing_phone"
  | "missing_employer"
  | "truncated_employer"
  | "missing_dates"
  | "missing_education";

/**
 * A parsed `### Role | Employer | Location | Dates` entry.
 * For education entries, `role` is the degree and `employer` the institution.
 * `index` is per kind (experience and education are numbered separately).
 */
export interface ReviewEntry {
  index: number;
  heading: string;
  section: string;
  role: string;
  employer: string;
  location: string;
  start: string;
  end: string;
  issues: ReviewEntryIssueCode[];
}

export interface ReviewIssue {
  code: ReviewIssueCode;
  message: string;
  /** Experience entry index, when the issue belongs to a specific role. */
  index?: number;
}

export interface ResumeReview {
  contact: ContactFields;
  experience: ReviewEntry[];
  education: ReviewEntry[];
  has_education_section: boolean;
  issues: ReviewIssue[];
}

/** GET /resume/tailored/{id} and POST /resume/tailored/{id}/fix response. */
export interface TailoredResume {
  document_id: string;
  template: ResumeTemplateId;
  resume_markdown: string;
  summary: string | null;
  ats_score: number | null;
  keywords_matched: string[];
  keywords_missing: string[];
  changes_made: string[];
  warnings: string[];
  review: ResumeReview;
  /** Pre-fill values from the user's profile; may be {} when unavailable. */
  contact_suggestions: Partial<ContactFields>;
}

/** POST /resume/optimize response. */
export interface ResumeOptimizeResponse {
  run_id: string;
  status: string;
  template?: ResumeTemplateId | string;
  pdf_available?: boolean;
  pdf_document_id?: string | null;
  resume_markdown?: string | null;
  summary?: string | null;
  ats_score?: number | null;
  keywords_matched?: string[];
  keywords_missing?: string[];
  changes_made?: string[];
  warnings?: string[];
  review?: ResumeReview | null;
  contact_suggestions?: Partial<ContactFields>;
}

export interface ExperienceFix {
  index: number;
  role?: string;
  employer?: string;
  location?: string;
  start?: string;
  end?: string;
}

/** Omit `index` to add a new education entry. */
export interface EducationFix {
  index?: number;
  degree?: string;
  institution?: string;
  location?: string;
  start?: string;
  end?: string;
  details?: string;
}

/** POST /resume/tailored/{id}/fix body. Every field is optional. */
export interface ResumeFixPayload {
  /** Full manual edit of the markdown (max 30000 chars). */
  resume_markdown?: string;
  /** Re-render in another template (no LLM call). */
  template?: ResumeTemplateId;
  /** "" removes a field; omitted keeps it. */
  contact?: Partial<ContactFields>;
  experience?: ExperienceFix[];
  education?: EducationFix[];
  /** Default true: saves facts for future tailoring runs. */
  remember?: boolean;
}
