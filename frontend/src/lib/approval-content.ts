/** Null means untouched; an empty edited draft is an invalid approval. */
export function approvalContent(original: string, edited: string | null): string {
  return edited ?? original;
}
export function approvalEdits(approved: boolean, edited: string | null) {
  if (!approved || edited === null) return undefined;
  if (!edited.trim()) throw new Error("The approved content cannot be empty");
  return { body: edited };
}
