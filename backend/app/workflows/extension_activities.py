"""Activities for AutoApplyWorkflow's extension mode.

The workflow hands the application to the user's own browser through an
extension_tasks row, then waits for the extension's progress signals. Only
references and short status strings enter workflow history — never form
contents, resumes or cookies.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from temporalio import activity

logger = logging.getLogger(__name__)

OPEN_TASK_STATUSES = ("pending", "claimed", "filling", "needs_input", "review", "login_required")

WAITING_MESSAGE = (
    "Waiting for your browser. Keep Chrome open with the CareerCraft extension "
    "connected, and stay signed in to the job site."
)


def detect_platform(job_url: str) -> str:
    url = (job_url or "").lower()
    for needle, platform in (
        ("linkedin.com", "linkedin"),
        ("naukri.com", "naukri"),
        ("indeed.", "indeed"),
        ("greenhouse.io", "greenhouse"),
        ("lever.co", "lever"),
        ("ashbyhq.com", "ashby"),
        ("myworkdayjobs.com", "workday"),
        ("foundit.", "foundit"),
        ("instahyre.com", "instahyre"),
    ):
        if needle in url:
            return platform
    return "generic"


@activity.defn
async def create_extension_task_activity(params: dict) -> dict:
    """Create (or reuse) the open extension task for this application."""
    from sqlalchemy import select

    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import publish
    from app.models.db import AgentRun, ExtensionTask

    user_id = uuid.UUID(params["user_id"])
    application_id = uuid.UUID(params["job_application_id"])
    run_id = uuid.UUID(params["run_id"])
    payload = {
        "job_url": params["job_url"],
        "company": params.get("company"),
        "role": params.get("role"),
        "platform": detect_platform(params["job_url"]),
        "resume_document_id": params.get("pdf_document_id"),
        "attempt_id": params.get("attempt_id"),
    }

    async with AsyncSessionLocal() as db:
        task = (
            await db.execute(
                select(ExtensionTask)
                .where(
                    ExtensionTask.user_id == user_id,
                    ExtensionTask.job_application_id == application_id,
                    ExtensionTask.status.in_(OPEN_TASK_STATUSES),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if task is not None and task.workflow_id != params["workflow_id"]:
            # A task from an earlier, finished attempt: retire it.
            task.status = "cancelled"
            task.completed_at = datetime.now(UTC)
            task = None
        if task is None:
            task = ExtensionTask(
                id=uuid.uuid4(),
                user_id=user_id,
                run_id=run_id,
                job_application_id=application_id,
                workflow_id=params["workflow_id"],
                kind="apply",
                status="pending",
                payload=payload,
            )
            db.add(task)

        output = {
            "type": "extension_apply",
            "stage": "waiting_for_extension",
            "message": WAITING_MESSAGE,
            "task_id": str(task.id),
            "job_url": payload["job_url"],
            "platform": payload["platform"],
        }
        run = await db.get(AgentRun, run_id, with_for_update=True)
        if run is not None:
            run.status = "queued"
            run.output = output
        await db.commit()
        task_id = str(task.id)

    publish(str(run_id), "thinking", output)
    return {"task_id": task_id}


_RUN_STATUS = {
    "submitted": "completed",
    "failed": "failed",
    "cancelled": "cancelled",
    "expired": "expired",
}
_ATTEMPT_STATE = {
    "submitted": "submitted",
    "failed": "failed",
    "cancelled": "cancelled",
    "expired": "cancelled",
}
_MESSAGES = {
    "submitted": "Application submitted from your browser",
    "failed": "The application could not be completed in your browser",
    "cancelled": "Application cancelled",
    "expired": "No browser picked up this application in time — "
    "check that the extension is connected, then apply again",
}


@activity.defn
async def finish_extension_task_activity(params: dict) -> dict:
    """Record the final outcome on the task, attempt, application and run."""
    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import publish
    from app.models.db import AgentRun, ApplicationAttempt, ExtensionTask, JobApplication

    outcome = params["outcome"]
    details = params.get("details") or {}
    now = datetime.now(UTC)
    confirmed = bool(details.get("confirmation_text") or details.get("confirmation_url"))

    async with AsyncSessionLocal() as db:
        task = await db.get(ExtensionTask, uuid.UUID(params["task_id"]), with_for_update=True)
        if task is not None and task.status in OPEN_TASK_STATUSES:
            task.status = outcome
            task.result = {
                k: details.get(k)
                for k in (
                    "message",
                    "confirmation_text",
                    "confirmation_url",
                    "error",
                )
                if details.get(k)
            }
            task.completed_at = now

        if params.get("attempt_id"):
            attempt = await db.get(
                ApplicationAttempt,
                uuid.UUID(params["attempt_id"]),
                with_for_update=True,
            )
            if attempt is not None:
                attempt.state = (
                    "verified" if outcome == "submitted" and confirmed else _ATTEMPT_STATE[outcome]
                )
                attempt.confirmation_text = (details.get("confirmation_text") or "")[:2000] or None
                attempt.confirmation_url = details.get("confirmation_url") or None
                if outcome == "submitted":
                    attempt.submitted_at = now
                    attempt.verified_at = now if confirmed else None
                else:
                    attempt.last_error = (details.get("error") or _MESSAGES[outcome])[:2000]

        applied_at = None
        application = await db.get(
            JobApplication,
            uuid.UUID(params["job_application_id"]),
            with_for_update=True,
        )
        if outcome == "submitted" and application is not None:
            application.status = "applied"
            application.applied_at = application.applied_at or now
            application.followup_day5 = (
                application.followup_day5 or application.applied_at + timedelta(days=5)
            )
            application.followup_day12 = (
                application.followup_day12 or application.applied_at + timedelta(days=12)
            )
            applied_at = application.applied_at

        output = {
            "type": "extension_apply",
            "stage": outcome,
            "outcome": outcome,
            "message": details.get("message") or _MESSAGES[outcome],
            "confirmation_text": (details.get("confirmation_text") or "")[:500] or None,
            "confirmation_url": details.get("confirmation_url") or None,
            "error": details.get("error") if outcome != "submitted" else None,
        }
        run = await db.get(AgentRun, uuid.UUID(params["run_id"]), with_for_update=True)
        if run is not None:
            run.status = _RUN_STATUS[outcome]
            run.output = output
            run.completed_at = now
        await db.commit()

    publish(params["run_id"], "complete" if outcome == "submitted" else "error", output)
    return {"outcome": outcome, "applied_at": applied_at.isoformat() if applied_at else None}
