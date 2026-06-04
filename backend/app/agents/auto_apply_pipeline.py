"""
auto_apply_pipeline.py — Fully automated job application pipeline.

Chains: Multi-platform search → Score → Find recruiter → Tailor resume →
        Send cold email + LinkedIn connection/message

Prepares outreach end-to-end, then emits an approval checkpoint before any
email or LinkedIn action is dispatched.
"""
import asyncio
import base64
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import HumanMessage

from app.agents.resume_agent import resume_agent_node
from app.agents.state import AgentState
from app.core.event_bus import emit
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings, fetch_user_profile_text
from app.services.email_finder_service import find_recruiter_email as find_email_for_company
from app.services.job_platforms_service import scrape_jobs, JobListing
from app.services.gmail_service import GmailMCPClient

logger = logging.getLogger(__name__)

COLD_EMAIL_PROMPT = """Write a short, personalized cold email to a recruiter about a job opening.

Recruiter: {recruiter_name} ({recruiter_email})
Company: {company}
Role: {role}
Job Description (first 500 chars): {jd_snippet}
My Background: {profile_snippet}

Write a 3-paragraph email:
1. Hook — mention the specific role and something about the company
2. Value — 2-3 sentences on why I'm a fit (reference specific skills from JD)
3. CTA — ask for a quick call, suggest availability

Keep it under 150 words. Be direct, not generic.
Format: Subject: <subject>\n\n<body>"""

LINKEDIN_NOTE_PROMPT = """Write a LinkedIn connection request note (max 280 chars).

I'm reaching out about the {role} role at {company}.
My background: {profile_snippet}

Be concise, professional, mention the specific role. Max 280 characters."""


async def run_auto_apply_pipeline(
    user_id: str,
    search_query: str,
    location: str = "Remote",
    max_applications: int = 5,
    platforms: list[str] | None = None,
    linkedin_credentials: dict | None = None,
    live_browser: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run the fully automated job application pipeline.

    Steps:
    1. Scrape jobs from all platforms via JobSpy
    2. Score each job against user profile
    3. For top N matches: find recruiter email via Hunter.io
    4. Tailor resume per JD
    5. Prepare cold email to recruiter
    6. Prepare LinkedIn connection request + message for approval

    Args:
        user_id: The authenticated user's ID
        search_query: Job search keywords
        location: Location filter
        max_applications: Max jobs to apply to in this run
        platforms: Which platforms to scrape (default: all)
        linkedin_credentials: {"email": "...", "password": "..."} for LinkedIn login

    Returns:
        Pipeline results with stats and per-job outcomes
    """
    start_ts = time.monotonic()
    results: dict[str, Any] = {
        "jobs_found": 0,
        "jobs_scored": 0,
        "applications_sent": 0,
        "emails_sent": 0,
        "linkedin_connections_sent": 0,
        "errors": [],
        "applications": [],
    }

    # ── Step 1: Scrape jobs from all platforms ──────────────────────
    logger.info("[AutoApply] Step 1: Scraping jobs for '%s' in '%s'", search_query, location)
    if run_id:
        emit(run_id, "browser", {
            "phase": "auto_apply_search",
            "mode": "visible" if live_browser else "headless",
            "query": search_query,
            "location": location,
        })
    jobs = await asyncio.get_running_loop().run_in_executor(
        None, scrape_jobs, search_query, location, max_applications * 3, 72, platforms
    )
    results["jobs_found"] = len(jobs)

    if not jobs:
        results["errors"].append("No jobs found across any platform")
        return results

    # ── Step 2: Score jobs against user profile ─────────────────────
    logger.info("[AutoApply] Step 2: Scoring %d jobs", len(jobs))
    model_settings = fetch_model_settings(user_id)
    if not model_settings:
        results["errors"].append("No AI model configured — add API key in Settings")
        return results

    user_profile = fetch_user_profile_text(user_id)
    llm = _build_llm(model_settings)

    scored_jobs: list[tuple[JobListing, int]] = []
    for job in jobs[:max_applications * 2]:
        score = _score_job_quick(llm, job, user_profile)
        scored_jobs.append((job, score))

    scored_jobs.sort(key=lambda x: x[1], reverse=True)
    top_jobs = scored_jobs[:max_applications]
    results["jobs_scored"] = len(scored_jobs)

    # ── Step 3-6: For each top job, run the full apply sequence ─────

    # Determine auto_mode from user settings
    from app.core.database import AsyncSessionLocal
    from app.models.db import User as UserModel
    from sqlalchemy import select as sel
    auto_mode = "drafts"
    linkedin_email = None
    linkedin_password = None

    async with AsyncSessionLocal() as db:
        res = await db.execute(sel(UserModel).where(UserModel.id == uuid.UUID(user_id)))
        user_row = res.scalar_one_or_none()
        if user_row:
            auto_mode = user_row.auto_mode or "drafts"
            if user_row.linkedin_email_enc and user_row.linkedin_password_enc:
                from app.core.security import decrypt_api_key
                from app.core.config import settings as app_settings
                linkedin_email = decrypt_api_key(user_row.linkedin_email_enc, app_settings.APP_SECRET_KEY)
                linkedin_password = decrypt_api_key(user_row.linkedin_password_enc, app_settings.APP_SECRET_KEY)

    if linkedin_credentials:
        linkedin_email = linkedin_credentials.get("email")
        linkedin_password = linkedin_credentials.get("password")

    # Login to LinkedIn via browser-use if auto mode + credentials available
    linkedin_ready = False
    if linkedin_email and linkedin_password and auto_mode == "auto":
        try:
            from app.services.browser_control_service import linkedin_login as browser_login
            await browser_login(llm, user_id, linkedin_email, linkedin_password, live_browser=live_browser, run_id=run_id)
            linkedin_ready = True
        except Exception as exc:
            logger.warning("[AutoApply] LinkedIn browser login failed: %s", exc)
            results["errors"].append("LinkedIn browser login failed")

    for job, score in top_jobs:
        app_result = await _apply_to_job(
            user_id=user_id,
            job=job,
            score=score,
            llm=llm,
            model_settings=model_settings,
            user_profile=user_profile,
            linkedin_ready=linkedin_ready,
            auto_mode=auto_mode,
            live_browser=live_browser,
            run_id=run_id,
        )
        results["applications"].append(app_result)
        if app_result.get("email_sent"):
            results["emails_sent"] += 1
        if app_result.get("linkedin_sent"):
            results["linkedin_connections_sent"] += 1
        if app_result.get("email_sent") or app_result.get("linkedin_sent"):
            results["applications_sent"] += 1

    approval_actions = [
        action
        for app in results["applications"]
        for action in app.get("approval_actions", [])
    ]
    if approval_actions:
        results["type"] = "auto_apply_approval"
        results["requires_approval"] = True
        results["actions_pending"] = approval_actions
        results["live_browser"] = live_browser

    duration_ms = int((time.monotonic() - start_ts) * 1000)
    results["duration_ms"] = duration_ms

    logger.info(
        "[AutoApply] Pipeline complete: %d jobs found, %d applications sent in %dms",
        results["jobs_found"], results["applications_sent"], duration_ms
    )
    return results


async def _apply_to_job(
    user_id: str,
    job: JobListing,
    score: int,
    llm: Any,
    model_settings: Any,
    user_profile: str,
    linkedin_ready: bool = False,
    auto_mode: str = "drafts",
    live_browser: bool = False,
    run_id: str | None = None,
) -> dict:
    """Apply to a single job: find recruiter → tailor resume → email + LinkedIn."""
    result = {
        "company": job.company,
        "role": job.title,
        "platform": job.platform,
        "score": score,
        "job_url": job.job_url,
        "email_sent": False,
        "linkedin_sent": False,
        "draft_saved": False,
        "error": None,
    }

    try:
        if run_id:
            emit(run_id, "browser", {
                "phase": "apply_prepare",
                "company": job.company,
                "role": job.title,
                "url": job.job_url,
            })
        # ── Find recruiter email (self-hosted, no API key) ──────────
        recruiter = await find_email_for_company(job.company)
        recruiter_email = recruiter["email"] if recruiter else None
        recruiter_name = f"{recruiter.get('first_name', '')} {recruiter.get('last_name', '')}".strip() if recruiter else "Hiring Manager"

        # ── Tailor resume ───────────────────────────────────────────
        state = AgentState(
            user_id=user_id,
            run_id=str(uuid.uuid4()),
            task_type="resume_optimize",
            messages=[HumanMessage(content=job.description[:3000])],
            context={"jd_text": job.description[:3000], "template": "modern"},
            status="running",
            pending_action=None,
            result=None,
            error=None,
        )
        resume_result = await asyncio.get_running_loop().run_in_executor(
            None, resume_agent_node, state
        )
        result["resume_tailored"] = resume_result["status"] in ("completed", "awaiting_approval")

        # ── Generate cold email ─────────────────────────────────────
        email_content = None
        if recruiter_email:
            email_content = _generate_cold_email(
                llm, recruiter_name, recruiter_email,
                job.company, job.title, job.description, user_profile
            )

        # ── AUTO MODE: Queue for approval (HITL gate preserved) ────
        # NOTE: Even in "auto" mode, we preserve the human-in-the-loop gate
        # as required by CLAUDE.md. The user must explicitly approve each
        # email send and LinkedIn connection before they are dispatched.
        # To enable truly autonomous sending, the user must approve the
        # checkpoint emitted below.
        if auto_mode == "auto":
            # Prepare actions but DO NOT execute without approval
            result["draft_saved"] = True
            result["requires_approval"] = True

            if run_id:
                checkpoint_data = {
                    "type": "auto_apply_approval",
                    "company": job.company,
                    "role": job.title,
                    "actions_pending": []
                }

                # Autonomous browser application — the agent fills + submits the
                # real job form on approval (HITL gate preserved).
                if job.job_url:
                    checkpoint_data["actions_pending"].append({
                        "action": "apply_browser",
                        "job_url": job.job_url,
                        "company": job.company,
                        "role": job.title,
                    })
                    result["apply_browser_queued"] = True

                if email_content and recruiter_email:
                    checkpoint_data["actions_pending"].append({
                        "action": "send_email",
                        "to": recruiter_email,
                        "subject": email_content["subject"],
                        "body": email_content["body"],
                    })
                    result["email_draft"] = email_content
                    result["recruiter_email"] = recruiter_email

                if linkedin_ready:
                    from app.services.proxycurl_service import ProxycurlService
                    proxycurl = ProxycurlService()
                    contacts = await proxycurl.find_contacts(job.company, "recruiter")
                    if contacts and contacts[0].get("linkedin_url"):
                        note = _generate_linkedin_note(llm, job.company, job.title, user_profile)
                        checkpoint_data["actions_pending"].append({
                            "action": "send_linkedin_connection",
                            "profile_url": contacts[0]["linkedin_url"],
                            "note": note,
                        })
                        result["linkedin_draft"] = {
                            "profile_url": contacts[0]["linkedin_url"],
                            "note": note,
                        }

                emit(run_id, "checkpoint", checkpoint_data)
                result["approval_actions"] = checkpoint_data["actions_pending"]

        # ── DRAFTS MODE: Save for review ────────────────────────────
        else:
            result["draft_saved"] = True
            if run_id:
                emit(run_id, "checkpoint", {
                    "type": "review_application_draft",
                    "company": job.company,
                    "role": job.title,
                    "job_url": job.job_url,
                    "message": "Review draft before any email or application is submitted.",
                })
            result["draft"] = {
                "recruiter_email": recruiter_email,
                "recruiter_name": recruiter_name,
                "email_subject": email_content["subject"] if email_content else None,
                "email_body": email_content["body"] if email_content else None,
                "resume_ready": result.get("resume_tailored", False),
            }

    except Exception as exc:
        result["error"] = "Auto-apply preparation failed"
        logger.warning("[AutoApply] Failed for %s at %s: %s", job.title, job.company, exc)

    return result


def _score_job_quick(llm: Any, job: JobListing, profile: str) -> int:
    """Score a job 0-100 using critical thinking analysis."""
    try:
        from app.agents.thinking import think_about_job_match
        result = think_about_job_match(llm, profile, f"{job.title} at {job.company}\n{job.description[:500]}")
        match_level = result.get("match_level", "MEDIUM")
        decision = result.get("decision", "MAYBE")

        # Convert thinking output to numeric score
        level_scores = {"HIGH": 85, "MEDIUM": 60, "LOW": 30}
        decision_bonus = {"YES": 10, "MAYBE": 0, "NO": -20}
        base = level_scores.get(match_level, 50)
        bonus = decision_bonus.get(decision, 0)
        return max(0, min(100, base + bonus))
    except Exception:
        return 50


def _generate_cold_email(
    llm: Any, recruiter_name: str, recruiter_email: str,
    company: str, role: str, jd: str, profile: str
) -> dict | None:
    """Generate personalized cold email."""
    try:
        resp = llm.invoke([HumanMessage(
            content=COLD_EMAIL_PROMPT.format(
                recruiter_name=recruiter_name,
                recruiter_email=recruiter_email,
                company=company,
                role=role,
                jd_snippet=jd[:500],
                profile_snippet=profile[:300],
            )
        )])
        text = resp.content.strip()
        if text.startswith("Subject:"):
            lines = text.split("\n", 2)
            subject = lines[0].replace("Subject:", "").strip()
            body = lines[2].strip() if len(lines) > 2 else text
            return {"subject": subject, "body": body}
        return {"subject": f"Re: {role} at {company}", "body": text}
    except Exception as exc:
        logger.warning("Cold email generation failed: %s", exc)
        return None


def _generate_linkedin_note(llm: Any, company: str, role: str, profile: str) -> str:
    """Generate LinkedIn connection note (max 280 chars)."""
    try:
        resp = llm.invoke([HumanMessage(
            content=LINKEDIN_NOTE_PROMPT.format(
                company=company, role=role, profile_snippet=profile[:200]
            )
        )])
        return resp.content.strip()[:280]
    except Exception:
        return f"Hi! I'm interested in the {role} role at {company}. Would love to connect."[:280]
