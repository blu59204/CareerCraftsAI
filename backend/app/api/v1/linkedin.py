import asyncio
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import apply_harness_result
from app.models.db import AgentRun, LinkedInOutreachQueue, User

router = APIRouter(prefix="/linkedin", tags=["linkedin"])
logger = logging.getLogger(__name__)

HARNESS_TIMEOUT_SECONDS = 120


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
    try:
        harness_result = await asyncio.wait_for(
            harness.run(
                user_id=str(current_user.id),
                task_type="linkedin_outreach",
                context={"company_name": body.company_name, "role_context": body.role_context},
                user_settings={},
                run_id=run_id,
            ),
            timeout=HARNESS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        agent_run.status = "failed"
        agent_run.output = {"error": f"Timed out after {HARNESS_TIMEOUT_SECONDS}s"}
        await db.flush()
        raise HTTPException(status_code=504, detail="LinkedIn outreach identification timed out") from None
    apply_harness_result(agent_run, harness_result)
    await db.flush()
    return {"run_id": run_id, "status": agent_run.status}


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
        from app.core.model_router import _build_llm
        from app.core.sync_db import fetch_model_settings
        from app.services.browser_control_service import linkedin_send_connection

        output = run.output or {}
        messages = output.get("messages") or []
        if not messages:
            raise HTTPException(status_code=422, detail="No outreach messages pending")

        model_settings = fetch_model_settings(str(current_user.id))
        if not model_settings:
            raise HTTPException(status_code=400, detail="No active model settings configured")
        llm = _build_llm(model_settings)

        sent: list[dict] = []
        for item in messages:
            if not isinstance(item, dict):
                continue
            profile_url = item.get("profile_url")
            message = body.edited_message or item.get("message")
            if not profile_url or not message:
                raise HTTPException(status_code=422, detail="Outreach message missing profile_url or message")
            try:
                await linkedin_send_connection(
                    llm=llm,
                    user_id=str(current_user.id),
                    profile_url=profile_url,
                    note=message,
                    run_id=str(run_id),
                )
            except Exception as exc:
                logger.warning("LinkedIn outreach send failed for run %s: %s", run_id, exc)
                raise HTTPException(status_code=502, detail="LinkedIn send failed") from exc

            queue_id = item.get("queue_id")
            if queue_id:
                qres = await db.execute(
                    select(LinkedInOutreachQueue).where(
                        LinkedInOutreachQueue.id == uuid.UUID(queue_id),
                        LinkedInOutreachQueue.user_id == current_user.id,
                    )
                )
                queue_item = qres.scalar_one_or_none()
                if queue_item:
                    queue_item.status = "sent"
                    queue_item.approved_at = datetime.now(timezone.utc)
                    queue_item.sent_at = datetime.now(timezone.utc)
                    if body.edited_message:
                        queue_item.message = body.edited_message
            sent.append({"profile_url": profile_url, "contact_name": item.get("contact_name")})

        run.status = "completed"
        run.output = {**output, "sent": sent}
    else:
        output = run.output or {}
        for queue_id in output.get("queue_ids") or []:
            qres = await db.execute(
                select(LinkedInOutreachQueue).where(
                    LinkedInOutreachQueue.id == uuid.UUID(queue_id),
                    LinkedInOutreachQueue.user_id == current_user.id,
                )
            )
            queue_item = qres.scalar_one_or_none()
            if queue_item:
                queue_item.status = "rejected"
        run.status = "failed"
        run.output = {**output, "error": "Outreach rejected by user"}

    run.completed_at = datetime.now(timezone.utc)
    await db.flush()
    return {"status": run.status, "run_id": str(run_id)}
