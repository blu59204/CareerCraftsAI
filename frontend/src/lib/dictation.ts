/**
 * Browser speech-to-text for interview answers. Uses the Web Speech API where
 * it exists (Chrome, Edge, Safari); nothing is sent to CareerCraft, and where
 * the API is missing the caller keeps its typed input.
 */

/** Append a spoken phrase to the text already in the box, spaced cleanly. */
export function appendTranscript(existing: string, spoken: string): string {
  const phrase = spoken.trim();
  if (!phrase) return existing;
  if (!existing.trim()) return phrase;
  return `${existing.replace(/\s+$/, "")} ${phrase}`;
}

/** Plain-English reason for a recognition error code, or null to stay silent. */
export function dictationErrorMessage(code: string): string | null {
  switch (code) {
    case "not-allowed":
    case "service-not-allowed":
      return "Microphone access is blocked. Allow it in your browser's site settings to dictate.";
    case "audio-capture":
      return "No microphone was found.";
    case "network":
      return "Speech recognition needs a network connection.";
    case "no-speech":
    case "aborted":
      return null;
    default:
      return "Dictation stopped unexpectedly. You can keep typing.";
  }
}
