import assert from "node:assert/strict";
import { appOrigin, jobUrl, taskSenderAllowed } from "../src/common.js";

const active = { taskId: "task", tabId: 7 };
const sender = { id: "extension", frameId: 0, tab: { id: 7 }, url: "https://jobs.lever.co/company/posting" };
assert(taskSenderAllowed(sender, active, { taskId: "task" }, "extension"));
assert(!taskSenderAllowed({ ...sender, tab: { id: 8 } }, active, { taskId: "task" }, "extension"));
assert(!taskSenderAllowed({ ...sender, frameId: 1 }, active, { taskId: "task" }, "extension"));
assert(!taskSenderAllowed(sender, active, { taskId: "another" }, "extension"));
assert(!taskSenderAllowed(sender, active, { taskId: "task", url: "https://evil.example/form" }, "extension"));
assert.throws(() => jobUrl("http://localhost/form"));
assert.throws(() => jobUrl("https://127.0.0.1/form"));
assert.throws(() => appOrigin("https://user:password@app.example"));
assert.equal(appOrigin("http://localhost:3000"), "http://localhost:3000");
console.log("Task sender, frame, origin and pairing boundary checks passed.");
