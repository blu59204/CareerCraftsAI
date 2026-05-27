"""
Internal endpoints called by BullMQ worker only.
Not exposed via Nginx (blocked at nginx level).
Protected by shared APP_SECRET_KEY header — not Supabase JWT.
"""
import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
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


@router.post("/agents/run-job-search", dependencies=[Depends(_verify_secret)])
async def run_job_search(
    payload: JobSearchTrigger,
):

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
            run.completed_at = datetime.now(timezone.utc)

        # Persist matched jobs as saved JobApplications
        if result_state["status"] == "completed":
            matches = (result_state.get("result") or {}).get("matches", [])
            from app.models.db import JobApplication
            for job in matches:
                app = JobApplication(
                    user_id=uuid.UUID(payload.user_id),
                    company=job.get("company", "Unknown"),
                    role=job.get("title", "Unknown"),
                    job_url=job.get("job_url"),
                    jd_text=job.get("description"),
                    match_score=job.get("match_score"),
                    status="saved",
                )
                db.add(app)

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


@router.post("/agents/run-followup", dependencies=[Depends(_verify_secret)])
async def run_followup(
    payload: FollowupTrigger,
):

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

    await schedule_followups(payload.user_id, payload.application_id, application.applied_at)
    logger.info(
        "Follow-up day-%d triggered for application %s user %s",
        payload.day,
        payload.application_id,
        payload.user_id,
    )
    return {"status": "scheduled", "day": payload.day, "application_id": payload.application_id}



class StatusCheckTrigger(BaseModel):
    user_id: str


@router.post("/agents/daily-search", dependencies=[Depends(_verify_secret)])
async def daily_search(payload: StatusCheckTrigger):
    """Daily automated job search based on user preferences.

    Fetches user preferences from memory, searches all platforms + Google Jobs,
    scores matches, and saves top results as applications.
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.core.model_router import get_llm
    from app.models.db import JobApplication, User as UserModel
    from app.agents.memory.manager import MemoryManager
    from app.services.job_platforms_service import scrape_all_platforms
    from app.services.indian_platforms_service import search_google_jobs

    jobs_found = 0
    applications_queued = 0

    async with AsyncSessionLocal() as db:
        # Get users to search for
        if payload.user_id == "all":
            res = await db.execute(select(UserModel))
            users = res.scalars().all()
        else:
            res = await db.execute(
                select(UserModel).where(UserModel.supabase_uid == payload.user_id)
            )
            users = res.scalars().all()

        for user in users:
            try:
                user_id = user.supabase_uid
                llm = await get_llm(user_id, db)

                # Get user preferences from memory
                mgr = MemoryManager(
                    db_url=settings.DATABASE_URL, redis_url=settings.REDIS_URL
                )
                await mgr.initialize()
                user_ctx = await mgr.get_user_context(user_id)
                await mgr.close()

                search_term = user_ctx.get("target_roles", "software engineer")
                location = user_ctx.get("preferred_locations", "Bangalore")

                # Search all platforms
                all_jobs = await scrape_all_platforms(
                    search_term=search_term,
                    location=location,
                    results_wanted=15,
                    include_indian=True,
                    llm=llm,
                    user_id=user_id,
                )

                # Also search Google Jobs for company-only postings
                google_jobs = await search_google_jobs(
                    llm=llm, user_id=user_id,
                    search_term=search_term, location=location,
                    results_wanted=10,
                )
                all_jobs.extend(google_jobs)
                jobs_found += len(all_jobs)

                # Save top results as applications
                for job in all_jobs[:10]:
                    existing = await db.execute(
                        select(JobApplication).where(
                            JobApplication.user_id == uuid.UUID(user_id),
                            JobApplication.job_url == job.job_url,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue  # Skip duplicates

                    app = JobApplication(
                        user_id=uuid.UUID(user_id),
                        company=job.company,
                        role=job.title,
                        job_url=job.job_url,
                        jd_text=job.description,
                        status="saved",
                    )
                    db.add(app)
                    applications_queued += 1

                await db.commit()
            except Exception as exc:
                logger.warning("Daily search failed for user %s: %s", user.supabase_uid, exc)

    logger.info("Daily search complete: %d jobs found, %d queued", jobs_found, applications_queued)
    return {"status": "ok", "jobs_found": jobs_found, "applications_queued": applications_queued}


@router.post("/applications/check-status", dependencies=[Depends(_verify_secret)])
async def check_application_status(payload: StatusCheckTrigger):
    """Check application status on hiring platforms via browser-use.

    Called by BullMQ status-check scheduler every 6 hours.
    Logs into platforms, checks notifications/status pages, updates DB.
    """
    from sqlalchemy import select, update
    from app.core.database import AsyncSessionLocal
    from app.core.model_router import get_llm
    from app.models.db import JobApplication
    from app.services.browser_control_service import run_browser_task

    updated_count = 0

    async with AsyncSessionLocal() as db:
        # Get all active applications (applied/viewed) for this user
        if payload.user_id == "all":
            res = await db.execute(
                select(JobApplication).where(
                    JobApplication.status.in_(["applied", "viewed", "shortlisted"])
                )
            )
        else:
            res = await db.execute(
                select(JobApplication).where(
                    JobApplication.user_id == uuid.UUID(payload.user_id),
                    JobApplication.status.in_(["applied", "viewed", "shortlisted"]),
                )
            )
        applications = res.scalars().all()

        if not applications:
            return {"status": "ok", "updated_count": 0, "message": "No active applications"}

        # Group by platform for efficient checking
        platform_apps: dict[str, list] = {}
        for app in applications:
            platform = _detect_platform(app.job_url or "")
            platform_apps.setdefault(platform, []).append(app)

        # Check each platform's notification page
        for platform, apps in platform_apps.items():
            try:
                user_id = str(apps[0].user_id)
                llm = await get_llm(user_id, db)

                task = _build_status_check_task(platform, apps)
                result_text = await run_browser_task(llm, task, user_id, max_steps=15)

                # Parse status updates from browser agent response
                updates = _parse_status_updates(result_text, apps)
                for app_id, new_status in updates.items():
                    await db.execute(
                        update(JobApplication)
                        .where(JobApplication.id == app_id)
                        .values(status=new_status)
                    )
                    updated_count += len(updates)
            except Exception as exc:
                logger.warning("Status check failed for platform %s: %s", platform, exc)

        await db.commit()

    logger.info("Status check complete: %d applications updated", updated_count)
    return {"status": "ok", "updated_count": updated_count}


def _detect_platform(job_url: str) -> str:
    """Detect platform from job URL."""
    url_lower = job_url.lower()
    if "linkedin" in url_lower:
        return "linkedin"
    if "naukri" in url_lower:
        return "naukri"
    if "indeed" in url_lower:
        return "indeed"
    if "foundit" in url_lower or "monster" in url_lower:
        return "foundit"
    if "instahyre" in url_lower:
        return "instahyre"
    return "unknown"


def _build_status_check_task(platform: str, apps: list) -> str:
    """Build browser-use task to check application status on a platform."""
    urls = {
        "linkedin": "https://www.linkedin.com/my-items/saved-jobs/",
        "naukri": "https://www.naukri.com/mnjuser/recommendedjobs",
        "indeed": "https://www.indeed.com/myjobs",
        "foundit": "https://www.foundit.in/my-applications",
        "instahyre": "https://www.instahyre.com/candidate/opportunities/",
    }
    check_url = urls.get(platform, "")
    if not check_url:
        return f"Cannot check status for platform: {platform}"

    companies = ", ".join(set(a.company for a in apps[:10]))
    return (
        f"Go to {check_url}. "
        f"Look for application status updates for these companies: {companies}. "
        f"For each application found, report the status in this format: "
        f"COMPANY: <name> | STATUS: <viewed/shortlisted/interview/rejected/no_update>. "
        f"One per line. If you can't find status info, report NO_UPDATE for all."
    )


def _parse_status_updates(result_text: str, apps: list) -> dict:
    """Parse browser agent output into {app_id: new_status} dict."""
    updates = {}
    if not result_text:
        return updates

    status_map = {
        "viewed": "viewed",
        "shortlisted": "shortlisted",
        "interview": "interview",
        "rejected": "rejected",
        "hired": "offer",
        "offer": "offer",
    }

    for line in result_text.strip().split("\n"):
        line = line.strip().upper()
        if "COMPANY:" not in line or "STATUS:" not in line:
            continue
        try:
            parts = {}
            for segment in line.split("|"):
                if ":" in segment:
                    key, val = segment.split(":", 1)
                    parts[key.strip()] = val.strip().lower()

            company = parts.get("company", "")
            status = parts.get("status", "no_update")

            if status == "no_update":
                continue

            new_status = status_map.get(status)
            if not new_status:
                continue

            # Match to application by company name
            for app in apps:
                if app.company.lower() in company or company in app.company.lower():
                    updates[app.id] = new_status
                    break
        except Exception:
            continue

    return updates
