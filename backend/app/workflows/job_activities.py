"""Activities for job search, follow-ups and the recurring Schedules."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from temporalio import activity

logger = logging.getLogger(__name__)


@activity.defn
async def refresh_job_catalog_activity(params: dict) -> dict:
    from app.services.job_catalog import refresh_catalog

    return await refresh_catalog()


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
async def list_inbox_tracking_users_activity(params: dict) -> dict:
    from app.services.application_status_service import list_inbox_tracking_users

    return {"user_ids": await list_inbox_tracking_users()}


@activity.defn
async def inbox_status_activity(params: dict) -> dict:
    import asyncio

    from app.services.application_status_service import scan_inbox_for_member

    outcome = await asyncio.to_thread(scan_inbox_for_member, params["user_id"])
    if outcome["status"] == "failed":
        # Let Temporal retry the member's scan; other members are unaffected.
        raise RuntimeError("Inbox scan failed")
    changes = (outcome["result"] or {}).get("changes", [])
    if changes:
        await _notify_status_changes(params["user_id"], changes)
    return {"changes": len(changes)}


async def _notify_status_changes(user_id: str, changes: list[dict]) -> None:
    """Tell the member their applications moved. Best effort: the status is
    already saved, so a notification failure must not retry the scan."""
    import logging
    import uuid

    from app.workflows.starters import start_notification

    first = changes[0]
    if len(changes) == 1:
        title = f"{first['company']}: application moved to {first['to_status']}"
        body = first.get("role")
    else:
        title = f"{len(changes)} applications updated from your inbox"
        body = ", ".join(f"{c['company']} ({c['to_status']})" for c in changes[:5])
    try:
        await start_notification(
            uuid.UUID(user_id),
            type="application_update",
            title=title,
            body=body,
            link="/applications",
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "Failed to notify user %s of application updates", user_id, exc_info=True
        )


@activity.defn
async def list_auto_apply_users_activity(params: dict) -> dict:
    from app.services.auto_apply_queue import list_auto_apply_users

    return {"user_ids": await list_auto_apply_users()}


@activity.defn
async def auto_apply_queue_activity(params: dict) -> dict:
    from app.services.auto_apply_queue import queue_for_member

    return await queue_for_member(params["user_id"])


@activity.defn
async def list_summary_users_activity(params: dict) -> dict:
    from app.services.daily_summary import list_summary_users

    return {"user_ids": await list_summary_users()}


@activity.defn
async def daily_summary_activity(params: dict) -> dict:
    from app.services.daily_summary import send_summary

    return {"sent": int(await send_summary(params["user_id"]))}


@activity.defn
async def list_outreach_users_activity(params: dict) -> dict:
    from app.services.outreach_service import list_outreach_users

    return {"user_ids": await list_outreach_users()}


@activity.defn
async def outreach_activity(params: dict) -> dict:
    """One member's turn: note replies and bounces, queue due follow-ups,
    then send what is approved, within their daily cap."""
    from app.services import email_answers, outreach_service

    user_id = params["user_id"]
    outcome = await outreach_service.record_replies(user_id)
    outcome.update(await email_answers.collect_answers(user_id))
    followups = await outreach_service.queue_due_followups(user_id)
    outcome.update(await outreach_service.send_approved(user_id))
    outcome["followups_queued"] = followups
    return {k: v for k, v in outcome.items() if isinstance(v, (int, bool))}


@activity.defn
async def list_daily_search_users_activity(params: dict) -> dict:
    from app.services.scheduled_jobs import list_daily_search_users

    return {"user_ids": await list_daily_search_users()}


@activity.defn
async def daily_search_activity(params: dict) -> dict:
    from app.services.scheduled_jobs import StatusCheckTrigger, daily_search

    result = await daily_search(StatusCheckTrigger(user_id=params.get("user_id", "all")))
    return {k: v for k, v in result.items() if isinstance(v, (int, str))}


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
    and reconcile application attempts."""
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
        # Paged by start time: runs whose workflow is still legitimately
        # running (an application waiting a day for its member) would
        # otherwise fill a single page and starve every newer stale run.
        candidates = []
        after = None
        for _ in range(10):
            stale = or_(
                and_(
                    AgentRun.status.in_(("queued", "running")),
                    AgentRun.started_at < now - _STALE_AFTER,
                ),
                and_(
                    AgentRun.status == "awaiting_approval",
                    AgentRun.started_at < approval_cutoff,
                ),
            )
            query = select(AgentRun).where(stale).order_by(AgentRun.started_at).limit(100)
            if after is not None:
                query = query.where(AgentRun.started_at > after)
            runs = (await db.execute(query)).scalars().all()
            candidates += [(run.id, _workflow_id_for(run)) for run in runs]
            if len(runs) < 100:
                break
            after = runs[-1].started_at

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
                                (
                                    "pending",
                                    "claimed",
                                    "filling",
                                    "needs_input",
                                    "review",
                                )
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

    try:
        async with AsyncSessionLocal() as db:
            from app.services.account_deletion_service import (
                reap_expired_account_deletions,
            )

            deleted = await reap_expired_account_deletions(db)
            await db.commit()
            if deleted:
                logger.info("Reaped %d expired account deletion(s)", deleted)
    except Exception:
        logger.exception("Account deletion reaper failed")

    try:
        from app.services.document_cleanup import sweep_document_cleanup

        await sweep_document_cleanup()
    except Exception:
        logger.exception("Document cleanup sweep failed; retained items will retry")

    return {"reconciled": reconciled}
