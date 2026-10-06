import { apiClient, UserFacingError } from "@/lib/api";

export async function uploadResume(file: File) {
  if (file.size > 10 * 1024 * 1024) throw new UserFacingError("Resume must be under 10 MB.");
  if (!/\.(pdf|docx|txt)$/i.test(file.name)) throw new UserFacingError("Choose a PDF, DOCX, or TXT resume. Convert older DOC files to DOCX first.");
  const body = new FormData();
  body.append("file", file);
  body.append("doc_type", "resume");
  body.append("is_primary", "true");
  return (await apiClient.post("/rag/upload", body, {
    headers: { "Content-Type": "multipart/form-data" }, timeout: 180000,
  })).data as { id: string; filename: string; warning?: string };
}
