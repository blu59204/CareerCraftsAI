# Supplemental root unit test review

All sixteen files in `coverage-backend-root-tests.csv` were read in full (3,432 lines), including seven Temporal/workflow modules and four extension modules.

- Account deletion tests cover ordered failures, preservation on provider/purge failures, Redis ownership and deferral for bounded send/request work. Mock-only locks cannot reproduce replacement-document versus erasure ordering.
- `test_agents_api.py:32–69` accepts unauthenticated failure for tests named result-limit rejection, successful dispatch, stream ownership and unknown-run approval. These assertions do not establish the named authenticated behavior; this extends TEST-INF-2 in `full-backend-nonunit-tests.md`.
- Run lifecycle tests meaningfully check shared admission, dispatch failure and stale workflow reconciliation, but do not cover dedicated endpoint admission bypasses.
- Application tests exercise sensitive answer provenance, checked state, semantic validation and profile roundtrips. Mock database results cannot establish two-user query isolation or foreign-key lifecycle behavior.
- Auto-apply pipeline tests exercise the empty-results case and selected helpers; they do not pass a generated tailored document through submission loading. This leaves the BND-1 artifact contract regression undetected.
- Temporal time-skipping tests exercise approval/rejection/expiry, nonretryable continuations, follow-up timing, extension completion and independent scheduled member failures. Sandbox tests validate actual workflow import behavior without requiring a production server. These are meaningful tests of orchestration; stubbed activities deliberately do not establish production ownership, browser click gating or database concurrency.
- Runtime tests protect immutable targets, invalidated edited PDFs, uncertain submission state, duplicate email suppression and cancellation during agent execution. Their mocked database does not reproduce actual row locks; the separate integration tests supply that evidence for selected paths.
- Extension tests meaningfully exercise device token hashing, sensitive-answer handling, approval expiry, replay protection, uncertain outcome persistence and failed-signal retry. These backend permit checks do not cover a content-script click that bypasses the permit path entirely (INF-1).

No tests were edited. Findings distinguish missing validation from proven runtime defects.
