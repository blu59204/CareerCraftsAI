"""Activities for job search, follow-ups and the recurring Schedules."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def run_job_search_activity(params: dict) -> dict:
    from app.services.scheduled_jobs import JobSearchTrigger, run_job_search

    result = await run_job_search(JobSearchTrigger(**params))
    return {"status": result.get("status", "failed")}


@activity.defn
async def fail_job_search_activity(params: dict) -> None:
    """Close out a run whose search activity could not finish at all."""
    from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR
    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import emit
    from app.models.db import AgentRun

    run_id = params["run_id"]
    async with AsyncSessionLocal() as db:
        run = await db.get(AgentRun, uuid.UUID(run_id), with_for_update=True)
        if run is None or run.status not in {"queued", "running"}:
            return
        run.status = "failed"
        run.output = {"error": CLIENT_SAFE_AGENT_ERROR}
        run.completed_at = datetime.now(UTC)
        await db.commit()
    emit(run_id, "error", CLIENT_SAFE_AGENT_ERROR)


@activity.defn
async def draft_followup_activity(params: dict) -> dict:
    from app.services.scheduled_jobs import FollowupTrigger, run_followup

    result = await run_followup(FollowupTrigger(**params))
    return {"status": result.get("status"), "reason": result.get("reason")}


@activity.defn
async def daily_search_activity(params: dict) -> dict:
    from app.services.scheduled_jobs import StatusCheckTrigger, daily_search

    result = await daily_search(StatusCheckTrigger(user_id=params.get("user_id", "all")))
    return {k: v for k, v in result.items() if isinstance(v, (int, str))}


@activity.defn
async def status_check_activity(params: dict) -> dict:
    from app.services.scheduled_jobs import StatusCheckTrigger, check_application_status

    result = await check_application_status(
        StatusCheckTrigger(user_id=params.get("user_id", "all"))
    )
    return {"updated_count": result.get("updated_count", 0)}


# Runs whose workflow is gone but whose row still says it is in progress
# (workflow terminated by hand, history lost, pre-Temporal rows).
_STALE_AFTER = timedelta(minutes=15)
_OPEN_RUN_STATUSES = ("queued", "running", "awaiting_approval")


def _workflow_id_for(run) -> str:
    from app.workflows.agent_run import agent_run_workflow_id
    from app.workflows.job_search import job_search_workflow_id

    explicit = (run.input or {}).get("workflow_id")
    if explicit:
        return explicit
    if run.agent_type == "job_search":
        return job_search_workflow_id(str(run.id))
    return agent_run_workflow_id(str(run.id))


@activity.defn
async def maintenance_activity(params: dict) -> dict:
    """Reconcile agent_runs with Temporal, expire orphaned extension tasks,
    and reap server-side browser sandboxes."""
    from sqlalchemy import and_, or_, select
    from temporalio.client import WorkflowExecutionStatus
    from temporalio.service import RPCError, RPCStatusCode

    from app.core.config import settings
    from app.core.database import AsyncSessionLocal
    from app.core.event_bus import publish
    from app.core.temporal_client import get_temporal_client
    from app.models.db import AgentRun, ApplicationAttempt, ExtensionTask

    client = await get_temporal_client()
    now = datetime.now(UTC)
    reconciled = 0

    approval_cutoff = now - timedelta(seconds=settings.AGENT_APPROVAL_TIMEOUT_S)
    async with AsyncSessionLocal() as db:
        # In-progress rows get 15 minutes; checkpoints the full approval
        # window, since inline-route runs wait at a checkpoint with no
        # workflow until the user decides (signal-with-start creates one).
        runs = (
            (
                await db.execute(
                    select(AgentRun)
                    .where(
                        or_(
                            and_(
                                AgentRun.status.in_(("queued", "running")),
                                AgentRun.started_at < now - _STALE_AFTER,
                            ),
                            and_(
                                AgentRun.status == "awaiting_approval",
                                AgentRun.started_at < approval_cutoff,
                            ),
                        )
                    )
                    .order_by(AgentRun.started_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        candidates = [(run.id, _workflow_id_for(run)) for run in runs]

    for run_id, workflow_id in candidates:
        try:
            description = await client.get_workflow_handle(workflow_id).describe()
            if description.status == WorkflowExecutionStatus.RUNNING:
                continue
        except RPCError as exc:
            if exc.status != RPCStatusCode.NOT_FOUND:
                logger.warning("Could not describe %s: %s", workflow_id, exc)
                continue

        async with AsyncSessionLocal() as db:
            run = await db.get(AgentRun, run_id, with_for_update=True)
            if run is None or run.status not in _OPEN_RUN_STATUSES:
                continue
            expired = run.status == "awaiting_approval"
            run.status = "expired" if expired else "failed"
            run.output = {
                "error": (
                    "Approval expired — run the agent again when you are ready"
                    if expired
                    else "The run stopped without reporting a result; start it again"
                )
            }
            run.completed_at = now
            # A worker that died mid-submit leaves the attempt claimed
            # ("submitting"); the submit is never retried, so record that the
            # outcome must be verified by hand rather than blocking re-apply.
            for attempt in (
                (
                    await db.execute(
                        select(ApplicationAttempt).where(
                            ApplicationAttempt.run_id == run_id,
                            ApplicationAttempt.state == "submitting",
                        )
                    )
                )
                .scalars()
                .all()
            ):
                attempt.state = "outcome_unknown"
                attempt.last_error = (
                    "Worker stopped during submission; verify the external outcome "
                    "before starting again"
                )
            for task in (
                (
                    await db.execute(
                        select(ExtensionTask).where(
                            ExtensionTask.run_id == run_id,
                            ExtensionTask.status.in_(
                                ("pending", "claimed", "filling", "needs_input", "review")
                            ),
                        )
                    )
                )
                .scalars()
                .all()
            ):
                task.status = "expired"
                task.completed_at = now
            await db.commit()
            reconciled += 1
        publish(str(run_id), "error", {"error": "Run stopped"})

    if settings.APPLY_EXECUTION_MODE == "server_browser":
        from app.services.sandbox_service import reap_sessions

        try:
            await reap_sessions()
        except Exception:
            logger.exception("Browser reaper failed")

    return {"reconciled": reconciled}
