import asyncio
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.orchestrator import orchestrator
from app.agents.state import AgentState
from app.api.v1.deps import get_current_user, get_db
from app.core.database import AsyncSessionLocal
from app.core.event_bus import emit, get_queue, stream_events
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


@router.post("/run", response_model=RunResponse)
async def start_agent_run(
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

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type=payload.task_type,
        messages=[HumanMessage(content=str(payload.context))],
        context=payload.context,
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    async def _run() -> None:
        try:
            loop = asyncio.get_event_loop()
            result_state = await loop.run_in_executor(None, orchestrator.invoke, state)
            async with AsyncSessionLocal() as fresh_db:
                res = await fresh_db.execute(
                    select(AgentRun).where(AgentRun.id == uuid.UUID(run_id))
                )
                run = res.scalar_one_or_none()
                if run:
                    run.status = result_state["status"]
                    run.output = result_state.get("result") or result_state.get("pending_action")
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
    return {"status": "completed", "action": action_type}
