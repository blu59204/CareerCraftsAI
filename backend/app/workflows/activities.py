"""Application reservation and follow-up activities; submission runs in the extension."""

from __future__ import annotations

import uuid as _uuid
from datetime import UTC, datetime

from temporalio import activity


@activity.defn
async def reserve_application_attempt(params: dict) -> dict:
    """Reserve (or reuse) the ApplicationAttempt + AgentRun for this
    workflow — the single place an application attempt is reserved, for
    both the extension and the server-browser modes.

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

    from app.applications.submission import load_resume
    from app.core.database import AsyncSessionLocal
    from app.models.db import AgentRun, ApplicationAttempt, JobApplication
    from app.services.workflow_service import ACTIVE_SUBMISSION_STATES

    user_id = _uuid.UUID(params["user_id"])
    job_application_id = _uuid.UUID(params["job_application_id"])
    workflow_id = params["workflow_id"]
    run_id = _uuid.UUID(params["run_id"])

    async with AsyncSessionLocal() as db:
        app_row = (
            await db.execute(
                select(JobApplication)
                .where(
                    JobApplication.id == job_application_id,
                    JobApplication.user_id == user_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if not app_row:
            raise ValueError("Application not found")
        if not app_row.job_url:
            raise ValueError("Application has no job URL")
        if app_row.status == "applied":
            raise ValueError("Already applied to this job")
        if not app_row.resume_id:
            raise ValueError("Attach an approved resume to this application before applying")

        existing = (
            await db.execute(
                select(ApplicationAttempt)
                .where(
                    ApplicationAttempt.user_id == user_id,
                    ApplicationAttempt.job_application_id == job_application_id,
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        # Workflow IDs are reused across executions. Even the same ID must
        # not reset a submitted or uncertain attempt when started again.
        if existing and existing.state in ACTIVE_SUBMISSION_STATES:
            raise ValueError(f"An application attempt is already {existing.state}")

        _, resume_sha256 = await load_resume(user_id, str(app_row.resume_id))

        # Idempotent: a retry of this same activity invocation (same run_id)
        # must not insert a second AgentRun row.
        agent_run = await db.get(AgentRun, run_id)
        if agent_run is None:
            db.add(
                AgentRun(
                    id=run_id,
                    user_id=user_id,
                    agent_type="apply_prepare",
                    status="running",
                    input={
                        "application_id": str(job_application_id),
                        "engine": "temporal",
                        "workflow_id": workflow_id,
                    },
                )
            )

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
                user_id=user_id,
                job_application_id=job_application_id,
                run_id=run_id,
                workflow_id=workflow_id,
                state="preparing",
            )
            db.add(attempt)
        await db.flush()
        attempt_id = str(attempt.id)
        await db.commit()

    return {
        "attempt_id": attempt_id,
        "run_id": str(run_id),
        "job_url": app_row.job_url,
        "company": app_row.company,
        "role": app_row.role,
        "pdf_document_id": str(app_row.resume_id),
        "resume_sha256": resume_sha256,
    }


@activity.defn
async def schedule_followup_activity(params: dict) -> None:
    """Only ever called after a confirmed submission. Starts the
    application's FollowupWorkflow (idempotent per application)."""
    from sqlalchemy import select

    from app.agents.followup_agent import schedule_followups
    from app.core.database import AsyncSessionLocal
    from app.models.db import JobApplication

    user_id = params["user_id"]
    job_application_id = _uuid.UUID(params["job_application_id"])
    applied_at = datetime.fromisoformat(params["applied_at"]) if params.get("applied_at") else None
    if applied_at is None:
        async with AsyncSessionLocal() as db:
            app_row = (
                await db.execute(
                    select(JobApplication).where(JobApplication.id == job_application_id)
                )
            ).scalar_one_or_none()
            applied_at = app_row.applied_at if app_row else None
    await schedule_followups(user_id, str(job_application_id), applied_at or datetime.now(UTC))
