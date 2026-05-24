import asyncio
import base64
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from langchain_core.messages import HumanMessage
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.resume_agent import resume_agent_node
from app.agents.state import AgentState
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, User

router = APIRouter(prefix="/resume", tags=["resume"])
logger = logging.getLogger(__name__)


class OptimizeRequest(BaseModel):
    jd_text: str


class OptimizeResponse(BaseModel):
    run_id: str
    status: str
    resume_text: str | None = None
    pdf_available: bool = False


@router.post("/optimize", response_model=OptimizeResponse)
async def optimize_resume(
    payload: OptimizeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.jd_text.strip():
        raise HTTPException(status_code=400, detail="jd_text cannot be empty")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="resume",
        status="running",
        input={"jd_text": payload.jd_text[:500]},
    )
    db.add(agent_run)
    await db.flush()

    state = AgentState(
        user_id=str(current_user.id),
        run_id=run_id,
        task_type="resume_optimize",
        messages=[HumanMessage(content=payload.jd_text)],
        context={"jd_text": payload.jd_text},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    result_state = await asyncio.get_event_loop().run_in_executor(
        None, resume_agent_node, state
    )

    agent_run.status = result_state["status"]
    agent_run.completed_at = datetime.now(UTC)
    if result_state.get("pending_action"):
        agent_run.output = {
            "type": result_state["pending_action"].get("type"),
            "pdf_b64": result_state["pending_action"].get("pdf_b64"),
        }

    if result_state["status"] == "failed":
        raise HTTPException(
            status_code=500, detail=result_state.get("error", "Agent failed")
        )

    pending = result_state.get("pending_action") or {}
    return OptimizeResponse(
        run_id=run_id,
        status=result_state["status"],
        resume_text=pending.get("resume_text"),
        pdf_available=bool(pending.get("pdf_b64")),
    )


@router.get("/download/{run_id}")
async def download_pdf(
    run_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == uuid.UUID(run_id),
            AgentRun.user_id == current_user.id,
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
    if not run.output or "pdf_b64" not in run.output:
        raise HTTPException(status_code=404, detail="PDF not available for this run")

    pdf_bytes = base64.b64decode(run.output["pdf_b64"])
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=resume_{run_id[:8]}.pdf"
        },
    )
