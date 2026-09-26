"""Workflow control flow on Temporal's time-skipping test server.

Activities are replaced with name-matched stubs (the standard Temporal
pattern), so these tests pin down signals, timers and retry behaviour
without a database or browser. Activity implementations are covered in
test_workflow_runtime.py / test_agent_run_lifecycle.py.
"""

import asyncio
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from app.workflows.agent_run import (
    AgentRunInput,
    AgentRunWorkflow,
    ApprovalDecision,
    agent_run_workflow_id,
)
from app.workflows.auto_apply import AutoApplyIntent, AutoApplyWorkflow, auto_apply_workflow_id
from app.workflows.followup import FollowupInput, FollowupWorkflow
from app.workflows.job_search import JobSearchInput, JobSearchWorkflow

QUEUE = "test-workflows"


async def _wait_for(handle, query, expected, attempts=200):
    for _ in range(attempts):
        if await handle.query(query) == expected:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"workflow never reached {expected!r}")


# ── AgentRunWorkflow ────────────────────────────────────────────────────


def _agent_activities(execute_status="awaiting_approval", continue_status="completed"):
    calls = {"execute": 0, "continue": [], "expire": 0}

    @activity.defn(name="execute_agent_run_activity")
    async def execute(params: dict) -> dict:
        calls["execute"] += 1
        return {"status": execute_status, "action_type": "send_email"}

    @activity.defn(name="continue_agent_run_activity")
    async def continue_(params: dict) -> dict:
        calls["continue"].append(params["continuation"])
        return {"status": continue_status, "action_type": None}

    @activity.defn(name="expire_agent_run_activity")
    async def expire(params: dict) -> None:
        calls["expire"] += 1

    return calls, [execute, continue_, expire]


@pytest.mark.asyncio
async def test_agent_run_waits_for_approval_then_continues_once():
    calls, activities = _agent_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AgentRunWorkflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                AgentRunInput(run_id="r1", user_id="u1"),
                id=agent_run_workflow_id("r1"),
                task_queue=QUEUE,
            )
            await _wait_for(handle, AgentRunWorkflow.status, "awaiting_approval")
            await handle.signal(
                AgentRunWorkflow.decide,
                ApprovalDecision(
                    approved=True, action_type="send_email", continuation={"type": "send_email"}
                ),
            )
            result = await handle.result()

    assert result["status"] == "completed"
    assert calls["execute"] == 1
    assert calls["continue"] == [{"type": "send_email"}]


@pytest.mark.asyncio
async def test_agent_run_expires_when_nobody_decides():
    calls, activities = _agent_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AgentRunWorkflow], activities=activities
        ):
            result = await env.client.execute_workflow(
                AgentRunWorkflow.run,
                AgentRunInput(run_id="r2", user_id="u1", approval_timeout_s=3600),
                id=agent_run_workflow_id("r2"),
                task_queue=QUEUE,
            )

    assert result == {"status": "expired"}
    assert calls["expire"] == 1
    assert calls["continue"] == []


@pytest.mark.asyncio
async def test_agent_run_rejection_never_continues():
    calls, activities = _agent_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AgentRunWorkflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                AgentRunInput(run_id="r3", user_id="u1"),
                id=agent_run_workflow_id("r3"),
                task_queue=QUEUE,
            )
            await _wait_for(handle, AgentRunWorkflow.status, "awaiting_approval")
            await handle.signal(AgentRunWorkflow.decide, ApprovalDecision(approved=False))
            result = await handle.result()

    assert result == {"status": "cancelled"}
    assert calls["continue"] == []


@pytest.mark.asyncio
async def test_signal_with_start_approves_a_run_created_outside_a_workflow():
    """Inline API routes and follow-up drafts create checkpoints with no
    workflow; approval starts one at the checkpoint with the decision
    already delivered, and execution is skipped."""
    calls, activities = _agent_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AgentRunWorkflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                AgentRunInput(run_id="r4", user_id="u1", start_at_checkpoint=True),
                id=agent_run_workflow_id("r4"),
                task_queue=QUEUE,
                start_signal="decide",
                start_signal_args=[
                    ApprovalDecision(approved=True, continuation={"type": "resume_ready"})
                ],
            )
            result = await handle.result()

    assert result["status"] == "completed"
    assert calls["execute"] == 0
    assert calls["continue"] == [{"type": "resume_ready"}]


@pytest.mark.asyncio
async def test_a_continuation_is_never_retried():
    """A continuation may have sent an email or clicked Submit: a failure
    must end the workflow, not replay the side effect."""
    attempts = []

    @activity.defn(name="execute_agent_run_activity")
    async def execute(params: dict) -> dict:
        return {"status": "awaiting_approval"}

    @activity.defn(name="continue_agent_run_activity")
    async def continue_(params: dict) -> dict:
        attempts.append(1)
        raise RuntimeError("Gmail timed out after sending?")

    @activity.defn(name="expire_agent_run_activity")
    async def expire(params: dict) -> None:
        return None

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=QUEUE,
            workflows=[AgentRunWorkflow],
            activities=[execute, continue_, expire],
        ):
            handle = await env.client.start_workflow(
                AgentRunWorkflow.run,
                AgentRunInput(run_id="r5", user_id="u1"),
                id=agent_run_workflow_id("r5"),
                task_queue=QUEUE,
            )
            await _wait_for(handle, AgentRunWorkflow.status, "awaiting_approval")
            await handle.signal(
                AgentRunWorkflow.decide, ApprovalDecision(approved=True, continuation={})
            )
            with pytest.raises(WorkflowFailureError):
                await handle.result()

    assert attempts == [1]


# ── FollowupWorkflow ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_followups_fire_on_day_5_and_day_12_after_applying():
    fired_at = []

    async with await WorkflowEnvironment.start_time_skipping() as env:
        start = await env.get_current_time()

        @activity.defn(name="draft_followup_activity")
        async def draft(params: dict) -> dict:
            fired_at.append((params["day"], activity.info().current_attempt_scheduled_time))
            return {"status": "awaiting_approval"}

        # Applied four days ago: day 5 is ~1 day away, day 12 ~8 days away.
        applied_at = start - timedelta(days=4)
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[FollowupWorkflow], activities=[draft]
        ):
            result = await env.client.execute_workflow(
                FollowupWorkflow.run,
                FollowupInput(user_id="u1", application_id="a1", applied_at=applied_at.isoformat()),
                id="followup/a1",
                task_queue=QUEUE,
            )

    assert result == {"status": "completed", "drafted": [5, 12]}
    (day5, t5), (day12, t12) = fired_at
    assert (day5, day12) == (5, 12)
    assert abs((t5 - (applied_at + timedelta(days=5))).total_seconds()) < 60
    assert abs((t12 - (applied_at + timedelta(days=12))).total_seconds()) < 60


@pytest.mark.asyncio
async def test_followups_stop_when_the_recruiter_replied():
    days = []

    @activity.defn(name="draft_followup_activity")
    async def draft(params: dict) -> dict:
        days.append(params["day"])
        return {"status": "cancelled", "reason": "recruiter_replied"}

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[FollowupWorkflow], activities=[draft]
        ):
            result = await env.client.execute_workflow(
                FollowupWorkflow.run,
                FollowupInput(
                    user_id="u1", application_id="a2", applied_at=datetime.now(UTC).isoformat()
                ),
                id="followup/a2",
                task_queue=QUEUE,
            )

    assert result["status"] == "stopped"
    assert days == [5]


# ── JobSearchWorkflow ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_job_search_marks_the_run_failed_when_the_search_cannot_finish():
    failed = []

    @activity.defn(name="run_job_search_activity")
    async def search(params: dict) -> dict:
        raise RuntimeError("scraper crashed")

    @activity.defn(name="fail_job_search_activity")
    async def fail(params: dict) -> None:
        failed.append(params["run_id"])

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[JobSearchWorkflow], activities=[search, fail]
        ):
            result = await env.client.execute_workflow(
                JobSearchWorkflow.run,
                JobSearchInput(run_id="run-9", user_id="u1", params={"search_query": "python"}),
                id="job-search/run-9",
                task_queue=QUEUE,
            )

    assert result == {"status": "failed"}
    assert failed == ["run-9"]


# ── AutoApplyWorkflow, extension mode ───────────────────────────────────


def _extension_activities():
    calls = {"created": [], "finished": [], "followups": []}

    @activity.defn(name="reserve_application_attempt")
    async def reserve(params: dict) -> dict:
        return {
            "attempt_id": "att-1",
            "run_id": params["run_id"],
            "job_url": "https://www.linkedin.com/jobs/view/1",
            "company": "Acme",
            "role": "Backend Engineer",
            "pdf_document_id": "doc-1",
            "resume_sha256": "abc",
        }

    @activity.defn(name="create_extension_task_activity")
    async def create(params: dict) -> dict:
        calls["created"].append(params)
        return {"task_id": "task-1"}

    @activity.defn(name="finish_extension_task_activity")
    async def finish(params: dict) -> dict:
        calls["finished"].append({"outcome": params["outcome"], "details": params["details"]})
        return {"outcome": params["outcome"], "applied_at": "2026-09-25T00:00:00+00:00"}

    @activity.defn(name="schedule_followup_activity")
    async def followup(params: dict) -> None:
        calls["followups"].append(params)

    @activity.defn(name="run_application_stage_activity")
    async def stage(params: dict) -> dict:
        raise AssertionError("extension mode must not drive a server browser")

    @activity.defn(name="apply_answers_and_resume_activity")
    async def answers(params: dict) -> dict:
        raise AssertionError("extension mode must not drive a server browser")

    return calls, [reserve, create, finish, followup, stage, answers]


def _intent(**overrides):
    return AutoApplyIntent(
        **{
            "user_id": "u1",
            "job_application_id": "j1",
            "mode": "extension",
            "claim_timeout_s": 3600,
            "complete_timeout_s": 3600,
            **overrides,
        }
    )


@pytest.mark.asyncio
async def test_extension_submission_records_outcome_and_schedules_followups():
    calls, activities = _extension_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AutoApplyWorkflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                _intent(),
                id=auto_apply_workflow_id("u1", "j1"),
                task_queue=QUEUE,
            )
            await _wait_for_state(handle, "waiting_for_extension")
            await handle.signal(AutoApplyWorkflow.extension_update, {"stage": "claimed"})
            await handle.signal(AutoApplyWorkflow.extension_update, {"stage": "review"})
            await handle.signal(
                AutoApplyWorkflow.extension_update,
                {
                    "stage": "submitted",
                    "details": {"confirmation_text": "Your application was sent"},
                },
            )
            result = await handle.result()

    assert result == {"status": "completed", "result": {"outcome": "submitted"}}
    assert calls["created"][0]["job_url"] == "https://www.linkedin.com/jobs/view/1"
    assert calls["finished"] == [
        {
            "outcome": "submitted",
            "details": {"confirmation_text": "Your application was sent"},
        }
    ]
    assert calls["followups"][0]["applied_at"] == "2026-09-25T00:00:00+00:00"


@pytest.mark.asyncio
async def test_extension_task_expires_when_no_browser_claims_it():
    calls, activities = _extension_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AutoApplyWorkflow], activities=activities
        ):
            result = await env.client.execute_workflow(
                AutoApplyWorkflow.run,
                _intent(job_application_id="j2"),
                id=auto_apply_workflow_id("u1", "j2"),
                task_queue=QUEUE,
            )

    assert result["status"] == "expired"
    assert calls["finished"][0]["outcome"] == "expired"
    assert calls["followups"] == []


@pytest.mark.asyncio
async def test_extension_task_can_be_cancelled_while_the_user_reviews():
    calls, activities = _extension_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AutoApplyWorkflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                _intent(job_application_id="j3"),
                id=auto_apply_workflow_id("u1", "j3"),
                task_queue=QUEUE,
            )
            await _wait_for_state(handle, "waiting_for_extension")
            await handle.signal(AutoApplyWorkflow.extension_update, {"stage": "claimed"})
            await _wait_for_state(handle, "in_browser")
            await handle.signal(AutoApplyWorkflow.cancel)
            result = await handle.result()

    assert result["status"] == "cancelled"
    assert calls["finished"][0]["outcome"] == "cancelled"
    assert calls["followups"] == []


@pytest.mark.asyncio
async def test_extension_failure_is_terminal_and_keeps_the_reason():
    calls, activities = _extension_activities()
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client, task_queue=QUEUE, workflows=[AutoApplyWorkflow], activities=activities
        ):
            handle = await env.client.start_workflow(
                AutoApplyWorkflow.run,
                _intent(job_application_id="j4"),
                id=auto_apply_workflow_id("u1", "j4"),
                task_queue=QUEUE,
            )
            await _wait_for_state(handle, "waiting_for_extension")
            await handle.signal(
                AutoApplyWorkflow.extension_update,
                {
                    "stage": "failed",
                    "details": {"error": "External application"},
                },
            )
            # A late duplicate must not change the recorded outcome.
            await handle.signal(AutoApplyWorkflow.extension_update, {"stage": "submitted"})
            result = await handle.result()

    assert result["status"] == "failed"
    assert calls["finished"] == [
        {"outcome": "failed", "details": {"error": "External application"}}
    ]


async def _wait_for_state(handle, expected):
    for _ in range(200):
        status = await handle.query(AutoApplyWorkflow.status)
        if status.state == expected:
            return
        await asyncio.sleep(0.02)
    raise AssertionError(f"workflow never reached {expected!r}")


# ── Schedules ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mode,expected",
    [
        ("extension", {"daily-job-search", "maintenance"}),
        ("server_browser", {"daily-job-search", "maintenance", "application-status-check"}),
    ],
)
async def test_ensure_schedules_registers_recurring_jobs(monkeypatch, mode, expected):
    from temporalio.client import ScheduleAlreadyRunningError

    from app.core.config import settings
    from app.workflows import scheduled

    monkeypatch.setattr(settings, "APPLY_EXECUTION_MODE", mode)
    created = {}

    async def create_schedule(schedule_id, schedule):
        if schedule_id == "maintenance":
            raise ScheduleAlreadyRunningError()
        created[schedule_id] = schedule

    handles = {}

    def get_schedule_handle(schedule_id):
        handle = MagicMock()
        handle.update = AsyncMock()
        handle.delete = AsyncMock()
        handles[schedule_id] = handle
        return handle

    client = MagicMock()
    client.create_schedule = AsyncMock(side_effect=create_schedule)
    client.get_schedule_handle = MagicMock(side_effect=get_schedule_handle)

    await scheduled.ensure_schedules(client)

    assert set(created) | {"maintenance"} == expected
    handles["maintenance"].update.assert_awaited_once()  # existing one is updated
    if mode == "extension":
        # The status check needs a server-side portal session; removed here.
        handles["application-status-check"].delete.assert_awaited_once()
    daily = created["daily-job-search"]
    assert daily.spec.intervals[0].every == timedelta(hours=settings.DAILY_SEARCH_INTERVAL_HOURS)


def test_every_started_workflow_is_registered_with_the_worker():
    from app.workflows.registry import ACTIVITIES, WORKFLOWS
    from app.workflows.scheduled import (
        DailySearchWorkflow,
        MaintenanceWorkflow,
        StatusCheckWorkflow,
    )

    for workflow_cls in (
        AgentRunWorkflow,
        AutoApplyWorkflow,
        FollowupWorkflow,
        JobSearchWorkflow,
        DailySearchWorkflow,
        MaintenanceWorkflow,
        StatusCheckWorkflow,
    ):
        assert workflow_cls in WORKFLOWS
    names = {a.__temporal_activity_definition.name for a in ACTIVITIES}
    assert {
        "execute_agent_run_activity",
        "continue_agent_run_activity",
        "expire_agent_run_activity",
        "create_extension_task_activity",
        "finish_extension_task_activity",
        "run_job_search_activity",
        "fail_job_search_activity",
        "draft_followup_activity",
        "maintenance_activity",
        "reserve_application_attempt",
    } <= names
