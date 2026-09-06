"""
Internal endpoints called by BullMQ worker only.
Not exposed via Nginx (blocked at nginx level).
Protected by a dedicated INTERNAL_SECRET header — not Supabase JWT.
"""
import asyncio
import hmac
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException
from langchain_core.messages import HumanMessage
from pydantic import BaseModel, Field

from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR
from app.core.config import settings
from app.core.event_bus import emit

router = APIRouter(prefix="/internal", tags=["internal"])
logger = logging.getLogger(__name__)


def _verify_secret(x_internal_secret: str = Header(...)) -> None:
    internal_secret = settings.INTERNAL_SECRET or settings.APP_SECRET_KEY
    if not hmac.compare_digest(x_internal_secret, internal_secret):
        raise HTTPException(status_code=403, detail="Forbidden")


class JobSearchTrigger(BaseModel):
    user_id: str
    run_id: str
    search_query: str
    location: str
    max_results: int
    live_browser: bool = False
    work_mode: str = ""
    platforms: list[str] = Field(default_factory=list)
    remote: str = "any"


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
            "live_browser": payload.live_browser,
            "work_mode": payload.work_mode,
            "platforms": payload.platforms,
            "remote": payload.remote,
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    try:
        result_state = await asyncio.wait_for(
            asyncio.get_running_loop().run_in_executor(
                None, job_search_agent_node, state
            ),
            timeout=120,
        )
    except TimeoutError:
        logger.error("Job search run %s timed out", payload.run_id)
        result_state = {**state, "status": "failed", "error": "Job search timed out"}

    async with AsyncSessionLocal() as db:
        res = await db.execute(
            select(AgentRun).where(AgentRun.id == uuid.UUID(payload.run_id))
        )
        run = res.scalar_one_or_none()
        if run:
            if result_state["status"] == "failed" and result_state.get("error"):
                logger.warning(
                    "Job search run %s failed: %s",
                    payload.run_id,
                    result_state.get("error"),
                )
            run.status = result_state["status"]
            run.output = (
                result_state.get("result")
                if result_state["status"] == "completed"
                else {"error": CLIENT_SAFE_AGENT_ERROR}
            )
            run.completed_at = datetime.now(timezone.utc)

        # Persistence lives in the node (_persist_saved_jobs: score >= 50,
        # idempotent on user_id+url), so the worker never double-writes —
        # not even on BullMQ retries. The result carries saved_count.
        await db.commit()

    if result_state["status"] == "completed":
        emit(payload.run_id, "complete", result_state.get("result") or {})
    elif result_state["status"] == "awaiting_approval":
        emit(payload.run_id, "checkpoint", result_state.get("pending_action") or {})
    else:
        emit(payload.run_id, "error", CLIENT_SAFE_AGENT_ERROR)

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
    from app.models.db import JobApplication, User
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

        # Auto-cancel: check if recruiter already replied before sending follow-up
        if await _has_recruiter_replied(
            db, payload.user_id, application.company,
            application.role, application.applied_at,
        ):
            logger.info(
                "Follow-up day-%d CANCELLED for application %s — recruiter already replied",
                payload.day, payload.application_id,
            )
            application.followup_day5 = None
            application.followup_day12 = None
            await db.commit()
            return {
                "status": "cancelled",
                "reason": "recruiter_replied",
                "application_id": payload.application_id,
            }

    await schedule_followups(payload.user_id, payload.application_id, application.applied_at)
    logger.info(
        "Follow-up day-%d triggered for application %s user %s",
        payload.day,
        payload.application_id,
        payload.user_id,
    )
    return {"status": "scheduled", "day": payload.day, "application_id": payload.application_id}


async def _has_recruiter_replied(
    db, user_id: str, company: str, role: str, applied_at, window_days: int = 30,
) -> bool:
    """Check Gmail for recruiter replies since application was submitted.

    Searches Gmail for threads mentioning the company or role since applied_at.
    If any thread has a reply from someone who is NOT the user → recruiter replied.
    """
    from app.services.gmail_service import GmailMCPClient
    from app.models.db import User

    user_res = await db.execute(select(User).where(User.id == uuid.UUID(user_id)))
    user = user_res.scalar_one_or_none()
    if not user:
        return False

    user_email = user.email
    if not user_email:
        return False

    gmail = GmailMCPClient(user_id)
    since_str = applied_at.strftime("%Y/%m/%d") if applied_at else None

    queries = []
    if company:
        domain = company.lower().replace(" ", "")
        queries.append(f"{company} newer_than:{window_days}d")
    if role:
        queries.append(f'"{role}" newer_than:{window_days}d')

    for query in queries:
        try:
            threads = gmail.search_threads(query, max_results=5)
            if not isinstance(threads, list):
                continue
            for thread in threads:
                thread_id = thread.get("threadId") or thread.get("id")
                if not thread_id:
                    continue
                try:
                    details = gmail.get_thread(thread_id)
                except Exception:
                    continue
                messages = details.get("messages", details.get("Messages", []))
                for msg in reversed(messages):
                    headers = msg.get("payload", {}).get("headers", [])
                    from_addr = ""
                    for h in headers:
                        if h.get("name", "").lower() == "from":
                            from_addr = h.get("value", "").lower()
                            break
                    if from_addr and user_email.lower() not in from_addr:
                        logger.info(
                            "Found recruiter reply in thread %s from %s for user %s",
                            thread_id, from_addr, user_id,
                        )
                        return True
        except Exception as exc:
            logger.debug("Gmail recruiter-reply check failed for query '%s': %s", query, exc)

    return False



class StatusCheckTrigger(BaseModel):
    user_id: str


@router.post("/agents/daily-search", dependencies=[Depends(_verify_secret)])
async def daily_search(payload: StatusCheckTrigger):
    """Daily automated job search based on user preferences.

    Fetches user preferences from memory, searches all platforms + Google Jobs,
    scores matches, and saves top results as applications.

    Honors per-user opt-in: only members who (1) have an active LLM model
    configured and (2) have saved job preferences (target_roles /
    preferred_locations) get a daily search. "all" fans out across all
    eligible members; an explicit user_id targets just that member.
    """
    from sqlalchemy import select
    from app.core.database import AsyncSessionLocal
    from app.core.model_router import get_llm
    from app.models.db import JobApplication, User as UserModel, UserModelSettings, UserPreferences
    from app.agents.memory.manager import MemoryManager
    from app.services.job_platforms_service import scrape_all_platforms
    from app.services.indian_platforms_service import search_google_jobs

    jobs_found = 0
    applications_queued = 0
    users_searched = 0
    visible_browser_opted_in = 0  # how many users have prefer_live_browser=True

    async with AsyncSessionLocal() as db:
        if payload.user_id == "all":
            # Fan-out: every user with an active model + saved preferences.
            res = await db.execute(
                select(UserModel)
                .join(UserModelSettings, UserModelSettings.user_id == UserModel.id)
                .join(UserPreferences, UserPreferences.user_id == UserModel.id)
                .where(
                    UserModelSettings.is_active == True,  # noqa: E712
                    UserPreferences.target_roles.is_not(None),
                )
                .distinct()
            )
            users = res.scalars().all()
        else:
            res = await db.execute(
                select(UserModel).where(UserModel.supabase_uid == payload.user_id)
            )
            users = res.scalars().all()

        for user in users:
            try:
                user_id = str(user.id)
                llm = await get_llm(user_id, db)
                if llm is None:
                    logger.debug("Skipping daily search for %s: no active model", user_id)
                    continue

                # Read per-user preference so we can log opted-in users and
                # potentially trigger visible prepare-apply for them in a future
                # iteration.  Right now we just report the count.
                prefs_row = (await db.execute(
                    select(UserPreferences).where(UserPreferences.user_id == user.id)
                )).scalar_one_or_none()
                if prefs_row and getattr(prefs_row, "prefer_live_browser", False):
                    visible_browser_opted_in += 1
                    logger.info(
                        "Daily search: user %s opted into live browser — saved jobs "
                        "will open a visible Chromium when the user clicks Apply.",
                        user_id,
                    )

                # Get user preferences from memory
                mgr = MemoryManager(
                    db_url=settings.DATABASE_URL, redis_url=settings.REDIS_URL
                )
                await mgr.initialize()
                user_ctx = await mgr.get_user_context(user_id)
                await mgr.close()

                search_term = user_ctx.get("target_roles", "software engineer")
                location = user_ctx.get("preferred_locations", "Bangalore")
                if isinstance(search_term, list) and search_term:
                    search_term = search_term[0]
                if isinstance(location, list) and location:
                    location = location[0]
                if not search_term or not location:
                    logger.debug("Skipping daily search for %s: missing prefs", user_id)
                    continue

                users_searched += 1

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
                            JobApplication.user_id == user.id,
                            JobApplication.job_url == job.job_url,
                        )
                    )
                    if existing.scalar_one_or_none():
                        continue  # Skip duplicates

                    app = JobApplication(
                        user_id=user.id,
                        company=job.company,
                        role=job.title,
                        location=job.location,
                        job_url=job.job_url,
                        jd_text=job.description,
                        status="saved",
                    )
                    db.add(app)
                    applications_queued += 1

                await db.commit()
            except Exception as exc:
                logger.warning("Daily search failed for user %s: %s", user.id, exc)

    logger.info(
        "Daily search complete: %d users searched (%d opted into live browser), "
        "%d jobs found, %d queued",
        users_searched, visible_browser_opted_in, jobs_found, applications_queued,
    )
    return {
        "status": "ok",
        "users_searched": users_searched,
        "visible_browser_opted_in": visible_browser_opted_in,
        "jobs_found": jobs_found,
        "applications_queued": applications_queued,
    }


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
    from app.services.browser_control_service import run_browser_task_with_captcha_retry as run_browser_task

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
                    updated_count += 1
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
        except Exception as exc:
            logger.debug("Skipping unparsable status update line: %s", exc)
            continue

    return updates
