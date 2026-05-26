import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, User

router = APIRouter(prefix="/linkedin", tags=["linkedin"])


class OutreachIdentifyRequest(BaseModel):
    company_name: str
    role_context: str | None = None


class OutreachApproveRequest(BaseModel):
    approved: bool
    edited_message: str | None = None


@router.post("/outreach/identify")
async def identify_contacts(
    body: OutreachIdentifyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Find contacts at a company via Proxycurl, filter, and draft messages."""
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="linkedin_outreach",
        status="running",
        input={"company_name": body.company_name, "role_context": body.role_context},
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    await harness.run(
        user_id=str(current_user.id),
        task_type="linkedin_outreach",
        context={"company_name": body.company_name, "role_context": body.role_context},
        user_settings={},
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "running"}


@router.get("/outreach/queue")
async def get_outreach_queue(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """View pending outreach messages."""
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.user_id == current_user.id,
            AgentRun.agent_type == "linkedin_outreach",
        ).order_by(AgentRun.started_at.desc().nulls_last()).limit(20)
    )
    return result.scalars().all()


@router.post("/outreach/{run_id}/approve")
async def approve_outreach(
    run_id: uuid.UUID,
    body: OutreachApproveRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Approve or reject a pending outreach message. HITL gate enforced."""
    result = await db.execute(
        select(AgentRun).where(
            AgentRun.id == run_id,
            AgentRun.user_id == current_user.id,
            AgentRun.agent_type == "linkedin_outreach",
        )
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=404, detail="Outreach run not found")
    if run.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail="Run is not awaiting approval")

    if body.approved:
        run.status = "completed"
        # In production, this would trigger PinchTab to send the message
    else:
        run.status = "cancelled"

    return {"status": run.status, "run_id": str(run_id)}
