# Backend unit tests f–m

Fully read all 24 tracked test files whose semantic basename after test_ starts f through m: 4,853 lines. File hashes and exact coverage are in coverage-backend-unit-f-m.csv. Source only; no live network/browser/provider tests were run for this slice.

## Validation gaps

Remediation: copied HITL branch tests now call record_run_result and check commit-before-publish, draft/result persistence and cancellation preservation. The submit-call guard parses Python AST and sees multiline calls. The two quarantined obsolete suites were removed; maintained event-bus, job-search-service/platform and browser boundary suites own their current contracts. Historical hashes in coverage-backend-unit-f-m.csv identify the audited pre-remediation files.

- test_hitl_approval.py's four tests simulate copied branches and literal dictionaries instead of invoking production persistence/approval code. They still pass if the real branches regress. This reinforces TEST-INF-1 in full-backend-nonunit-tests.md; direct production contract regressions should replace those copies.
- test_hitl_flow.py's test_no_caller_passes_submit_true_to_apply_to_job only records violations when apply_to_job( and submit=True occur on the same line. A multiline submit=True call is missed despite the claimed source-wide guard. Several other checks merely search function source for strings; presence of a guard string does not prove its control flow is effective. Actual behavioral tests and AST parsing would provide stronger coverage.
- test_fixes_e2e.py is module-wide INTEGRATION=1 quarantined even for pure schemas/source assertions. Its ping test executes a locally defined imitation generator rather than event_bus.stream_events. It also hardcodes D:/CareerCraft AI paths and references retired agentSlice/browser-preference concepts. test_job_search_agent.py is explicitly quarantined for live fallback leakage and contains stale pre-rewrite contracts. These should not count as effective current unit coverage simply because they collect.
- test_job_search_service.py has meaningful current mocked adapter/ranking and HTTP route coverage, but its FakeSession dedupe test maintains one global seen flag instead of tracking URLs/user ownership. Real DB dedupe tests remain necessary.

## Meaningful coverage observed

- Follow-up drafting/reply cancellation and approval routing use production functions and assert drafts rather than sends.
- Integration gateway tests cover return-path rejection, raw-body HMAC, stale revocation, encrypted metadata, safe read retries and non-retried external mutations.
- LinkedIn profile tests cover PDF validation, bounded repair, evidence/number grounding, model input separation and failed-run token accounting.
- Model-router tests cover provider dispatch, crypto tampering, thinking-model options, token budget denial and token propagation from worker threads. JSON repair tests verify schema retention and redacted logs.
- New source connector tests mock network boundaries and verify parsing, paging, dedupe, hostile XML rejection and credential-disabled sources.

These test-design gaps are separate from confirmed runtime vulnerabilities in the production source audit. No additional production vulnerability was inferred solely from this test slice.
