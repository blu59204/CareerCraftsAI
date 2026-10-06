# Audit remediation — PR #34

Date: 2026-10-06. Original audit: [code, architecture and security findings](2026-10-06-code-architecture-security-audit.md).

## Resolved findings

| Finding | Implemented behavior |
| --- | --- |
| F1 Consent | Chat, history and health use the shared account/consent dependency. Due-for-erasure accounts cannot start protected work. |
| F2 Message approval | Every generated outreach and follow-up remains a draft. Explicit approval binds recipient, subject, body and attachment bytes; changes invalidate approval. Sending claims and quota checks serialize under the owner lock. |
| F3 Computer erasure | Strict owner-scoped relay purge removes owned profile/workspace volumes, including orphaned volumes. Ownership mismatch and busy resources fail safely for retry. Erasure waits for purge; tombstones prevent late recreation. |
| F4 Document lifecycle | Stable document UUIDs identify chunks. Retrieval requires a live owner/document record. A transactional cleanup queue retries file and vector removal after deletion. |
| F5 Parsing limits | Reads stop at the upload limit, format comes from verified bytes, archives/XML have expansion limits, and isolated parsing has bounded time, memory, pages, text and concurrency. |
| F6 Prompt bounds | Model prompts use a bounded window of complete user turns and tool groups, independently of retained SQL conversation history. |
| F7 Chat admission | Checkpoints belong to one bounded request. Shared locked admission reserves and logs chat/direct-outreach work, enforces per-user concurrency and prevents admission during erasure. |
| F8 Search consistency | Warm catalog and live search share role/location/work-mode matching. |
| F9 Vector indexes | Supported embedding dimensions use matching expression HNSW indexes and retrieval predicates. Migration backfills unambiguous live ownership and removes unsafe orphan/ambiguous vectors. |
| F10 Tailoring architecture | Rule tailoring uses the existing durable agent workflow, gateway, logging and checkpoints, with idempotent retry of reused runs. Final application review remains mandatory. |

Additional fixes move application filtering/count/paging into SQL, restore export completeness, purge raw memory and gateway sessions, serialize uploads against account deletion, let database cascades erase loaded child records, remove unused legacy ATS/PDF/SSE implementations, update production frontend dependencies, and repair changed-code CI formatting and fixture assumptions.

## Validation and limits

Backend: 1,380 unit/security tests passed, 63 skipped; the expanded database integration suite passed all 65 tests against disposable PostgreSQL/Redis. Frontend: 25 tests, lint, TypeScript and production build passed. Four Node ownership/purge tests passed, and the supervisor patch was checked against pinned upstream source. Production frontend dependencies and the Python dependency audit report no known vulnerabilities. Bandit reports no medium/high findings; the changed-code Ruff/Black gates are used because the repository retains existing Ruff diagnostics.

Development-only frontend dependency advisories remain: seven high and two moderate, involving currently unpatched transitive packages. Provider/live-environment tests are skipped where credentials are absent. No real email, job submission, production migration or deployment was performed. The actual deployed supervisor purge still needs deployment smoke validation.

## Rollout

1. Apply `20261006100000_outreach_approval.sql` and `20261006101000_document_lifecycle.sql` through the normal migration runner.
2. Rebuild and deploy the backend/worker and computer relay/supervisor images together. The supervisor image installs the strict owner-scoped purge route; the relay must reach that updated image.
3. Previously approved outreach must be explicitly approved again. Ambiguous legacy semantic chunks require document re-ingestion; source documents remain retained.
4. Verify purge with a synthetic owner on the deployed computer host and monitor document-cleanup retries before production acceptance.

The original audit describes the reviewed revision. This remediation record describes the subsequent fixes and their verification; it does not certify deployment configuration or eliminate all possible defects.
