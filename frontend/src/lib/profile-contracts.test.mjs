import assert from "node:assert/strict";
import test from "node:test";
import { githubProfileSchema, profileResultSchema } from "./profile-contracts.ts";

test("malformed model or integration responses fail validation", () => {
  assert.equal(profileResultSchema.safeParse({ sections: [{ after: 2 }] }).success, false);
  assert.equal(githubProfileSchema.safeParse({ skills: "Python" }).success, false);
  assert.equal(githubProfileSchema.safeParse({ skills: ["Python"], top_repos: [], suggested_projects: [{ name: "API", reason: "Demonstrates backend work" }] }).success, true);
});
