import { apiClient } from "@/lib/api";
import type { ResumeFixPayload, TailoredResume } from "@/lib/resume-types";
import { tailoredResumeSchema } from "@/lib/profile-contracts";

/** Mutation-key prefix shared by every request that replaces the tailored document. */
export const RESUME_TAILORED_KEY = ["resume-tailored"] as const;

/**
 * POST /resume/tailored/{id}/fix. The response's `document_id` may differ
 * from `documentId` (a resume pinned by a pending approval is saved as a new
 * version), so callers must adopt the returned id.
 */
export async function postResumeFix(documentId: string, body: ResumeFixPayload): Promise<TailoredResume> {
  // Re-renders the PDF server-side; allow more than the default 30s.
  const { data } = await apiClient.post<TailoredResume>(`/resume/tailored/${documentId}/fix`, body, {
    timeout: 60_000,
  });
  return tailoredResumeSchema.parse(data) as TailoredResume;
}
