"""
Internal endpoints called by BullMQ worker only.
Not exposed via Nginx (blocked at nginx level).
Protected by shared APP_SECRET_KEY header — not Supabase JWT.
"""
import asyncio
import hmac
import logging
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Header, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)


def _verify_secret(x_internal_secret: str = Header(...)) -> None:
    if not hmac.compare_digest(x_internal_secret, settings.APP_SECRET_KEY):
        raise HTTPException(status_code=403, detail="Forbidden")


class JobSearchTrigger(BaseModel):
    user_id: str
    run_id: str
    search_query: str
    location: str
    max_results: int


@router.post("/agents/run-job-search")
async def run_job_search(
    payload: JobSearchTrigger,
    x_internal_secret: str = Header(...),
):
    _verify_secret(x_internal_secret)

    from sqlalchemy import select

    from app.agents.job_search import job_search_agent_node
    from app.agents.state import AgentState
    from app.core.database import AsyncSessionLocal
    from app.models.db import AgentRun

    state = AgentState(
        user_id=payload.user_id,
        run_id=payload.run_id,
        task_type="job_search",
        messages=[HumanMessage(content=payload.search_query)],
        context={
            "search_query": payload.search_query,
            "location": payload.location,
            "max_results": payload.max_results,
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    result_state = await asyncio.get_running_loop().run_in_executor(
        None, job_search_agent_node, state
    )

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(AgentRun).where(AgentRun.id == uuid.UUID(payload.run_id))
        )
        run = res.scalar_one_or_none()
        if run:
            run.status = result_state["status"]
            run.output = result_state.get("result")
            run.completed_at = datetime.now(UTC)
        await db.commit()

    logger.info(
        "Job search run %s finished with status %s",
        payload.run_id,
        result_state["status"],
    )
    return {"status": result_state["status"], "run_id": payload.run_id}


class FollowupTrigger(BaseModel):
    user_id: str
    application_id: str
    day: int


@router.post("/agents/run-followup")
async def run_followup(
    payload: FollowupTrigger,
    x_internal_secret: str = Header(...),
):
    _verify_secret(x_internal_secret)

    from app.agents.followup_agent import schedule_followups
    from app.core.database import AsyncSessionLocal
    from app.models.db import JobApplication
    from sqlalchemy import select

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(JobApplication).where(
                JobApplication.id == uuid.UUID(payload.application_id)
            )
        )
        application = res.scalar_one_or_none()
        if not application:
            logger.warning("Follow-up: application %s not found", payload.application_id)
            return {"status": "not_found", "application_id": payload.application_id}

    schedule_followups(payload.user_id, payload.application_id, application.applied_at)
    logger.info(
        "Follow-up day-%d triggered for application %s user %s",
        payload.day,
        payload.application_id,
        payload.user_id,
    )
    return {"status": "scheduled", "day": payload.day, "application_id": payload.application_id}
