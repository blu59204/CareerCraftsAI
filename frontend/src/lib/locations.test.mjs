import assert from "node:assert/strict";
import test from "node:test";
import { suggestLocations } from "./locations.ts";

test("prefix matches come first, then contains", () => {
  const out = suggestLocations("hyd");
  assert.equal(out[0], "Hyderabad, India");
  assert.ok(suggestLocations("india").length > 1);
});

test("old city names find the current one", () => {
  assert.equal(suggestLocations("bangalore")[0], "Bengaluru, India");
  assert.equal(suggestLocations("Gurgaon")[0], "Gurugram, India");
  assert.equal(suggestLocations("bangal")[0], "Bengaluru, India"); // partial old name
});

test("already-picked places are not suggested again", () => {
  assert.ok(!suggestLocations("pu", ["Pune, India"]).includes("Pune, India"));
  assert.equal(suggestLocations("", [], 3).length, 3);
});
