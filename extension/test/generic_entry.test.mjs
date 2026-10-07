import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import { isStaticOrigin } from "../src/common.js";

// A signed-in unknown portal with a one-click Apply control must never be
// operated automatically before its effects can be reviewed.
for (const tagName of ["BUTTON", "A"]) {
  let submissions = 0;
  const control = { tagName, type: "button", disabled: false,
    getAttribute: () => tagName === "A" ? "#apply" : null, closest: () => null };
  const document = { forms: [], querySelectorAll: selector =>
    selector.includes("iframe") ? [] : selector.includes("a[href]") ? [control] : [] };
  const context = { window: { CareerCraftDOM: { isVisible: () => true,
    textOf: () => "Apply", delay: async () => {}, clickLike: () => submissions++ },
    addEventListener: () => {} }, document,
    location: { href: "https://careers.example/job", hostname: "careers.example" },
    URL, Date, setTimeout, console };
  vm.runInNewContext(fs.readFileSync(new URL("../src/content/drivers.js", import.meta.url), "utf8"), context);
  await assert.rejects(context.window.CareerCraftDrivers.genericDriver.run({
    task: {}, delay: async () => {}, api: { navigate: async () => {} }, panel: {},
  }), /Open the application form manually/);
  assert.equal(submissions, 0);
}

const manifest = JSON.parse(fs.readFileSync(new URL("../manifest.json", import.meta.url)));
assert(manifest.host_permissions.includes("https://app.careercraftsai.me/*"));
assert(manifest.content_scripts[0].matches.includes("https://app.careercraftsai.me/*"));
assert(isStaticOrigin("https://app.careercraftsai.me"));
const background = fs.readFileSync(new URL("../src/background.js", import.meta.url), "utf8");
assert(background.includes('"app.careercraftsai.me"'));
console.log("Generic one-click Apply blocked and production pairing permissions verified.");
