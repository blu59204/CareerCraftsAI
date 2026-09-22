"""Live agent matrix: exercises the 12 non-lifecycle graph-agent task routes
through the real /agents/run API and asserts each reaches a valid terminal
result with real output. Also covers Task 9 Steps 3-5: FollowUpAgent and
AutoApply checkpoint investigation (each resulted in a documented,
honestly-reported gap rather than a fabricated live test — see the comment
blocks ahead of Step 5 below for why), plus routing/negative-path coverage
(agent_type echo, invalid task_type, missing active model, and the
queued/running-vs-awaiting_approval concurrency-limit contract).

This is Task 9 (all steps) of the agent-reliability-fix plan. Together with
test_live_user_journeys.py's existing FollowUp date-mirroring and AutoApply
cold-email-checkpoint tests (Task 8), this file exercises Orchestrator
routing for all 15 agent responsibilities.

Supersedes and replaces test_agent_failure_regression.py (deleted by Task 9
Step 6 — its CASES/`_wait_for_terminal` matrix is superseded by AGENT_CASES/
`start_and_wait` below, and its one still-valid test,
test_invalid_task_type_is_rejected, was ported forward). Reuses conftest.py's
session-scoped `api_client` and the shared `wait_for_run` fixture instead of
redefining them.

Run with RUN_LIVE_E2E=1 and a staging TEST_JWT:

    RUN_LIVE_E2E=1 \
        backend/.venv/Scripts/python.exe -m pytest backend/tests/e2e/test_agent_matrix.py -q

This is also how scripts/run_e2e_tests.sh invokes this file (alongside
test_harness_contract.py, test_live_screen_smoke.py, and
test_live_user_journeys.py) - that script only exports RUN_LIVE_E2E=1, so
this file's gate must not require anything else or it will silently skip
under the real runner.

This suite never approves an email send or job application submit.
"""
from __future__ import annotations

import os

import pytest

# Pure-API file (no Playwright page), so conftest.py's `_auth_state` live gate
# never applies to it. conftest.py's `pytest_collection_modifyitems` already
# skips everything under tests/e2e/ unless RUN_E2E=1 or (TEST_* creds present
# and /health is up) - but that check has nothing to do with RUN_LIVE_E2E, and
# would happily let this suite run (burning real LLM tokens against all 12
# agents) just because creds happen to be exported for an unrelated reason.
# Gate explicitly on RUN_LIVE_E2E=1, matching every sibling live file in this
# suite (test_harness_contract.py, test_live_screen_smoke.py,
# test_live_user_journeys.py) and scripts/run_e2e_tests.sh's actual
# invocation, which exports only RUN_LIVE_E2E=1 - not RUN_AGENT_FAILURE_E2E
# (that var is specific to the old test_agent_failure_regression.py file
# this one supersedes; carrying it over here would make the runner script
# silently skip every case).
pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.getenv("RUN_LIVE_E2E") != "1",
        reason="Set RUN_LIVE_E2E=1 to run the live agent matrix (hits all 12 graph "
        "agents with real model calls and tokens)",
    ),
    # Overrides pyproject.toml's global 60s pytest-timeout: individual cases
    # wait up to 300s (auto_apply) and the concurrency test alone waits
    # 150s + 150s sequentially within one test.
    pytest.mark.timeout(600),
]

AGENT_CASES = [
    ("job_search", {"titles": ["Senior Python Engineer"], "location": "Remote", "max_results": 3}),
    ("nl_job_search", {"query": "remote senior Python engineer role"}),
    ("resume_optimize", {"jd_text": "Senior Python Engineer using FastAPI and PostgreSQL"}),
    ("cover_letter", {"jd_text": "Senior Python Engineer using FastAPI", "tone": "formal"}),
    ("linkedin_optimize", {"target_role": "Senior Python Engineer"}),
    ("linkedin_outreach", {"company_name": "Example Corp", "role_context": "Senior Python Engineer"}),
    ("email", {"company": "Example Corp", "role": "Senior Python Engineer", "recipient_email": "e2e@example.com"}),
    ("email_monitor", {}),
    ("interview_coach", {"role": "Senior Python Engineer", "company": "Example Corp"}),
    ("interview_prep", {"role": "Senior Python Engineer", "company": "Example Corp"}),
    ("company_research", {"company_name": "Example Corp"}),
    ("salary_intelligence", {"role": "Senior Python Engineer", "location": "Bengaluru", "experience_years": 5}),
]

# email_monitor is a read-only Gmail inbox scan (AGENTS.md) that can
# truthfully find nothing to act on and legitimately `complete` with an
# empty result and zero tokens spent (no reply found -> nothing to draft ->
# no LLM call). Every other case here is LLM-backed generation/analysis work
# that must always produce a nonempty result/pending_action and spend
# nonzero tokens - an empty result from any of those is a real bug, not a
# valid outcome, so this allowance is scoped to email_monitor only.
EMPTY_RESULT_ALLOWED = {"email_monitor"}

TERMINAL_STATUSES = {"completed", "awaiting_approval", "failed", "expired"}


def start_and_wait(api_client, wait_for_run, task_type: str, context: dict, terminal_statuses=TERMINAL_STATUSES) -> dict:
    """POST /agents/run for (task_type, context), poll GET /agents/runs/{id}
    via the shared `wait_for_run` helper until the run reaches one of
    `terminal_statuses`, and return the persisted run detail dict."""
    response = api_client.post("/agents/run", json={"task_type": task_type, "context": context})
    assert response.status_code != 429, response.text
    response.raise_for_status()

    run_id = response.json()["run_id"]
    timeout = 300 if task_type == "auto_apply" else 120
    run = wait_for_run(api_client, run_id, timeout)
    assert run["status"] in terminal_statuses, run
    return run


def _assert_owner_isolation(api_client, run_id: str) -> None:
    """Owner isolation check.

    `GET /agents/runs/{run_id}` (backend/app/api/v1/agents.py::get_run_detail)
    scopes its lookup to `AgentRun.id == run_uuid, AgentRun.user_id ==
    current_user.id` and returns 404 (not 403) when the row doesn't match
    both - the same IDOR-safe "scope the query, 404 on miss" pattern used
    for InterviewSession lookups in interview.py (Task 5's IDOR check). A run
    owned by another user is therefore indistinguishable from a nonexistent
    run to anyone else's client: there is no code path that returns another
    user's run.

    This test suite's live env provisions exactly one identity (TEST_JWT /
    TEST_EMAIL / TEST_PASSWORD - see conftest.py's REQUIRED_LIVE_VARS); there
    is no second account/JWT to make a real cross-account HTTP call with. In
    its absence we (a) confirm this run is fetchable by its owner via this
    exact id, which pins down that the endpoint and id are real and not
    trivially satisfied, and (b) rely on the code-level guarantee above,
    verified by inspection rather than a live 404. If a second live identity
    (e.g. TEST_JWT_2) is ever added to the suite, replace this with an actual
    cross-account GET asserting 404.
    """
    response = api_client.get(f"/agents/runs/{run_id}")
    response.raise_for_status()
    assert response.json()["id"] == run_id


@pytest.mark.parametrize("task_type,context", AGENT_CASES)
def test_agent_matrix_reaches_terminal_result(api_client, wait_for_run, task_type, context):
    run = start_and_wait(api_client, wait_for_run, task_type, context, {"completed", "awaiting_approval"})

    assert run.get("duration_ms") is not None and run["duration_ms"] > 0, run
    _assert_owner_isolation(api_client, run["id"])

    output = run.get("output") or {}
    if run["status"] == "completed" and not output:
        assert task_type in EMPTY_RESULT_ALLOWED, (
            f"{task_type} completed with an empty result. Only email_monitor's "
            f"empty-inbox scan is allowed to complete empty; every other task_type "
            f"here is LLM-backed generation/analysis and an empty result is a bug: {run}"
        )
        return  # legitimate empty inbox scan - no drafting work, tokens may be 0

    assert output, f"{task_type} produced an empty result/pending_action: {run}"
    assert run.get("tokens_used", 0) > 0, run


# ---------------------------------------------------------------------------
# Step 3: FollowUpAgent
# ---------------------------------------------------------------------------
# Task 8 already covers the one FollowUp contract reachable through a safe,
# public API surface: PATCH /jobs/applications/{id}/status mirroring
# followup_day5/followup_day12 onto the JobApplication row the moment a
# saved application transitions to "applied"
# (test_followup_schedule_set_when_application_marked_applied in
# test_live_user_journeys.py). Not duplicated here.
#
# This task's brief additionally asks to "create an email draft, approve
# only its scheduling checkpoint, assert day-5/day-12 queue entries, mark a
# test reply, run EmailMonitor, and assert follow-ups are cancelled."
# Grepping every file touching "followup"/"schedule_followups" found:
#
#   - schedule_followups() (app/agents/followup_agent.py:83) has exactly one
#     call site: schedule_followup_activity in app/workflows/activities.py,
#     itself only reachable from the real Temporal-orchestrated auto-apply
#     workflow after a *verified* submission. It has no HITL "scheduling
#     checkpoint" of its own to approve — scheduling is unconditional once a
#     submission is verified, so there is nothing to "approve only the
#     scheduling checkpoint" of.
#
#   - The actual day-5/day-12 SEND does have a checkpoint, but it lives in
#     app/api/internal.py's POST /internal/agents/run-followup, fired only
#     by the BullMQ worker (worker/src/processors/followup.processor.ts)
#     once a delayed job's real 5- or 12-day timer elapses. That endpoint is
#     protected by a dedicated `x-internal-secret` header
#     (app/api/internal.py's `_verify_secret`), not the JWT `api_client`
#     authenticates with, and the module's own docstring states it is "Not
#     exposed via Nginx (blocked at nginx level)" — deliberately walled off
#     from the public API surface this live suite talks to. Reaching it
#     live would mean either handing this test process a server secret
#     meant only for the internal worker, or waiting out a real multi-day
#     BullMQ delay — neither is reasonable here.
#
#   - CORRECTION to this task's original investigation notes: a real
#     auto-cancel-on-reply mechanism DOES exist. run_followup() in
#     app/api/internal.py calls _has_recruiter_replied() before drafting
#     and, if it returns True, clears followup_day5/followup_day12 and
#     returns status="cancelled" without ever drafting or sending anything
#     — it is not a dead stub, and it is unit-tested with mocks in
#     backend/tests/unit/test_followup_agent.py::
#     test_run_followup_cancels_instead_of_drafting_when_recruiter_replied.
#     What's missing is not the feature; it's a way to reach it live
#     through the public, JWT-authenticated API surface without either
#     breaking the internal/public boundary or waiting multiple real days.
#
# Both halves of Step 3 (the scheduling-checkpoint approval and the
# cancel-on-reply flow) are only reachable through that internal,
# secret-gated, worker-only endpoint or a real multi-day delay, so there is
# no additional *live* assertion to safely add beyond Task 8's
# date-mirroring coverage. Documented here rather than fabricated.


# ---------------------------------------------------------------------------
# Step 4: AutoApply checkpoints
# ---------------------------------------------------------------------------
# Task 8 already covers AutoApplyPipeline's one real, safely-reachable HITL
# checkpoint: the orchestrator's `auto_apply` task_type
# (app/agents/auto_apply_pipeline.py) — a job-search + cold-email/LinkedIn-
# outreach pipeline whose single checkpoint carries resume_markdown/
# resume_draft content, rejected (never approved) in
# test_auto_apply_first_checkpoint_includes_drafts_and_rejects_cleanly
# (test_live_user_journeys.py). Not duplicated here.
#
# This task's brief describes a different shape: "a disposable generic-form
# fixture... checkpoint one contains resume and cover letter... checkpoint
# two contains the filled form, reject it." That two-checkpoint,
# resume+cover-letter-then-filled-form shape does not match either shipped
# auto-apply surface:
#
#   1. auto_apply_pipeline.py's checkpoint (above) has resume only, no
#      cover letter, and no filled form — it precedes any browser
#      automation entirely.
#
#   2. The real form-filling/browser-submission workflow is a SEPARATE
#      surface: POST /jobs/applications/{id}/prepare-apply
#      (app/api/v1/jobs.py:1008). It hard-requires an application that
#      already has an *approved* resume attached (app.resume_id, checked at
#      jobs.py:1042-1046) — i.e. ResumeAgent's own checkpoint must already
#      be done, separately, beforehand. There is no "resume + cover letter"
#      checkpoint of its own to review; its two stages are browser_prepare
#      -> browser_input/browser_review (form-filling states in
#      app/workflows/auto_apply.py), not a document review.
#
#   Reaching a genuine browser_review checkpoint for (2) requires, in
#   order:
#     a. TEMPORAL_ENABLED=true with a running Temporal worker
#        (jobs.py:1048), OR the non-Temporal fallback, which still queues a
#        background "browser_prepare" task
#        (app/services/workflow_service.add_task, jobs.py:1109-1122) that a
#        worker process must actually pick up and execute with real
#        Playwright/browser-use automation (app/tools/form_filler.py)
#        against `app.job_url`.
#     b. A JobApplication row with a real `job_url` AND an already-attached,
#        already-approved `resume_id` — i.e. a full prior live ResumeAgent
#        HITL approval cycle just to satisfy the precondition.
#     c. That real browser automation actually detecting and filling a form
#        at `job_url`. platform_detector.py does have a "generic" fallback
#        (detect_platform() returns "generic" for any unrecognized host —
#        AGENTS.md's "generic form detection"), so a disposable static HTML
#        fixture page is plausible in principle. But even with such a URL,
#        nothing in this repo stands up the rest of that infra
#        automatically — no fixture-form host, no guarantee
#        TEMPORAL_ENABLED or a background worker is running in this test
#        environment, and reaching browser_review means real
#        Playwright/Chromium execution against that fixture.
#
# Standing up Temporal + a worker + browser automation + a hosted
# disposable form is well outside what's reasonable to build as part of
# writing one test, and this task's own safety instructions say to
# document the gap rather than guess when not certain an action is safe.
# This is a documented gap (brief's option (b)), not a live test. What
# Task 8 already exercises (auto_apply_pipeline's one real, safe
# checkpoint) is the correct/only live coverage of an AutoApply HITL gate
# this suite can safely reach today.


# ---------------------------------------------------------------------------
# Step 5: routing and negative paths
# ---------------------------------------------------------------------------

_CASES_BY_TYPE = dict(AGENT_CASES)


def test_agent_run_reports_requested_task_type_as_agent_type(api_client, wait_for_run):
    """`agent_type` on a persisted run is set directly from the request's
    task_type (app/api/v1/agents.py:101, `agent_type=payload.task_type`) —
    there is no separate internal-graph-node name it could drift from.
    Closes the "task maps to expected agent_type" contract with one cheap,
    real HTTP round-trip (email_monitor: read-only, legitimately
    zero-token per this file's own EMPTY_RESULT_ALLOWED reasoning above)
    rather than re-running the full, expensive 12-case matrix a second time
    only to check a field none of those cases asserted on."""
    task_type = "email_monitor"
    run = start_and_wait(api_client, wait_for_run, task_type, _CASES_BY_TYPE[task_type])
    assert run["agent_type"] == task_type, run


def test_invalid_task_type_is_rejected(api_client):
    """Ported from test_agent_failure_regression.py (deleted by this task's
    Step 6) — still valid, still simple."""
    response = api_client.post("/agents/run", json={"task_type": "not_a_real_task", "context": {}})
    assert response.status_code == 400


def test_missing_active_model_produces_actionable_failed_status(api_client, wait_for_run):
    """job_search_node returns `{"status": "failed", "error": "missing:
    active model settings"}` directly (app/agents/job_search.py:1973-1975,
    a plain early return — not a raised exception that would get redacted
    to the generic "Agent failed" by the orchestrator's catch-all), so a
    genuinely-zero-active-model account surfaces this actionable detail
    end to end. There is no dedicated "deactivate" endpoint
    (app/api/v1/users.py only has activate/delete), and deleting the real
    active row would permanently lose its key — every other live-LLM test
    in this suite depends on a working active model. Instead: add a
    disposable fake-key model (POST /me/models deactivates the real row but
    never deletes it — users.py:279-283), then delete the now-active
    disposable row. That leaves zero active rows while the real row is
    still fully intact, just inactive, and recoverable by id via
    PATCH .../activate — exactly the mechanism Task 8a's
    test_settings_models_deepseek_key_never_leaks_and_test_returns_result
    established (restore in `finally`, regardless of assertion outcome)."""
    list_resp = api_client.get("/users/me/models")
    list_resp.raise_for_status()
    previously_active_id = next(
        (m["id"] for m in list_resp.json() if m.get("is_active")), None
    )
    assert previously_active_id, (
        "expected this shared live account to already have an active model "
        "(every other live-LLM test in this suite depends on one) — nothing "
        "to safely probe/restore against if it doesn't"
    )

    disposable_id = None
    try:
        add_resp = api_client.post(
            "/users/me/models",
            json={
                "provider": "deepseek",
                "model_name": "deepseek-flash",
                "api_key": "sk-e2e-missing-model-probe-do-not-use",
            },
        )
        add_resp.raise_for_status()
        disposable_id = add_resp.json()["id"]

        del_resp = api_client.delete(f"/users/me/models/{disposable_id}")
        assert del_resp.status_code == 204, del_resp.text
        disposable_id = None  # gone — don't try to delete it again in finally

        run = start_and_wait(
            api_client, wait_for_run, "job_search", _CASES_BY_TYPE["job_search"], {"failed"},
        )
        error = ((run.get("output") or {}).get("error") or "").lower()
        assert "model" in error, f"expected an actionable missing-model error, got: {run}"
    finally:
        if disposable_id:
            api_client.delete(f"/users/me/models/{disposable_id}")
        restore = api_client.patch(f"/users/me/models/{previously_active_id}/activate")
        assert restore.status_code == 200, (
            f"CRITICAL: failed to restore the previously active model "
            f"(id={previously_active_id}) — every other live-LLM test in this "
            f"suite depends on this: {restore.text}"
        )


# "Missing resume" for resume_optimize: resume_agent_node
# (app/agents/resume_agent.py:82-113) retrieves resume RAG chunks but never
# checks whether any came back — `chunk_texts` is simply used as-is, empty
# or not, and the LLM is still called to tailor a resume from the JD text
# alone. There is no "no resume indexed" error path in the shipped agent to
# actually observe; it silently degrades instead of failing. Separately,
# the shared live test account cannot safely be stripped of its indexed
# resume to construct this state anyway — later tests in this suite (and
# other files) depend on it being present, and there is no equivalent of
# the deactivate/reactivate trick above (RAG documents aren't soft-toggled).
# No test written for this half of Step 5; fabricating one against
# behavior that doesn't exist would misrepresent the app.


def test_concurrency_limit_counts_active_runs_not_approval_waiting_ones(api_client, wait_for_run):
    """AGENTS.md: "Max 2 concurrent agent runs per user." The enforcement
    (app/api/v1/agents.py:79-95) only counts status in {queued, running} —
    awaiting_approval is excluded by that filter. This proves both halves
    live: two simultaneously *active* (queued/running) runs block a third
    start with 429 (matching the mocked unit contract in
    test_agent_run_lifecycle.py::test_concurrency_error_includes_active_run_ids),
    and once those same two runs settle into awaiting_approval, a third
    start no longer 429s.

    Uses company_research and job_search (~120s windows, same contexts as
    the Step 1/2 matrix, both carrying a real HITL checkpoint per
    AGENTS.md) as the two long-running slots, fired back-to-back with no
    wait in between so both are still queued/running when the 429 probe
    fires immediately after."""
    run_a = api_client.post(
        "/agents/run",
        json={"task_type": "company_research", "context": _CASES_BY_TYPE["company_research"]},
    )
    run_a.raise_for_status()
    run_a_id = run_a.json()["run_id"]

    run_b = api_client.post(
        "/agents/run", json={"task_type": "job_search", "context": _CASES_BY_TYPE["job_search"]},
    )
    run_b.raise_for_status()
    run_b_id = run_b.json()["run_id"]

    # Phase 1: A and B were just enqueued with no wait — still queued/running.
    probe = api_client.post("/agents/run", json={"task_type": "email_monitor", "context": {}})
    assert probe.status_code == 429, (
        f"expected a 3rd concurrent run to 429 while {run_a_id} and {run_b_id} are "
        f"still active, got {probe.status_code}: {probe.text}"
    )
    returned_ids = set(probe.json()["detail"]["run_ids"])
    assert {run_a_id, run_b_id} <= returned_ids, probe.text

    # Phase 2: let both settle. Both carry a HITL checkpoint per AGENTS.md,
    # so awaiting_approval is expected, but accept completed too — matching
    # the Step 1/2 matrix's own tolerance for these exact two task_types.
    run_a_detail = wait_for_run(api_client, run_a_id, 150)
    run_b_detail = wait_for_run(api_client, run_b_id, 150)
    assert run_a_detail["status"] in {"completed", "awaiting_approval"}, run_a_detail
    assert run_b_detail["status"] in {"completed", "awaiting_approval"}, run_b_detail

    # Neither counts toward the limit anymore — a 3rd start must succeed.
    after = api_client.post("/agents/run", json={"task_type": "email_monitor", "context": {}})
    assert after.status_code != 429, (
        f"expected a 3rd run to succeed once {run_a_id}/{run_b_id} left queued/running, "
        f"got 429: {after.text}"
    )
    after.raise_for_status()
    wait_for_run(api_client, after.json()["run_id"], 60)
