import assert from "node:assert/strict";
import test from "node:test";
import { appendTranscript, dictationErrorMessage } from "./dictation.ts";

test("spoken text is appended with one space, never doubled", () => {
  assert.equal(appendTranscript("", " hello there "), "hello there");
  assert.equal(appendTranscript("I led a team.  ", "We shipped it"), "I led a team. We shipped it");
  assert.equal(appendTranscript("Existing", "   "), "Existing");
});

test("silence is not an error, a blocked microphone is explained", () => {
  assert.equal(dictationErrorMessage("no-speech"), null);
  assert.match(dictationErrorMessage("not-allowed") ?? "", /Allow it/);
  assert.ok(dictationErrorMessage("something-new"));
});
