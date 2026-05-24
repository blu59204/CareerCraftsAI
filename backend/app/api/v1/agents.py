import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.core.database import AsyncSessionLocal
from app.core.event_bus import emit, get_queue, stream_events
from app.core.rate_limit import limiter
from app.models.db import AgentRun, User

router = APIRouter(prefix="/agents", tags=["agents"])
logger = logging.getLogger(__name__)

VALID_TASKS = {"resume_optimize", "job_search", "linkedin_optimize", "email"}


class RunRequest(BaseModel):
    task_type: str
    context: dict = {}


class RunResponse(BaseModel):
    run_id: str
    status: str


class ApproveRequest(BaseModel):
    approved: bool


class AgentRunResponse(BaseModel):
    id: uuid.UUID
    agent_type: str
    status: str
    input: dict | None
    output: dict | None
    duration_ms: int | None
    created_at: datetime
    completed_at: datetime | None

    model_config = {"from_attributes": True}


@router.get("/runs", response_model=list[AgentRunResponse])
@limiter.limit("30/minute")
async def list_runs(
    request: Request,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent agent runs for the current user."""
    result = await db.execute(
        select(AgentRun)
        .where(AgentRun.user_id == current_user.id)
        .order_by(AgentRun.created_at.desc())
        .limit(min(limit, 50))
    )
    return result.scalars().all()


@router.post("/run", response_model=RunResponse)
@limiter.limit("10/minute")
async def start_agent_run(
    request: Request,
    payload: RunRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.task_type not in VALID_TASKS:
        raise HTTPException(
            status_code=400,
            detail=f"task_type must be one of: {VALID_TASKS}",
        )

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type=payload.task_type,
        status="running",
        input={
            "task_type": payload.task_type,
            "context_keys": list(payload.context.keys()),
        },
    )
    db.add(agent_run)
    await db.flush()
    get_queue(run_id)

    async def _run() -> None:
        try:
            harness = await get_harness()
            harness_result = await harness.run(
                user_id=str(current_user.id),
                task_type=payload.task_type,
                context=payload.context,
                user_settings={},   # user model settings resolved inside agents
                run_id=run_id,
            )
            final_status = harness_result.get("status", "failed")
            final_output = harness_result.get("result") or harness_result.get("pending_action")

            # Forward SSE events based on harness outcome
            if final_status == "awaiting_approval":
                emit(run_id, "checkpoint", final_output or {})
            elif final_status == "failed":
                emit(run_id, "error", harness_result.get("error") or "Unknown error")
            elif final_status == "completed":
                emit(run_id, "complete", final_output or {})

            async with AsyncSessionLocal() as fresh_db:
                res = await fresh_db.execute(
                    select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
                )
                run = res.scalar_one_or_none()
                if run:
                    run.status = final_status
                    run.output = final_output
                    run.duration_ms = harness_result.get("duration_ms")
                    run.completed_at = datetime.now(UTC)
                await fresh_db.commit()
        except Exception as exc:
            logger.error("Agent run %s background task failed: %s", run_id, exc)
            emit(run_id, "error", str(exc))

    asyncio.create_task(_run())
    return RunResponse(run_id=run_id, status="running")


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        )
    )
    if not res.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Run not found")
    return StreamingResponse(
        stream_events(run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/{run_id}/approve", response_model=dict)
async def approve_or_cancel(
    run_id: str,
    payload: ApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    res = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        )
    )
    run = res.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(
            status_code=400,
            detail=f"Run is {run.status}, not awaiting_approval",
        )

    if not payload.approved:
        run.status = "failed"
        run.completed_at = datetime.now(UTC)
        emit(run_id, "complete", {"cancelled": True})
        return {"status": "cancelled"}

    pending = run.output or {}
    action_type = pending.get("type", "")
    if action_type == "send_email":
        from app.services.gmail_service import GmailMCPClient

        gmail = GmailMCPClient(str(current_user.id))
        gmail.send_message(pending["recipient"], pending["subject"], pending["body"])

    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    emit(run_id, "complete", {"approved": True, "action": action_type})
    await db.flush()
    return {"status": "completed", "action": action_type}
