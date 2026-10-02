import assert from "node:assert/strict";
import test from "node:test";

const store = new Map();
globalThis.sessionStorage = {
  getItem: (k) => (store.has(k) ? store.get(k) : null),
  setItem: (k, v) => store.set(k, String(v)),
  removeItem: (k) => store.delete(k),
};
const { setPendingJd, takePendingJd } = await import("./job-handoff.ts");

test("a remount right after arrival still gets the handed-off job description", () => {
  setPendingJd({ jdText: "Build APIs", role: "Engineer", company: "Acme" });
  assert.equal(takePendingJd()?.jdText, "Build APIs");
  assert.equal(takePendingJd()?.jdText, "Build APIs"); // second mount
  assert.equal(store.size, 0); // not left behind for a later visit
});

test("a new handoff replaces the cached one", () => {
  setPendingJd({ jdText: "First", role: "A", company: "X" });
  takePendingJd();
  setPendingJd({ jdText: "Second", role: "B", company: "Y" });
  assert.equal(takePendingJd()?.jdText, "Second");
});
