import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.rate_limit import limiter
from app.models.db import AgentRun, JobApplication, User
from app.services.queue_service import enqueue_job_search

router = APIRouter(prefix="/jobs", tags=["jobs"])
logger = logging.getLogger(__name__)

VALID_STATUSES = {"saved", "applied", "viewed", "interview", "offer", "rejected"}


class JobSearchRequest(BaseModel):
    search_query: str = Field(max_length=200)
    location: str = "Remote"
    max_results: int = 10


class JobSearchResponse(BaseModel):
    queue_job_id: str
    status: str = "queued"


class ApplicationResponse(BaseModel):
    id: uuid.UUID
    company: str
    role: str
    job_url: str | None
    match_score: int | None
    status: str
    applied_at: datetime | None

    model_config = {"from_attributes": True}


class StatusUpdateBody(BaseModel):
    status: str


class NLSearchRequest(BaseModel):
    query: str = Field(min_length=5, max_length=500)


@router.post("/search/natural")
@limiter.limit("10/minute")
async def natural_language_search(
    request: Request,
    payload: NLSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Accept a natural language job query, extract parameters, return interpretation + results."""
    from app.agents.harness import get_harness

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="nl_job_search",
        status="running",
        input={"query": payload.query},
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    await harness.run(
        user_id=str(current_user.id),
        task_type="nl_job_search",
        context={"query": payload.query},
        user_settings={},
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "running"}


@router.post("/search", response_model=JobSearchResponse)
@limiter.limit("10/minute")
async def search_jobs(
    request: Request,
    payload: JobSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not payload.search_query.strip():
        raise HTTPException(status_code=400, detail="search_query cannot be empty")
    if payload.max_results > 25:
        raise HTTPException(status_code=400, detail="max_results cannot exceed 25")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="job_search",
        status="running",
        input={
            "search_query": payload.search_query,
            "location": payload.location,
            "max_results": payload.max_results,
        },
    )
    db.add(agent_run)
    await db.flush()

    try:
        queue_job_id = await enqueue_job_search(
            user_id=str(current_user.id),
            run_id=run_id,
            search_query=payload.search_query,
            location=payload.location,
            max_results=payload.max_results,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return JobSearchResponse(queue_job_id=queue_job_id)

@router.get("/applications", response_model=list[ApplicationResponse])
async def list_applications(
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if status and status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be one of: {VALID_STATUSES}"
        )

    query = select(JobApplication).where(JobApplication.user_id == current_user.id)
    if status:
        query = query.where(JobApplication.status == status)
    result = await db.execute(
        query.order_by(JobApplication.applied_at.desc().nulls_last())
    )
    return result.scalars().all()


@router.patch("/applications/{application_id}/status", response_model=ApplicationResponse)
async def update_application_status(
    application_id: uuid.UUID,
    body: StatusUpdateBody,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.status not in VALID_STATUSES:
        raise HTTPException(
            status_code=400, detail=f"status must be one of: {VALID_STATUSES}"
        )

    result = await db.execute(
        select(JobApplication).where(
            JobApplication.id == application_id,
            JobApplication.user_id == current_user.id,
        )
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")

    app.status = body.status
    if body.status == "applied" and not app.applied_at:
        app.applied_at = datetime.now(timezone.utc)
    return app
