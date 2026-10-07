import assert from "node:assert/strict";
import test from "node:test";
import { parseCsv } from "./csv.ts";
import { approvalContent, approvalEdits } from "./approval-content.ts";
import { applicationFilterParams } from "./application-filters.ts";
import { useAgentStore } from "../store/agentStore.ts";

test("quoted CSV fields preserve commas, multiline text, and escaped quotes", () => {
  assert.deepEqual(parseCsv('name,email,company\r\n"Doe, Jane",jane@x.co,"Acme ""Labs""\nIndia"\r\n'), [["name", "email", "company"], ["Doe, Jane", "jane@x.co", 'Acme "Labs"\nIndia']]);
  assert.throws(() => parseCsv('"unfinished'), /Unclosed/);
});

test("approval preview and payload use the same edited draft, rejecting blank approvals", () => {
  const edited = "Reviewed new content";
  assert.equal(approvalContent("Original", edited), approvalEdits(true, edited).body);
  assert.equal(approvalContent("Original", null), "Original");
  assert.throws(() => approvalEdits(true, "  "), /empty/);
  assert.equal(approvalEdits(false, "  "), undefined);
});

test("export uses every active list filter, including city and posting date", () => {
  assert.deepEqual(applicationFilterParams({ status: "saved", source: "linkedin", location: "Bangalore", postedWithinDays: 7, minMatch: 70, q: "  Engineer  ", foundAfter: "2026-01-01", foundBefore: "2026-02-01", sort: "match_desc" }), { status: "saved", source: "linkedin", location: "Bangalore", posted_within_days: 7, min_match: 70, q: "Engineer", found_after: "2026-01-01", found_before: "2026-02-01", sort: "match_desc" });
});

test("account transitions clear private runs and restore only that owner's active marker", () => {
  const data = new Map();
  globalThis.window = {};
  globalThis.localStorage = { getItem: (key) => data.get(key) ?? null, setItem: (key, value) => data.set(key, value), removeItem: (key) => data.delete(key) };
  const store = () => useAgentStore.getState();
  store().setOwner("A"); store().initRun("A-private"); store().setCheckpoint("A-private", { body: "private" });
  const oldGeneration = store().generation;
  store().setOwner("B");
  assert.notEqual(store().generation, oldGeneration);
  store().addEvent("A-private", "checkpoint", { body: "late secret" });
  store().setCheckpoint("A-private", { body: "late secret" });
  assert.deepEqual(store().runs, {}); assert.equal(store().activeRunId, null);
  store().initRun("B-current");
  store().initRun("B-old"); store().setActiveRun("B-current"); store().setComplete("B-old", {});
  assert.equal(data.get("cc_active_run_id:B"), "B-current");
  store().setCheckpoint("B-current", { body: "pending" }); store().setRunStatus("B-current", "expired");
  assert.equal(store().runs["B-current"].pendingAction, null); assert.equal(data.has("cc_active_run_id:B"), false);
  store().setOwner("A"); assert.equal(store().activeRunId, "A-private");
  delete globalThis.window; delete globalThis.localStorage;
  store().setOwner(null);
});
