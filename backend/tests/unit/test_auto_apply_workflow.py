"""AutoApplyWorkflow tests using Temporal's official test environment.

These replace the four real activities with name-matched stubs (the
standard Temporal Python pattern for isolating workflow control-flow from
activity implementation) so no real DB/browser is touched — that coverage
already exists in test_workflow_runtime.py / test_durable_workflows.py for
the underlying application_workflow.run_application_stage these activities
wrap. What's tested here is Temporal-specific: signals, queries, retry
policy behavior, and the states no application should ever get stuck in.
"""
import uuid

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflows.auto_apply import AutoApplyIntent, AutoApplyWorkflow, auto_apply_workflow_id

TASK_QUEUE = "test-auto-apply-queue"


def test_stable_workflow_id_is_deterministic_per_user_and_application():
    user_id = str(uuid.uuid4())
    job_application_id = str(uuid.uuid4())
    assert (
        auto_apply_workflow_id(user_id, job_application_id)
        == f"auto-apply/{user_id}/{job_application_id}"
    )
    # Same inputs -> same id, every time (this is what makes "repeated start
    # requests return the existing run" work: Temporal itself rejects a
    # second Start with the same id while one is running).
    assert auto_apply_workflow_id(user_id, job_application_id) == auto_apply_workflow_id(user_id, job_application_id)
    assert auto_apply_workflow_id(user_id, "other") != auto_apply_workflow_id(user_id, job_application_id)


def _reserved(run_id="run-1", attempt_id="attempt-1"):
    return {
        "attempt_id": attempt_id, "run_id": run_id, "job_url": "https://jobs.example.test/apply",
        "company": "Acme", "role": "Backend Engineer", "pdf_document_id": "doc-1",
        "resume_sha256": "deadbeef",
    }


@pytest.mark.asyncio
async def test_approval_signal_advances_from_review_to_submit():
    stage_calls = []

    @activity.defn(name="reserve_application_attempt")
    async def fake_reserve(params: dict) -> dict:
        return _reserved()

    @activity.defn(name="run_application_stage_activity")
    async def fake_stage(params: dict) -> dict:
        stage_calls.append(params["pending"]["type"])
        if params["pending"]["type"] == "browser_prepare":
            return {"status": "awaiting_approval", "pending_action": {"type": "browser_review", "form": {}}}
        return {"status": "completed", "result": {"outcome": "submitted"}}

    @activity.defn(name="apply_answers_and_resume_activity")
    async def fake_answers(params: dict) -> dict:
        raise AssertionError("not used in this test")

    @activity.defn(name="schedule_followup_activity")
    async def fake_followup(params: dict) -> None:
        return None

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=TASK_QUEUE, workflows=[AutoApplyWorkflow],
            activities=[fake_reserve, fake_stage, fake_answers, fake_followup],
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                AutoApplyIntent(user_id="user-1", job_application_id="job-1"),
                id=auto_apply_workflow_id("user-1", "job-1"),
                task_queue=TASK_QUEUE,
            )
            # Poll until the workflow is actually waiting on approval before
            # signaling — the time-skipping env auto-advances time, so this
            # resolves almost immediately in wall-clock terms.
            import asyncio
            for _ in range(50):
                status = await handle.query(AutoApplyWorkflow.status)
                if status.state == "awaiting_approval":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached awaiting_approval")

            await handle.signal(AutoApplyWorkflow.approve)
            result = await handle.result()

    assert stage_calls == ["browser_prepare", "browser_review"]
    assert result["status"] == "completed"
    assert result["result"]["outcome"] == "submitted"


@pytest.mark.asyncio
async def test_cancellation_signal_stops_the_workflow_before_submit():
    @activity.defn(name="reserve_application_attempt")
    async def fake_reserve(params: dict) -> dict:
        return _reserved()

    @activity.defn(name="run_application_stage_activity")
    async def fake_stage(params: dict) -> dict:
        return {"status": "awaiting_approval", "pending_action": {"type": "browser_review", "form": {}}}

    @activity.defn(name="apply_answers_and_resume_activity")
    async def fake_answers(params: dict) -> dict:
        raise AssertionError("not used in this test")

    @activity.defn(name="schedule_followup_activity")
    async def fake_followup(params: dict) -> None:
        raise AssertionError("must never run for a cancelled application")

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=TASK_QUEUE, workflows=[AutoApplyWorkflow],
            activities=[fake_reserve, fake_stage, fake_answers, fake_followup],
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                AutoApplyIntent(user_id="user-2", job_application_id="job-2"),
                id=auto_apply_workflow_id("user-2", "job-2"),
                task_queue=TASK_QUEUE,
            )
            import asyncio
            for _ in range(50):
                status = await handle.query(AutoApplyWorkflow.status)
                if status.state == "awaiting_approval":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached awaiting_approval")

            await handle.signal(AutoApplyWorkflow.cancel)
            result = await handle.result()

    assert result["status"] == "cancelled"


@pytest.mark.asyncio
async def test_submit_activity_is_never_retried_on_failure():
    """The one hard safety property: maximum_attempts=1 on the activity
    call that can reach the actual Submit click. If this activity raises,
    Temporal must not call it again — an ambiguous external side effect is
    never something the platform silently retries."""
    submit_attempts = {"n": 0}

    @activity.defn(name="reserve_application_attempt")
    async def fake_reserve(params: dict) -> dict:
        return _reserved()

    @activity.defn(name="run_application_stage_activity")
    async def fake_stage(params: dict) -> dict:
        if params["pending"]["type"] == "browser_prepare":
            return {"status": "awaiting_approval", "pending_action": {"type": "browser_review", "form": {}}}
        submit_attempts["n"] += 1
        raise RuntimeError("browser crashed mid-click")

    @activity.defn(name="apply_answers_and_resume_activity")
    async def fake_answers(params: dict) -> dict:
        raise AssertionError("not used in this test")

    @activity.defn(name="schedule_followup_activity")
    async def fake_followup(params: dict) -> None:
        return None

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=TASK_QUEUE, workflows=[AutoApplyWorkflow],
            activities=[fake_reserve, fake_stage, fake_answers, fake_followup],
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                AutoApplyIntent(user_id="user-3", job_application_id="job-3"),
                id=auto_apply_workflow_id("user-3", "job-3"),
                task_queue=TASK_QUEUE,
            )
            import asyncio
            for _ in range(50):
                status = await handle.query(AutoApplyWorkflow.status)
                if status.state == "awaiting_approval":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached awaiting_approval")

            await handle.signal(AutoApplyWorkflow.approve)
            with pytest.raises(WorkflowFailureError):
                await handle.result()

    assert submit_attempts["n"] == 1


@pytest.mark.asyncio
async def test_unresolved_answers_checkpoint_reuses_answers_activity_then_resumes():
    calls = []

    @activity.defn(name="reserve_application_attempt")
    async def fake_reserve(params: dict) -> dict:
        return _reserved()

    @activity.defn(name="run_application_stage_activity")
    async def fake_stage(params: dict) -> dict:
        calls.append(("stage", params["pending"]["type"]))
        return {
            "status": "awaiting_approval",
            "pending_action": {
                "type": "application_answers_required",
                "fields": [{"field_id": "sponsor", "question_key": "authorization.requires_sponsorship", "label": "Sponsorship?"}],
            },
        }

    @activity.defn(name="apply_answers_and_resume_activity")
    async def fake_answers(params: dict) -> dict:
        calls.append(("answers", dict(params["answers"])))
        return {"status": "completed", "result": {"outcome": "submitted"}}

    @activity.defn(name="schedule_followup_activity")
    async def fake_followup(params: dict) -> None:
        calls.append(("followup", None))

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=TASK_QUEUE, workflows=[AutoApplyWorkflow],
            activities=[fake_reserve, fake_stage, fake_answers, fake_followup],
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                AutoApplyIntent(user_id="user-4", job_application_id="job-4"),
                id=auto_apply_workflow_id("user-4", "job-4"),
                task_queue=TASK_QUEUE,
            )
            import asyncio
            for _ in range(50):
                status = await handle.query(AutoApplyWorkflow.status)
                if status.state == "awaiting_input":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached awaiting_input")

            await handle.signal(AutoApplyWorkflow.provide_answers, {"sponsor": "No"})
            result = await handle.result()

    assert ("answers", {"sponsor": "No"}) in calls
    assert ("followup", None) in calls
    assert result["result"]["outcome"] == "submitted"


@pytest.mark.asyncio
async def test_unknown_outcome_sets_needs_verification_and_does_not_reschedule_followup():
    @activity.defn(name="reserve_application_attempt")
    async def fake_reserve(params: dict) -> dict:
        return _reserved()

    @activity.defn(name="run_application_stage_activity")
    async def fake_stage(params: dict) -> dict:
        if params["pending"]["type"] == "browser_prepare":
            return {"status": "awaiting_approval", "pending_action": {"type": "browser_review", "form": {}}}
        return {"status": "failed", "result": {"outcome": "unknown", "message": "Check the portal before retrying."}}

    @activity.defn(name="apply_answers_and_resume_activity")
    async def fake_answers(params: dict) -> dict:
        raise AssertionError("not used in this test")

    @activity.defn(name="schedule_followup_activity")
    async def fake_followup(params: dict) -> None:
        raise AssertionError("must never run for an unconfirmed submission")

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=TASK_QUEUE, workflows=[AutoApplyWorkflow],
            activities=[fake_reserve, fake_stage, fake_answers, fake_followup],
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                AutoApplyIntent(user_id="user-5", job_application_id="job-5"),
                id=auto_apply_workflow_id("user-5", "job-5"),
                task_queue=TASK_QUEUE,
            )
            import asyncio
            for _ in range(50):
                status = await handle.query(AutoApplyWorkflow.status)
                if status.state == "awaiting_approval":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached awaiting_approval")

            await handle.signal(AutoApplyWorkflow.approve)
            result = await handle.result()
            final_status = await handle.query(AutoApplyWorkflow.status)

    assert result["result"]["outcome"] == "unknown"
    assert final_status.state == "needs_verification"


@pytest.mark.asyncio
async def test_browser_input_waits_for_approval_signal_like_browser_review():
    """Regression: browser_input must NOT auto-retry on a timer — the
    BullMQ path's frontend "Continue preparation" button posts to the same
    generic approve endpoint for every checkpoint type, so Temporal must
    wait for that same signal rather than silently changing the UX."""
    stage_calls = []

    @activity.defn(name="reserve_application_attempt")
    async def fake_reserve(params: dict) -> dict:
        return _reserved()

    @activity.defn(name="run_application_stage_activity")
    async def fake_stage(params: dict) -> dict:
        stage_calls.append(params["pending"]["type"])
        if len(stage_calls) == 1:
            return {"status": "awaiting_approval", "pending_action": {"type": "browser_input", "form": {}}}
        return {"status": "completed", "result": {"outcome": "submitted"}}

    @activity.defn(name="apply_answers_and_resume_activity")
    async def fake_answers(params: dict) -> dict:
        raise AssertionError("not used in this test")

    @activity.defn(name="schedule_followup_activity")
    async def fake_followup(params: dict) -> None:
        return None

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=TASK_QUEUE, workflows=[AutoApplyWorkflow],
            activities=[fake_reserve, fake_stage, fake_answers, fake_followup],
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                AutoApplyIntent(user_id="user-6", job_application_id="job-6"),
                id=auto_apply_workflow_id("user-6", "job-6"),
                task_queue=TASK_QUEUE,
            )
            import asyncio
            for _ in range(50):
                status = await handle.query(AutoApplyWorkflow.status)
                if status.state == "awaiting_browser_input":
                    break
                await asyncio.sleep(0.05)
            else:
                raise AssertionError("workflow never reached awaiting_browser_input")

            # Give the workflow a moment to (incorrectly) auto-retry if the
            # regression this test guards against were reintroduced.
            await asyncio.sleep(0.2)
            assert stage_calls == ["browser_prepare"], "must not retry browser_input without a signal"

            await handle.signal(AutoApplyWorkflow.approve)
            result = await handle.result()

    assert stage_calls == ["browser_prepare", "browser_input"]
    assert result["result"]["outcome"] == "submitted"
