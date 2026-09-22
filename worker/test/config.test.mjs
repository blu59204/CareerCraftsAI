import assert from "node:assert/strict";
import test from "node:test";

process.env.INTERNAL_SECRET = "test-secret";
const { resolveInternalSecret } = await import("../dist/config.js");

test("prefers INTERNAL_SECRET over APP_SECRET_KEY", () => {
  assert.equal(
    resolveInternalSecret({ INTERNAL_SECRET: "internal", APP_SECRET_KEY: "app" }),
    "internal"
  );
});

test("rejects missing internal authentication", () => {
  assert.throws(
    () => resolveInternalSecret({}),
    /INTERNAL_SECRET\/APP_SECRET_KEY not set/
  );
});
