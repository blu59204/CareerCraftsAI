"""Temporal activities for AutoApplyWorkflow.

Every activity here is a thin wrapper around code that already exists and is
already tested on the BullMQ/WorkflowTask path (application_workflow.py,
workflow_service.py, profile_service.py, followup_agent.py) — there is
exactly one implementation of "drive a browser through an application form,"
regardless of which engine (BullMQ or Temporal) is orchestrating it. Activity
functions may do real I/O (DB, browser, network); workflow code in
auto_apply.py must never do so directly, per Temporal's determinism rules.

No credentials, resume bytes, browser cookies, or form contents are ever
returned from an activity into workflow history — only references (ids,
hashes, short status strings). Everything logged here goes through the
standard `logging` module (never print raw secrets/cookies).
"""
from __future__ import annotations

import logging
import uuid as _uuid
from datetime import UTC, datetime

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def reserve_application_attempt(params: dict) -> dict:
    """Reserve (or reuse) the ApplicationAttempt + AgentRun for this
    workflow. Mirrors jobs.py's prepare_application_apply reservation logic
    exactly, so a Temporal-backed and a BullMQ-backed apply share one
    idempotency ledger and one set of guard rails.

    params: {user_id, job_application_id, workflow_id, run_id}. run_id is
    generated once by the caller (the API route or, for a retry driven by
    the workflow itself, the same value the workflow passed the first time)
    and MUST NOT be generated inside this function: Temporal executes
    activities at-least-once, so a retry after a transient failure (e.g. the
    commit below succeeds but the reply to Temporal is lost) must reuse the
    exact same AgentRun id rather than creating a second, orphaned one.

    Returns: {attempt_id, run_id, job_url, company, role, pdf_document_id, resume_sha256}
    Raises ValueError (ownership/state violations) — non-retryable by the
    workflow's own error-type handling in auto_apply.py.
    """
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.models.db import AgentRun, ApplicationAttempt, JobApplication
    from app.services.application_workflow import load_resume
    from app.services.workflow_service import ACTIVE_SUBMISSION_STATES

    user_id = _uuid.UUID(params["user_id"])
    job_application_id = _uuid.UUID(params["job_application_id"])
    workflow_id = params["workflow_id"]
    run_id = _uuid.UUID(params["run_id"])

    async with AsyncSessionLocal() as db:
        app_row = (await db.execute(
            select(JobApplication).where(
                JobApplication.id == job_application_id, JobApplication.user_id == user_id,
            ).with_for_update()
        )).scalar_one_or_none()
        if not app_row:
            raise ValueError("Application not found")
        if not app_row.job_url:
            raise ValueError("Application has no job URL")
        if app_row.status == "applied":
            raise ValueError("Already applied to this job")
        if not app_row.resume_id:
            raise ValueError("Attach an approved resume to this application before applying")

        existing = (await db.execute(
            select(ApplicationAttempt).where(
                ApplicationAttempt.user_id == user_id,
                ApplicationAttempt.job_application_id == job_application_id,
            ).with_for_update()
        )).scalar_one_or_none()
        # A retry of THIS SAME workflow (same workflow_id) reusing its own
        # attempt is fine; a different workflow/caller colliding with an
        # active submission is not.
        owned_by_other_workflow = existing and existing.workflow_id != workflow_id
        if existing and existing.state in ACTIVE_SUBMISSION_STATES and owned_by_other_workflow:
            raise ValueError(f"An application attempt is already {existing.state}")

        _, resume_sha256 = await load_resume(user_id, str(app_row.resume_id))

        # Idempotent: a retry of this same activity invocation (same run_id)
        # must not insert a second AgentRun row.
        agent_run = await db.get(AgentRun, run_id)
        if agent_run is None:
            db.add(AgentRun(
                id=run_id, user_id=user_id, agent_type="apply_prepare", status="running",
                input={
                    "application_id": str(job_application_id),
                    "engine": "temporal", "workflow_id": workflow_id,
                },
            ))

        if existing:
            attempt = existing
            attempt.state = "preparing"
            attempt.run_id = run_id
            attempt.workflow_id = workflow_id
            attempt.submission_token = None
            attempt.external_application_id = None
            attempt.confirmation_url = None
            attempt.confirmation_text = None
            attempt.approved_snapshot_hash = None
            attempt.last_error = None
            attempt.submitted_at = None
            attempt.verified_at = None
        else:
            attempt = ApplicationAttempt(
                user_id=user_id, job_application_id=job_application_id, run_id=run_id,
                workflow_id=workflow_id, state="preparing",
            )
            db.add(attempt)
        await db.flush()
        attempt_id = str(attempt.id)
        await db.commit()

    return {
        "attempt_id": attempt_id, "run_id": str(run_id), "job_url": app_row.job_url,
        "company": app_row.company, "role": app_row.role,
        "pdf_document_id": str(app_row.resume_id), "resume_sha256": resume_sha256,
    }


async def _record_stage_result(run_id: str, result: dict) -> dict:
    """Shared by both stage-advancing activities below: write the result
    into the same AgentRun.status/output shape workflow_service.execute_task
    already produces for the BullMQ path, and publish the same SSE event —
    so the existing frontend polling/SSE UI works identically regardless of
    which engine ran the stage."""
    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import publish
    from app.models.db import AgentRun

    status = result.get("status", "failed")
    normalized = status if status in {"completed", "awaiting_approval", "failed"} else "failed"
    is_awaiting = normalized == "awaiting_approval"
    output = result.get("pending_action") if is_awaiting else result.get("result")

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, _uuid.UUID(run_id), with_for_update=True)
        if run is not None:
            run.status = normalized
            default_error = {"error": result.get("error", "Application stage produced no result")}
            run.output = output or default_error
            run.completed_at = None if is_awaiting else datetime.now(UTC)
            await db.commit()

    event = {"completed": "complete", "awaiting_approval": "checkpoint", "failed": "error"}
    event = event[normalized]
    publish(run_id, event, output)
    return result


@activity.defn
async def run_application_stage_activity(params: dict) -> dict:
    """Drives one browser_prepare/browser_input/browser_review step via the
    existing application_workflow.run_application_stage — the same function
    the BullMQ path calls from workflow_service.continue_action.

    params: {run_id, pending}

    Heartbeats once at entry so a lost worker is detected via
    heartbeat_timeout rather than only start_to_close_timeout; the
    underlying browser calls (~15-30s each, bounded) don't have natural
    mid-call checkpoints to heartbeat from without changing
    application_workflow.py's browser stage internals, which is out of
    scope for this activity wrapper.
    """
    from app.core.database import AsyncSessionLocal
    from app.models.db import AgentRun
    from app.services.application_workflow import run_application_stage

    run_id = params["run_id"]
    pending = params["pending"]

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, _uuid.UUID(run_id))
        if run is None:
            raise ValueError(f"AgentRun {run_id} not found")

    activity.heartbeat("starting application stage")
    result = await run_application_stage(run, pending)
    return await _record_stage_result(run_id, result)


@activity.defn
async def apply_answers_and_resume_activity(params: dict) -> dict:
    """Saves user-provided answers to candidate_answers, then resumes
    preparation — the Temporal-path equivalent of workflow_service's
    continue_action "application_answers_required" branch. Kept as its own
    activity (rather than inlined in the workflow) since workflow code must
    never touch the database directly.

    params: {run_id, user_id, answers: {field_id: value}, fields: [...], pending}
    """
    from app.applications import profile_service
    from app.core.database import AsyncSessionLocal
    from app.models.db import AgentRun
    from app.services.application_workflow import run_application_stage

    run_id = params["run_id"]
    user_id = _uuid.UUID(params["user_id"])
    answers = params.get("answers") or {}
    fields_by_id = {f.get("field_id"): f for f in params.get("fields", [])}

    async with AsyncSessionLocal() as db:
        for field_id, value in answers.items():
            meta = fields_by_id.get(field_id, {})
            question_key = meta.get("question_key") or field_id
            await profile_service.save_approved_answer(
                db, user_id, question_key, meta.get("label", question_key), value,
            )
        await db.commit()

    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, _uuid.UUID(run_id))
        if run is None:
            raise ValueError(f"AgentRun {run_id} not found")

    excluded_keys = {"answers", "fields", "type", "message"}
    resumed_pending = {k: v for k, v in params["pending"].items() if k not in excluded_keys}
    resumed_pending["type"] = "browser_input"
    activity.heartbeat("resuming preparation with saved answers")
    result = await run_application_stage(run, resumed_pending)
    return await _record_stage_result(run_id, result)


@activity.defn
async def schedule_followup_activity(params: dict) -> None:
    """Only ever called after a confirmed ("verified") submission."""
    from sqlalchemy import select

    from app.agents.followup_agent import schedule_followups
    from app.core.database import AsyncSessionLocal
    from app.models.db import JobApplication

    user_id = params["user_id"]
    job_application_id = _uuid.UUID(params["job_application_id"])
    async with AsyncSessionLocal() as db:
        app_row = (await db.execute(
            select(JobApplication).where(JobApplication.id == job_application_id)
        )).scalar_one_or_none()
        applied_at = app_row.applied_at if app_row else None
    await schedule_followups(user_id, str(job_application_id), applied_at or datetime.now(UTC))
