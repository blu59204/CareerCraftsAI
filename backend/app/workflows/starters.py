"""Start and signal workflows from the API (and from activities that fan out).

Every workflow id is derived from the thing it works on (run, application),
so a retried request finds the workflow that is already running instead of
starting a duplicate.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime, timedelta

from temporalio.client import WorkflowHandle
from temporalio.common import WorkflowIDReusePolicy
from temporalio.exceptions import WorkflowAlreadyStartedError

from app.core.config import settings
from app.core.temporal_client import get_temporal_client

logger = logging.getLogger(__name__)


class WorkflowUnavailable(RuntimeError):
    """Temporal could not be reached; the caller should answer 503."""


async def _client():
    try:
        return await get_temporal_client()
    except Exception as exc:
        logger.error("Temporal unavailable: %s", exc)
        raise WorkflowUnavailable("Workflow engine unavailable") from exc


async def start_agent_run(
    run_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    initial_continuation: dict | None = None,
) -> str:
    from app.workflows.agent_run import AgentRunInput, AgentRunWorkflow, agent_run_workflow_id

    workflow_id = agent_run_workflow_id(str(run_id))
    client = await _client()
    try:
        await client.start_workflow(
            AgentRunWorkflow.run,
            AgentRunInput(
                run_id=str(run_id),
                user_id=str(user_id),
                activity_timeout_s=settings.WORKFLOW_TASK_TIMEOUT_S + 30,
                approval_timeout_s=settings.AGENT_APPROVAL_TIMEOUT_S,
                initial_continuation=initial_continuation,
            ),
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
    except WorkflowAlreadyStartedError:
        pass
    return workflow_id


async def signal_agent_decision(
    run_id: uuid.UUID | str,
    user_id: uuid.UUID | str,
    approved: bool,
    action_type: str = "",
    continuation: dict | None = None,
) -> None:
    """Deliver an approve/cancel decision to the run's workflow.

    Signal-with-start: if the run's workflow is running it just receives the
    signal; if the run was produced outside a workflow (inline API routes,
    follow-up drafts) one is started at the checkpoint with the decision
    already delivered — atomically, so there is no window to lose it."""
    from app.workflows.agent_run import (
        AgentRunInput,
        AgentRunWorkflow,
        ApprovalDecision,
        agent_run_workflow_id,
    )

    client = await _client()
    await client.start_workflow(
        AgentRunWorkflow.run,
        AgentRunInput(
            run_id=str(run_id),
            user_id=str(user_id),
            activity_timeout_s=settings.WORKFLOW_TASK_TIMEOUT_S + 30,
            approval_timeout_s=settings.AGENT_APPROVAL_TIMEOUT_S,
            start_at_checkpoint=True,
        ),
        id=agent_run_workflow_id(str(run_id)),
        task_queue=settings.TEMPORAL_TASK_QUEUE,
        id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        start_signal="decide",
        start_signal_args=[
            ApprovalDecision(approved=approved, action_type=action_type, continuation=continuation)
        ],
    )


async def start_job_search(run_id: uuid.UUID | str, user_id: uuid.UUID | str, params: dict) -> str:
    from app.workflows.job_search import JobSearchInput, JobSearchWorkflow, job_search_workflow_id

    workflow_id = job_search_workflow_id(str(run_id))
    client = await _client()
    try:
        await client.start_workflow(
            JobSearchWorkflow.run,
            JobSearchInput(run_id=str(run_id), user_id=str(user_id), params=params),
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
        )
    except WorkflowAlreadyStartedError:
        pass
    return workflow_id


async def start_auto_apply(user_id: uuid.UUID, application_id: uuid.UUID) -> dict:
    """Start (or find) the application workflow. Returns workflow_id and
    whether this call started it ("queued") or it was already running."""
    from app.workflows.auto_apply import AutoApplyIntent, AutoApplyWorkflow, auto_apply_workflow_id

    workflow_id = auto_apply_workflow_id(str(user_id), str(application_id))
    run_id = str(uuid.uuid4())
    extension = settings.APPLY_EXECUTION_MODE == "extension"
    client = await _client()
    try:
        await client.start_workflow(
            AutoApplyWorkflow.run,
            AutoApplyIntent(
                user_id=str(user_id),
                job_application_id=str(application_id),
                mode=settings.APPLY_EXECUTION_MODE,
                claim_timeout_s=settings.EXTENSION_TASK_CLAIM_TIMEOUT_S,
                complete_timeout_s=settings.EXTENSION_TASK_COMPLETE_TIMEOUT_S,
                run_id=run_id,
            ),
            id=workflow_id,
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            # The extension flow waits on a person and bounds itself with
            # its own timers; only the server-browser flow needs a hard cap.
            execution_timeout=(
                None
                if extension
                else timedelta(seconds=settings.TEMPORAL_WORKFLOW_EXECUTION_TIMEOUT_S)
            ),
            # A finished attempt (failed, cancelled, expired) may be retried;
            # a running one is reused.
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE,
        )
        status = "queued"
    except WorkflowAlreadyStartedError:
        status = "already_running"
        run_id = None  # the running workflow has its own
    return {
        "workflow_id": workflow_id,
        "run_id": run_id,
        "status": status,
        "mode": settings.APPLY_EXECUTION_MODE,
    }


async def auto_apply_handle(workflow_id: str) -> WorkflowHandle:
    from app.workflows.auto_apply import AutoApplyWorkflow

    client = await _client()
    return client.get_workflow_handle_for(AutoApplyWorkflow.run, workflow_id=workflow_id)


async def signal_extension_update(workflow_id: str, update: dict) -> None:
    from app.workflows.auto_apply import AutoApplyWorkflow

    handle = await auto_apply_handle(workflow_id)
    await handle.signal(AutoApplyWorkflow.extension_update, update)


async def start_followups(
    user_id: uuid.UUID | str,
    application_id: uuid.UUID | str,
    applied_at: datetime | None,
) -> bool:
    """Schedule the day-5 and day-12 follow-up drafts for an application.
    Returns False when they were already scheduled."""
    from app.workflows.followup import FollowupInput, FollowupWorkflow, followup_workflow_id

    applied_at = applied_at or datetime.now(UTC)
    if applied_at.tzinfo is None:
        applied_at = applied_at.replace(tzinfo=UTC)
    client = await _client()
    try:
        await client.start_workflow(
            FollowupWorkflow.run,
            FollowupInput(
                user_id=str(user_id),
                application_id=str(application_id),
                applied_at=applied_at.isoformat(),
            ),
            id=followup_workflow_id(str(application_id)),
            task_queue=settings.TEMPORAL_TASK_QUEUE,
            id_reuse_policy=WorkflowIDReusePolicy.ALLOW_DUPLICATE_FAILED_ONLY,
        )
        return True
    except WorkflowAlreadyStartedError:
        return False
