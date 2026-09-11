"""
auto_apply_service.py — Platform-agnostic job application handlers.

Every portal (LinkedIn, Naukri, Indeed, Workday, Greenhouse, Lever, any ATS)
goes through the same universal HITL-safe apply path:

  1. Build user profile context from DB + RAG
  2. Use form_filler_service to navigate, fill, and STOP before final submit
  3. Emit a 'checkpoint' SSE event so the orchestrator sets
     state["status"] = "awaiting_approval"
  4. Actual submission only happens after explicit user approval via
     /api/v1/agents/{run_id}/approve

NEVER submit without user approval — this is enforced at the form_filler
level (submit=False) AND by the task prompt wording, giving two independent
guardrails against accidental submission.
"""
import asyncio
import logging
import secrets
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from langchain_core.language_models import BaseChatModel

from app.services.browser_control_service import run_browser_task_with_captcha_retry as run_browser_task
from app.core.event_bus import emit

logger = logging.getLogger(__name__)
_RANDOM = secrets.SystemRandom()

ApplyStatus = Literal["draft_saved", "requires_manual", "failed"]
GENERIC_APPLY_FAILURE = "Application automation failed"


@dataclass
class ApplyResult:
    platform: str
    job_url: str
    status: ApplyStatus
    message: str = ""


async def _human_delay() -> None:
    """Random delay to avoid detection (2-6s)."""
    await asyncio.sleep(_RANDOM.uniform(2.0, 6.0))


def _detect_portal(job_url: str) -> str:
    """Detect portal name from URL domain for task-hint purposes."""
    try:
        host = urlparse(job_url).netloc.lower().lstrip("www.")
    except Exception:
        return "unknown"
    portal_map = {
        "linkedin.com": "LinkedIn",
        "naukri.com": "Naukri",
        "indeed.com": "Indeed",
        "glassdoor.com": "Glassdoor",
        "instahyre.com": "Instahyre",
        "foundit.in": "Foundit",
        "cutshort.io": "Cutshort",
        "hirect.in": "Hirect",
        "shine.com": "Shine",
        "internshala.com": "Internshala",
        "iimjobs.com": "iimjobs",
        "freshersworld.com": "Freshersworld",
        "myworkdayjobs.com": "Workday",
        "greenhouse.io": "Greenhouse",
        "lever.co": "Lever",
        "ashbyhq.com": "Ashby",
        "smartrecruiters.com": "SmartRecruiters",
        "bamboohr.com": "BambooHR",
        "remoteok.com": "RemoteOK",
        "remotive.com": "Remotive",
        "wellfound.com": "Wellfound",
        "angel.co": "AngelList",
        "ziprecruiter.com": "ZipRecruiter",
        "monster.com": "Monster",
        "dice.com": "Dice",
    }
    for domain, name in portal_map.items():
        if domain in host:
            return name
    return host.split(".")[0].title() if host else "Unknown"


async def apply_to_any_portal(
    llm: BaseChatModel,
    user_id: str,
    job_url: str,
    run_id: str | None = None,
    resume_path: str | None = None,
    cover_letter: str = "",
    job_description: str = "",
    past_learnings: list[str] | None = None,
) -> ApplyResult:
    """Universal HITL-safe apply — works on any job portal or ATS.

    past_learnings — forwarded from the harness context["_memory"]["learnings"].
    Injected into the form filler task prompt so the browser agent adapts based
    on what has worked and failed for this user previously (e.g.
    "portal:greenhouse:auto_fill_works", "portal:workday:requires_manual").
    """
    from app.services.form_filler_service import fill_and_submit_form

    portal = _detect_portal(job_url)
    await _human_delay()

    try:
        result = await fill_and_submit_form(
            llm=llm,
            user_id=user_id,
            job_url=job_url,
            resume_path=resume_path,
            cover_letter=cover_letter,
            job_description=job_description,
            submit=False,  # HITL gate — never submit automatically
            past_learnings=past_learnings,
        )
    except Exception as exc:
        logger.warning("apply_to_any_portal failed for user %s url %s: %s", user_id, job_url, exc)
        return ApplyResult(portal.lower(), job_url, "failed", GENERIC_APPLY_FAILURE)

    status_raw = (result or {}).get("status", "failed")
    message = (result or {}).get("message", "")

    if status_raw in ("requires_manual", "requires_account_creation"):
        return ApplyResult(portal.lower(), job_url, "requires_manual", message)

    if status_raw == "failed":
        return ApplyResult(portal.lower(), job_url, "failed", message)

    # status == "ready_for_review" — emit HITL checkpoint
    if run_id:
        emit(run_id, "checkpoint", {
            "type": "apply_review",
            "portal": portal,
            "job_url": job_url,
            "message": f"Application form filled on {portal}. Review and approve to submit.",
            "form_summary": message[:500],
        })

    return ApplyResult(portal.lower(), job_url, "draft_saved", message)


# ── Per-portal helpers (backward-compatible thin wrappers) ──────────────────
# All delegate to apply_to_any_portal so every portal enforces HITL.


async def apply_linkedin(
    llm: BaseChatModel, user_id: str, job_url: str,
    resume_path: str | None = None, run_id: str | None = None,
) -> ApplyResult:
    return await apply_to_any_portal(llm, user_id, job_url, run_id=run_id, resume_path=resume_path)


async def apply_naukri(
    llm: BaseChatModel, user_id: str, job_url: str,
    resume_path: str | None = None, run_id: str | None = None,
) -> ApplyResult:
    return await apply_to_any_portal(llm, user_id, job_url, run_id=run_id, resume_path=resume_path)


async def apply_instahyre(
    llm: BaseChatModel, user_id: str, job_url: str,
    message: str = "", run_id: str | None = None,
) -> ApplyResult:
    return await apply_to_any_portal(llm, user_id, job_url, run_id=run_id)


async def apply_indeed(
    llm: BaseChatModel, user_id: str, job_url: str,
    resume_path: str | None = None, run_id: str | None = None,
) -> ApplyResult:
    return await apply_to_any_portal(llm, user_id, job_url, run_id=run_id, resume_path=resume_path)


async def apply_foundit(
    llm: BaseChatModel, user_id: str, job_url: str,
    resume_path: str | None = None, run_id: str | None = None,
) -> ApplyResult:
    return await apply_to_any_portal(llm, user_id, job_url, run_id=run_id, resume_path=resume_path)


async def apply_cutshort(
    llm: BaseChatModel, user_id: str, job_url: str,
    run_id: str | None = None,
) -> ApplyResult:
    return await apply_to_any_portal(llm, user_id, job_url, run_id=run_id)


# ── Platform registry — kept for backward compat with auto_apply_pipeline ───
PLATFORM_HANDLERS = {
    "linkedin": apply_linkedin,
    "naukri": apply_naukri,
    "instahyre": apply_instahyre,
    "indeed": apply_indeed,
    "foundit": apply_foundit,
    "cutshort": apply_cutshort,
}


async def apply_to_external_form(
    llm: BaseChatModel,
    user_id: str,
    job_url: str,
    resume_path: str | None = None,
    cover_letter: str = "",
    job_description: str = "",
    run_id: str | None = None,
) -> ApplyResult:
    """Alias kept for backward compatibility — delegates to apply_to_any_portal."""
    return await apply_to_any_portal(
        llm, user_id, job_url,
        run_id=run_id,
        resume_path=resume_path,
        cover_letter=cover_letter,
        job_description=job_description,
    )


async def apply_to_job(
    llm: BaseChatModel,
    user_id: str,
    platform: str,
    job_url: str,
    resume_path: str | None = None,
    message: str = "",
    cover_letter: str = "",
    job_description: str = "",
    run_id: str | None = None,
) -> ApplyResult:
    """Apply to a job on any portal — routes everything through the universal HITL path.

    The platform hint is used only for logging/SSE labelling; the actual
    apply logic works from the URL regardless of whether the platform is
    named in PLATFORM_HANDLERS or not.  Unknown portals (any ATS URL,
    company career page, job board not listed) work without any changes.
    """
    return await apply_to_any_portal(
        llm, user_id, job_url,
        run_id=run_id,
        resume_path=resume_path,
        cover_letter=cover_letter,
        job_description=job_description,
    )
