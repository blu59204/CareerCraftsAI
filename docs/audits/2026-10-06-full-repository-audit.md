# Full repository code, architecture and security audit

Audited revision: `3a27b1ccd190c2b5f6950d5d9ddabd87ca1df342` on PR [#34](https://github.com/blu59204/CareerCraftsAI/pull/34). This audit extends the earlier PR review after its ten original findings were remediated. New findings below concern the current repository snapshot, including existing code outside the PR diff. They must not all be attributed to changes introduced by this PR.

**Status: complete for authored repository code, tests and configuration at the recorded revision.** All 876 tracked files are accounted for: 779 files were read in full, totaling 120,087 lines; 18 asset/generated exclusions, 44 documentation files outside full-line review and 35 historical generated evidence files are separately classified. Coverage reconciliation found zero missing code/config/test files, zero hash mismatches and zero overlapping reviewer records. Source edits, commits and pushes were outside this audit pass.

## Findings requiring first attention

| Priority | Finding | Evidence report |
|---|---|---|
| P1 | Generic interview evaluation can read and update another owner's session | `full-backend-services.md` |
| P1 | Generic extension Apply entry click can submit without approval | `full-infrastructure.md`, INF-1 |
| P1 | Existing tailored PDF replacement can race account erasure and leave a private file | `full-backend-boundaries.md`, BND-4 |
| P1 | Generated tailored resumes are rejected by application submission | `full-backend-boundaries.md`, BND-1 |
| P1 | Frontend private caches persist across account switching | `full-frontend.md`, F-FE-01 |
| P1 | Approval preview can display different text from the approved payload | `full-frontend.md`, F-FE-02 |
| P1 | Password recovery and common MFA challenges cannot be completed | `full-frontend.md`, F-FE-03 |
| P2 | Dedicated agent endpoints bypass shared admission and audit accounting | `full-backend-boundaries.md`, BND-3 |
| P2 | Referenced documents cannot be deleted through the document API | `full-backend-boundaries.md`, BND-2 |
| P2 | Idle SSE loops repeatedly perform nonblocking Redis polls | `full-backend-boundaries.md`, BND-5 |
| P2 | Migration changes and their ledger entry commit separately | `full-infrastructure.md`, INF-2 |
| P2 | Production extension origin cannot bootstrap bridge pairing | `full-infrastructure.md`, INF-3 |
| P2 | Production validation treats failed Compose inspection as healthy | `full-infrastructure.md`, INF-4 |

Additional P2 findings in the services report cover scoring-schema mismatch, inaccessible company memory, concurrent inbox status regression, incorrect Indeed country and discarded resume fallback. The frontend report additionally covers terminal-run reconciliation, failed assisted-apply queue advancement, unevaluated mock interviews, fabricated outreach status, ineffective filters/export, stale leads, salary discard and concurrent preference updates. BND-6 covers the retired LinkedIn send path. TEST-INF-1/2 cover misleading security assertions; the supplemental root test report identifies related gaps without claiming additional runtime exploits.

The component reports record 28 runtime findings: seven P1 and 21 P2. They also record separate test-design weaknesses, including placeholder HITL tests, unauthenticated input tests, a tautological ownership assertion, incomplete policy-history validation and ineffective schema assertions. Detailed reports include precise source references, reproduction evidence and recommendations. P1 means fix before treating the affected flow as production ready; P2 means a material correctness, reliability or validation defect.

## Architectural conclusion

The repository has appropriate building blocks: durable Temporal execution, ownership-scoped lookups, transactional submission reservation, immutable approval snapshots, encrypted model settings, gateway routing and durable cleanup. The significant defects arise where a reachable path bypasses those mechanisms or uses a conflicting artifact contract. The smallest coherent repair is to extend those existing responsible boundaries and make all callers use them.

1. Make tenant ownership part of every agent data lookup, including generic task dispatch. Route-level checks alone cannot cover alternate entry points.
2. Consolidate admission, durable dispatch and run accounting across dedicated and generic agent endpoints.
3. Centralize document lifecycle and accepted artifact contracts. Coordinate storage writes with account erasure, while preserving approved document versions and digests.
4. Treat unknown browser clicks as potential side effects before clicking. Bind the displayed approval preview to exactly the content submitted.
5. Reset or scope private client state at identity boundaries, and implement authentication capabilities consistently with Clerk configuration.
6. Commit deployment schema changes and migration accounting atomically; validate the actual deployed stack and fail on inspection errors.

The table-owner API database role means RLS does not independently protect every backend operation. Explicit ownership validation remains critical. Test counts alone do not certify those boundaries: the security suite contains placeholder and unauthenticated tests that pass without exercising the named property.

## Evidence and verification

This is a full-content static review of authored source, tests and configuration, supplemented by isolated runtime reproductions. Synthetic extension execution demonstrated one Apply submission with zero approval checks. Disposable PostgreSQL reproduced committed migration DDL without a ledger row and a failing retry, and an existing-document replacement surviving account erasure in a simulated file store. Mocked Python execution demonstrated foreign interview data reaching an attacker evaluation, tailored artifact rejection, scoring-schema loss and rapid idle SSE polling. The installed QueryClient returned account A's fresh cache without invoking account B's fetch. These probes were isolated and did not send real emails, apply for jobs or alter production.

The earlier remediation passed 1,380 backend unit/security tests (63 skipped), 65 integration tests, 25 frontend tests plus lint/typecheck/build, and four Node purge tests. All five GitHub CI jobs passed on this revision; live smoke was skipped. Those results are historical validation of the prior fixes, not proof that newly discovered issues are absent. The unchanged full suite was not rerun simply to repeat those results.

## Scope and limits

`coverage-full-inventory.csv` distinguishes files semantically read in full from generated lockfiles, generated vendor assets, binaries, historical logs and documentation. A SHA-256 identifies the reviewed snapshot; hashing is not itself a code review. Third-party installed dependencies, gitignored runtime secrets, deployed firewall rules and provider-side settings are outside the authored repository review. No claim is made that every historical Markdown line or third-party library was read. Full reading also does not prove absence of further defects.

Component coverage and reports:

- `coverage-backend-boundaries.csv` and `full-backend-boundaries.md`
- `coverage-backend-services.csv` and `full-backend-services.md`
- `coverage-frontend.csv` and `full-frontend.md`
- `coverage-infrastructure.csv` and `full-infrastructure.md`
- `coverage-backend-nonunit-tests.csv` and `full-backend-nonunit-tests.md`
- `coverage-backend-services-tests.csv`, with observations in `full-backend-services.md`
- `coverage-backend-root-tests.csv` and `full-backend-root-tests.md`
- `coverage-backend-unit-f-m.csv` and `full-backend-unit-f-m.md`
- `coverage-unit-n-z.csv` and `full-unit-n-z.md`

The original review and completed remediation remain in `2026-10-06-code-architecture-security-audit.md` and `2026-10-06-remediation.md`.
