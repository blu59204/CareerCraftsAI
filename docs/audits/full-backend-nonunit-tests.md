# Backend nonunit test audit

Audited source revision: `3a27b1c`. Fully read all 34 tracked files under backend/tests outside unit/ and fixtures/, including root conftest, integration, e2e and security (8,055 lines). Also fully read all 15 authored fixture HTML/SQL/Python files; the generated resume PDF is inventoried as binary. Exact file hashes and line counts are in coverage-backend-nonunit-tests.csv. No live browser/provider suite was executed, and no real emails or applications were approved.

## Confirmed validation gaps

Remediation: pass-only/literal-comparison approval tests were replaced with production endpoint rejection checks. Security input tests now run admitted routes or inspect actual bound SQL and escaped markup, without accepting authentication rejection as input validation. The old E2E runner delegates to the maintained root runner, and collect-only no longer probes backend health. Concurrent-send behavior remains covered by the real PostgreSQL integration suite.

### TEST-INF-1 — P2: passing HITL tests do not exercise their named contracts

`backend/tests/security/test_hitl_bypass_attempts.py:162–180`: wrong-action testing only compares two hardcoded dictionary strings; expired-checkpoint and concurrent-approval tests contain only `pass`. All three report success even if production approval logic is removed. Real concurrency coverage exists separately in test_durable_workflows.py and recruiter_outreach.py, so this finding concerns misleading security coverage, not proof of an exploitable production bypass. Replace the placeholders with endpoint/service assertions or explicit skips, and test expiry and mismatched action against persisted pending state.

### TEST-INF-2 — P2: security assertions can succeed without reaching input handling

`backend/tests/security/test_api_security.py:77–131`: SQL injection, invalid task, oversized result count and executable upload tests use an unauthenticated request and accept 401. They therefore pass when authentication rejects the request before the input security property is reached. The XSS assertion at line 105 is `A or not A`, always true; its remaining ATS range check exercises no browser rendering. Separate authentication tests from authenticated validation tests and verify actual escaping/sanitization at the rendering boundary.

## Other test architecture observations

- Live suites correctly gate actual sends and application queue approvals through live_safety/ALLOW_LIVE_SENDS, and Gmail-draft writes have a separate ALLOW_GMAIL_DRAFTS opt-in. Ordinary profile/preferences/model-setting writes still mutate the configured shared account; use a disposable account.
- Several live journeys leave checkpoints open (Salary, LinkedIn, dashboard restore), and profile/preferences/onboarding writes are not restored. Repeated execution on one account accumulates state and can encounter admission caps; add cleanup or reset the disposable account.
- The old backend/tests/e2e/run_tests.sh preflight targets /api/v1/health; the application serves /health. scripts/run_e2e_tests.sh uses the current path. Consolidate the legacy runner.
- E2E collection hook probes backend /health even during collect-only; collection is not entirely network-free.
- test_agent_matrix.py's owner-isolation helper only fetches its own run, while test_careercraft_full.py's wrong-user check uses an invalid JWT. Neither proves isolation between two valid users. There are real direct-function owner checks in integration tests, but an HTTP-level two-identity regression remains useful.
- Disposable workflow tests generally use explicit localhost:55439 infrastructure, while applications/resume-facts/provider tests use operator-supplied DB URLs. Test fixtures create throwaway users, but application-list cleanup removes all catalog URLs matching https://jobs.test/%; avoid shared production databases and parallel runs sharing that prefix.
- Migration-runner tests verify normal bootstrap/retry and baseline behavior but do not simulate failure between migration commit and ledger insertion; see INF-2 in full-infrastructure.md for the real disposable-Postgres failure proof.
- Durable workflow and outreach integration tests meaningfully cover concurrent reservation, single sends, payload/attachment reapproval, and account-deletion admission. Document lifecycle tests use isolated databases and real pgvector indexes across embedding dimensions.

## Limits

These findings concern source and test design. They do not certify the live deployment, Clerk/Nango configuration, browser permission state or paid provider behavior. Infrastructure runtime findings and two safe proofs are recorded separately in full-infrastructure.md.
