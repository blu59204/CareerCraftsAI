import assert from "node:assert/strict";
import test from "node:test";
import { githubProfileSchema, profileResultSchema } from "./profile-contracts.ts";

test("malformed model or integration responses fail validation", () => {
  assert.equal(profileResultSchema.safeParse({ sections: [{ after: 2 }] }).success, false);
  assert.equal(githubProfileSchema.safeParse({ skills: "Python" }).success, false);
  // Shape returned by backend github_profile.analyze().
  const repo = { name: "API", url: "https://github.com/u/api", description: null, languages: ["Python"], updated_at: null, score: 3, reason: "Public owned repository" };
  assert.equal(githubProfileSchema.safeParse({ skills: [{ name: "Python", category: "language", confidence: 0.9, evidence: ["api"] }], top_repos: [repo], suggested_projects: [repo] }).success, true);
});
