from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import settings
from app.core.event_bus import stream_events, publish
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User
from temporalio.service import RPCError, RPCStatusCode

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

SSE_TIMEOUT_SECONDS = 300

VALID_TASKS = {
    "resume_optimize",
    "job_search",
    "linkedin_optimize",
    "linkedin_outreach",
    "email",
    "cover_letter",
    "interview_coach",
    "evaluate_answer",
    "interview_prep",
    "company_research",
    "salary_intelligence",
    "nl_job_search",
    "email_monitor",
    "auto_apply",
}


class RunRequest(BaseModel):
    task_type: str
    context: dict = Field(default_factory=dict)

    @field_validator("context")
    @classmethod
    def reject_secrets(cls, value: dict) -> dict:
        from app.services.workflow_service import validate_context

        validate_context(value)
        return value


class ApproveRequest(BaseModel):
    approved: bool
    action_type: str | None = None
    edits: dict[str, Any] | None = None


# ── Endpoints ───────────────────────────────────────────────────


@router.post("/run", response_model=dict)
@limiter.limit("10/minute")
async def run_agent(
    request: Request,
    payload: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.task_type not in VALID_TASKS:
        raise HTTPException(status_code=400, detail=f"Invalid task_type: {payload.task_type}")

    # Serialize admission for this user across all API replicas.
    await db.execute(select(User.id).where(User.id == current_user.id).with_for_update())
    # Concurrent run check. Applications waiting in the user's own browser
    # (extension mode) use no server capacity and can wait for hours, so
    # they never block other agents.
    active_runs = await db.execute(
        select(AgentRun.id).where(
            AgentRun.user_id == current_user.id,
            AgentRun.status.in_(["queued", "running"]),
            AgentRun.agent_type != "apply_prepare",
        )
    )
    active_run_ids = [str(run_id) for run_id in active_runs.scalars().all()]
    count = len(active_run_ids)
    max_concurrent = getattr(settings, "AGENT_MAX_CONCURRENT_PER_USER", 2)
    if count >= max_concurrent:
        raise HTTPException(
            status_code=429,
            detail={
                "message": f"Max {max_concurrent} concurrent agent runs reached. Wait for current runs to complete.",
                "run_ids": active_run_ids,
            },
        )

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type=payload.task_type,
        status="queued",
        input={"task_type": payload.task_type, "context": payload.context},
    )
    db.add(agent_run)
    # Committed before the workflow starts: its first activity reads the row.
    await db.commit()

    from app.workflows.starters import WorkflowUnavailable, start_agent_run

    try:
        await start_agent_run(run_id, current_user.id)
    except WorkflowUnavailable as exc:
        agent_run.status = "failed"
        agent_run.output = {"error": "Agent service unavailable — try again shortly"}
        agent_run.completed_at = datetime.now(UTC)
        await db.commit()
        raise HTTPException(status_code=503, detail="Agent service unavailable") from exc

    stream_url = str(request.base_url).rstrip("/") + f"/api/v1/agents/{run_id}/stream"
    return {"run_id": run_id, "status": "queued", "stream_url": stream_url}


async def _redis_to_sse(run_id: str) -> StreamingResponse:
    async def _gen():
        started = time.time()
        async for event in stream_events(run_id, timeout_s=SSE_TIMEOUT_SECONDS):
            yield event
            if (time.time() - started) > SSE_TIMEOUT_SECONDS:
                return

    return StreamingResponse(
        _gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/{run_id}/stream")
async def stream_agent(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")

    res = await db.execute(
        select(AgentRun).where(
            AgentRun.id == run_uuid,
            AgentRun.user_id == current_user.id,
        )
    )
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    return await _redis_to_sse(run_id)


@router.post("/{run_id}/approve", response_model=dict)
@limiter.limit("10/minute")
async def approve_or_cancel(
    run_id: str,
    payload: ApproveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")

    res = await db.execute(
        select(AgentRun)
        .where(
            AgentRun.id == run_uuid,
            AgentRun.user_id == current_user.id,
        )
        .with_for_update()
    )
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail=f"Run is {run.status}, not awaiting_approval")

    # Application runs carry their AutoApplyWorkflow id; every other run is
    # driven by AgentRunWorkflow "agent-run/{run_id}".
    apply_workflow_id = (run.input or {}).get("workflow_id")
    from app.workflows.starters import WorkflowUnavailable, signal_agent_decision

    if not payload.approved:
        try:
            if apply_workflow_id:
                from app.workflows.auto_apply import AutoApplyWorkflow
                from app.workflows.starters import auto_apply_handle

                handle = await auto_apply_handle(apply_workflow_id)
                await handle.signal(AutoApplyWorkflow.cancel)
            else:
                await _signal_if_running(run_id, current_user.id)
        except WorkflowUnavailable as exc:
            raise HTTPException(status_code=503, detail="Agent service unavailable") from exc
        run.status = "failed"
        run.output = {"error": "Action cancelled by user"}
        run.completed_at = datetime.now(UTC)
        await db.commit()
        publish(run_id, "error", {"error": "Action cancelled by user"})
        return {"status": "cancelled"}

    pending = run.output or {}
    redis_action_type = pending.get("type") or pending.get("action_type")
    if payload.action_type and redis_action_type and payload.action_type != redis_action_type:
        raise HTTPException(status_code=422, detail="action_type mismatch")

    if not redis_action_type:
        redis_action_type = payload.action_type or ""

    from app.services.workflow_service import validate_approval

    try:
        continuation = validate_approval(pending, payload.edits or {})
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Queued before signalling, so the continuation activity can claim it and
    # a double-click finds the run no longer awaiting approval.
    run.status = "queued"
    run.completed_at = None
    await db.commit()
    try:
        if apply_workflow_id:
            await _signal_temporal_approval(run, redis_action_type, continuation)
        else:
            await signal_agent_decision(
                run_id,
                current_user.id,
                True,
                redis_action_type,
                continuation,
            )
    except (WorkflowUnavailable, RPCError) as exc:
        logger.error("Approval signal failed for run %s: %s", run_id, exc)
        run.status = "awaiting_approval"
        await db.commit()
        raise HTTPException(
            status_code=503, detail="Agent service unavailable — try again"
        ) from exc
    publish(run_id, "approved", {"action_type": redis_action_type})
    return {"status": "queued", "action_type": redis_action_type}


async def _signal_if_running(run_id: str, user_id) -> None:
    """Cancel a run's workflow if it has one; inline-route runs do not."""
    from app.workflows.agent_run import AgentRunWorkflow, ApprovalDecision, agent_run_workflow_id
    from app.workflows.starters import _client

    client = await _client()
    handle = client.get_workflow_handle_for(
        AgentRunWorkflow.run,
        workflow_id=agent_run_workflow_id(run_id),
    )
    try:
        await handle.signal(AgentRunWorkflow.decide, ApprovalDecision(approved=False))
    except RPCError as exc:
        if exc.status != RPCStatusCode.NOT_FOUND:
            raise


async def _signal_temporal_approval(run: AgentRun, action_type: str, continuation: dict) -> None:
    from app.workflows.auto_apply import AutoApplyWorkflow
    from app.workflows.starters import auto_apply_handle

    workflow_id = (run.input or {}).get("workflow_id")
    if not workflow_id:
        raise HTTPException(
            status_code=500, detail="Temporal-backed run is missing its workflow_id"
        )

    handle = await auto_apply_handle(workflow_id)
    if action_type == "application_answers_required":
        await handle.signal(AutoApplyWorkflow.provide_answers, continuation.get("answers") or {})
    else:
        # browser_review (final submit) and browser_input (resume
        # preparation) share one generic approval signal — see
        # auto_apply.py's workflow loop for why.
        await handle.signal(AutoApplyWorkflow.approve)


@router.get("/runs")
async def list_runs(
    status: str | None = None,
    application_id: str | None = None,
    limit: int = 20,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(AgentRun).where(AgentRun.user_id == current_user.id)
    if status:
        q = q.where(AgentRun.status == status)
    if application_id:
        try:
            uuid.UUID(application_id)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid application_id")
        # Runs are linked to an application through their stored input context.
        # Agents disagree on the key name, so match both spellings; without this
        # the caller silently gets every run the user has ever made.
        q = q.where(
            or_(
                AgentRun.input["application_id"].astext == application_id,
                AgentRun.input["job_application_id"].astext == application_id,
            )
        )
    q = q.order_by(AgentRun.started_at.desc()).offset(offset).limit(min(limit, 100))
    result = await db.execute(q)
    runs = result.scalars().all()
    return {
        "runs": [
            {
                "id": str(r.id),
                "agent_type": r.agent_type,
                "status": r.status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "completed_at": r.completed_at.isoformat() if r.completed_at else None,
                "tokens_used": r.tokens_used,
                "output": r.output,
                "duration_ms": r.duration_ms,
            }
            for r in runs
        ]
    }


@router.get("/runs/{run_id}")
async def get_run_detail(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run_id")
    res = await db.execute(
        select(AgentRun).where(AgentRun.id == run_uuid, AgentRun.user_id == current_user.id)
    )
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    return {
        "id": str(run.id),
        "status": run.status,
        "agent_type": run.agent_type,
        "input": run.input,
        "output": run.output,
        "tokens_used": run.tokens_used,
        "duration_ms": run.duration_ms,
        "error": (run.output or {}).get("error"),
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
