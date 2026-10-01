export function isCurrentAnalysis(
  analysis: { documentId: string; contentVersion?: string; jdText: string },
  documentId: string | null | undefined, contentVersion: string | undefined, jdText: string,
): boolean {
  return analysis.documentId === documentId && analysis.contentVersion === contentVersion && analysis.jdText === jdText.trim();
}
