# Agent B review and validation

Branch: agent-b/jobs. Worktree: D:/CareerCraft-agent-b. Review date: 2026-10-01.

## Phase boundaries

Phase 1 plan completed before implementation (2c40aee). Phase 2 implementation completed before Phase 3 began: owned search selector, isolated public catalog, optional GitHub, executor retirement, extension gate, tests/lint/typecheck/build and disposable migration checks passed. Phase 3 reviewed `git diff master...agent-b/jobs`; master also includes inherited baseline changes, so ownership was checked against baseline 093ef54. No Agent A implementation files were edited in this continuation. All changes are local commits; no deployment, production migration, email or external application submit occurred.

## Review fixes

1. Replaced form snapshot stringification with canonical object-key ordering. Actual MV3 testing showed Chrome storage could reorder unchanged values. Changed values and array ordering still invalidate approval.
2. Deleted the unused legacy form filler with ungated submit methods. Retired server browser task execution fails closed and directs applications to the paired extension. User-facing compatibility failures are clear; raw application URLs/exceptions are excluded from failure logs.
3. Gave jobs services unpooled async connections so synchronous agent event loops cannot reuse API-loop asyncpg connections. Moved vector-store construction into a worker thread. Selected RAG retrieval always filters the owned document ID in the configured provider's resume collection.
4. Increased the persisted source lease to five minutes, covering the bounded three-page retry budget. Broad Adzuna/Remotive feeds avoid query-poisoned source caches. Successful complete refreshes remove vanished source occurrences and preserve first-seen dates.
5. Added explicit PostgreSQL text casts for nullable health warning checks. Real database integration tests reproduced the ambiguous-parameter failure; pagination, cache reuse, 429 isolation and closed-job removal now pass.
6. Locked the owning user row when clearing defaults, matching the set-default serialization guard.
7. Limited GitHub public activity to 90 days and corrected project ranking to distinguish a recent push from a merely nonempty timestamp. Primary-language metadata is labeled separately from measured language bytes. Public-only filtering occurs before language/README fetches. Delete/version guards prevent late refreshes from repopulating deleted data.
8. Cleared GitHub popup polling when its component unmounts and corrected the browser timer type. Updated the real database submit-ledger test to verify both the refused ungated signal and the approved confirmed path.
9. Switched disposable workflow-test PostgreSQL to pgvector so the existing CI integration job exercises the new vector schema.

## Reproducible checks and results

| Check | Result |
|---|---|
| Backend unit/security | 1,082 passed; 69 skipped (existing optional/provider/infrastructure cases) |
| Real PostgreSQL/Redis workflow integration | 10 passed; includes extension authorization, catalog pagination/cache/429 isolation/removal, GitHub public fallback/cache/private exclusion/delete race |
| Recorded connector and ownership/SSRF tests | Included in backend suite; all required API families and JSON-LD covered |
| Read-only source probe | 321 configured candidates; 82 healthy responses; 5,129 normalized jobs; SOURCE_HEALTH.json contains counts/error types only |
| Actual unpacked MV3 popup/background/content check | Passed; no content approval, trusted popup approval, snapshot mutation and replay rejection; controlled API only |
| Temporal | Real disposable local server; register twice, no duplicate Schedules; overlap SKIP verified |
| Migrations | Apply/down checks pass; RLS, service-role grants, index presence and old application-data preservation verified |
| Catalog/index volume | 100,000 catalog rows + 1,000 vectors; sample HNSW query about 0.466 ms; title query about 0.393 ms |
| Locust catalog endpoint | 20 users / 30 seconds; 127 requests, zero failures; p95 about 190 ms. Actual SQL/API/rules, controlled auth, no BYOK/GitHub network traffic |
| Frontend | npm ci, type-check, full lint, production build pass |
| Python | Changed-line Ruff and Black gates pass; full baseline lint backlog remains outside these changes |
| Docker | Test Compose configuration passes; disposable Postgres/Redis suite passes |
| npm audit | Zero vulnerabilities |
| Bandit | No medium/high findings; eight existing low findings in legacy job_search, event_bus and model_router |
| pip-audit | Ran installed-environment audit: 48 findings across 15 existing shared packages; coordinated LangChain/LangGraph pin updates requested from A |
| Existing account-dependent e2e suite | 2 contract tests passed, 131 skipped without operator accounts; controlled MV3 and real database integration checks executed separately |

Runnable checks: `extension/test/mv3_gate.py`, `docs/agent-b/check-jobs.ps1`, `check-temporal.py`, `check-search-load.py`, `probe-sources.py`; backend unit/security and `RUN_WORKFLOW_INTEGRATION=1` durable integration suite. Load checks use an isolated validation-only Locust environment and disposable databases. No production credentials are read.

## Legal and operational posture

The family-by-family official API, attribution, credentials, caching and robots posture is in PLAN.md. LinkedIn/Naukri are explicit optional connectors; challenges require manual input, interaction delays remain, and no detection evasion is implemented. Generic JSON-LD sources require operator permission and robots compliance. Workable/Adzuna remain unavailable without authorized credentials. Candidate board counts are not advertised as healthy-source counts. Secrets are backend-only; new environment variables are documented in .env.example. Tokens remain in the existing Nango/Clerk encryption flow; extension credentials are hashed in the database and restricted to trusted browser contexts.

The retired product executor has no runtime UI/API/workflow/config/deploy references. Remaining literal `sandbox` references are Temporal's required deterministic runtime, Chromium's native isolation flag, historical migration columns, the preserved pre-existing inventory scratch file, and this removal documentation. Removing those independent security/history mechanisms would be unsafe; this distinction is explicit in the plan inventory.

## External limits and handoff

A direct live unauthenticated GitHub probe was attempted twice and hit outbound connection timeouts; recorded public responses plus actual PostgreSQL profile persistence/cache/deletion/race checks pass. Real Nango OAuth/scopes, authenticated Clerk onboarding and LinkedIn/Naukri account walkthroughs require operator accounts and are documented in EXTENSION_CHECK.md. No hosted CI run was triggered; local CI-equivalent gates passed. Python dependency remediation spans shared agent/checkpoint compatibility and is listed under Requests to A. This report does not claim the shared baseline is vulnerability-free or that external account-dependent checks ran.

The GitHub success contract remains exactly {skills, top_repos, suggested_projects}; disconnected/deleted profiles return 404. Applications and search work without GitHub or generative-model credentials. Agent A can consume the profile optionally without changing its shape.
