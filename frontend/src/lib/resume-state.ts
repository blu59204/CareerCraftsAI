export function selectResumeScore<T extends { ats_score: number | null }, U extends { ats_score: number | null }>(
  saved: T | null, uploaded: U | null,
): T | U | null {
  return saved ?? uploaded;
}

export function isCurrentAnalysis(
  analysis: { documentId: string; contentVersion?: string; jdText: string },
  documentId: string | null | undefined, contentVersion: string | undefined, jdText: string,
): boolean {
  return analysis.documentId === documentId && analysis.contentVersion === contentVersion && analysis.jdText === jdText.trim();
}
