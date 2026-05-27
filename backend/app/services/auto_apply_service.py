"""
auto_apply_service.py — Platform-specific job application handlers.

Each platform has its own apply flow:
- LinkedIn: Easy Apply (already in browser_control_service)
- Naukri: Fill form + upload resume
- Instahyre: One-click apply + optional message
- Indeed: Multi-step form
- Foundit: Upload resume + fill fields

All handlers use browser-use for automation with human-like delays.
"""
import asyncio
import logging
import random
from dataclasses import dataclass
from typing import Literal

from langchain_core.language_models import BaseChatModel

from app.services.browser_control_service import run_browser_task, _get_browser_config

logger = logging.getLogger(__name__)

ApplyStatus = Literal["applied", "draft_saved", "failed", "requires_manual"]


@dataclass
class ApplyResult:
    platform: str
    job_url: str
    status: ApplyStatus
    message: str = ""


async def _human_delay():
    """Random delay to avoid detection (2-6s)."""
    await asyncio.sleep(random.uniform(2.0, 6.0))


async def apply_linkedin(
    llm: BaseChatModel, user_id: str, job_url: str, resume_path: str | None = None
) -> ApplyResult:
    """Apply via LinkedIn Easy Apply."""
    task = (
        f"Go to {job_url}. "
        f"Click the 'Easy Apply' button. "
        f"Fill in any required fields with reasonable defaults. "
        f"{'Upload resume from ' + resume_path + '. ' if resume_path else ''}"
        f"Click through all steps (Next, Review, Submit). "
        f"Confirm the application was submitted. If it requires external redirect, report 'REQUIRES_MANUAL'."
    )
    await _human_delay()
    try:
        result = await run_browser_task(llm, task, user_id, max_steps=20)
        if "REQUIRES_MANUAL" in (result or ""):
            return ApplyResult("linkedin", job_url, "requires_manual", result)
        return ApplyResult("linkedin", job_url, "applied", result or "Submitted")
    except Exception as exc:
        return ApplyResult("linkedin", job_url, "failed", str(exc))


async def apply_naukri(
    llm: BaseChatModel, user_id: str, job_url: str, resume_path: str | None = None
) -> ApplyResult:
    """Apply on Naukri.com — fill form fields and upload resume."""
    task = (
        f"Go to {job_url}. "
        f"Click the 'Apply' or 'Apply on company site' button. "
        f"If there's an application form, fill in all required fields. "
        f"{'Upload resume from ' + resume_path + '. ' if resume_path else 'Use the already uploaded resume. '}"
        f"Submit the application. "
        f"If it redirects to an external site, report 'REQUIRES_MANUAL'. "
        f"Confirm submission."
    )
    await _human_delay()
    try:
        result = await run_browser_task(llm, task, user_id, max_steps=20)
        if "REQUIRES_MANUAL" in (result or ""):
            return ApplyResult("naukri", job_url, "requires_manual", result)
        return ApplyResult("naukri", job_url, "applied", result or "Submitted")
    except Exception as exc:
        return ApplyResult("naukri", job_url, "failed", str(exc))


async def apply_instahyre(
    llm: BaseChatModel, user_id: str, job_url: str, message: str = ""
) -> ApplyResult:
    """Apply on Instahyre — one-click apply with optional message."""
    msg_part = f"Type this message in the message box: '{message[:500]}'. " if message else ""
    task = (
        f"Go to {job_url}. "
        f"Click the 'Apply' or 'I'm Interested' button. "
        f"{msg_part}"
        f"Submit. Confirm the application was sent."
    )
    await _human_delay()
    try:
        result = await run_browser_task(llm, task, user_id, max_steps=12)
        return ApplyResult("instahyre", job_url, "applied", result or "Submitted")
    except Exception as exc:
        return ApplyResult("instahyre", job_url, "failed", str(exc))


async def apply_indeed(
    llm: BaseChatModel, user_id: str, job_url: str, resume_path: str | None = None
) -> ApplyResult:
    """Apply on Indeed — multi-step form."""
    task = (
        f"Go to {job_url}. "
        f"Click 'Apply now' or 'Apply on company site'. "
        f"If it's Indeed's own form, fill all required fields. "
        f"{'Upload resume from ' + resume_path + '. ' if resume_path else ''}"
        f"Click through all steps and submit. "
        f"If redirected externally, report 'REQUIRES_MANUAL'. "
        f"Confirm submission."
    )
    await _human_delay()
    try:
        result = await run_browser_task(llm, task, user_id, max_steps=20)
        if "REQUIRES_MANUAL" in (result or ""):
            return ApplyResult("indeed", job_url, "requires_manual", result)
        return ApplyResult("indeed", job_url, "applied", result or "Submitted")
    except Exception as exc:
        return ApplyResult("indeed", job_url, "failed", str(exc))


async def apply_foundit(
    llm: BaseChatModel, user_id: str, job_url: str, resume_path: str | None = None
) -> ApplyResult:
    """Apply on Foundit (Monster India)."""
    task = (
        f"Go to {job_url}. "
        f"Click the 'Apply' button. "
        f"Fill in any required fields. "
        f"{'Upload resume from ' + resume_path + '. ' if resume_path else ''}"
        f"Submit the application. Confirm it was sent."
    )
    await _human_delay()
    try:
        result = await run_browser_task(llm, task, user_id, max_steps=15)
        return ApplyResult("foundit", job_url, "applied", result or "Submitted")
    except Exception as exc:
        return ApplyResult("foundit", job_url, "failed", str(exc))


async def apply_cutshort(
    llm: BaseChatModel, user_id: str, job_url: str
) -> ApplyResult:
    """Apply on Cutshort — typically one-click."""
    task = (
        f"Go to {job_url}. "
        f"Click 'Apply' or 'I'm interested'. "
        f"If there's a form, fill required fields. "
        f"Submit. Confirm application sent."
    )
    await _human_delay()
    try:
        result = await run_browser_task(llm, task, user_id, max_steps=12)
        return ApplyResult("cutshort", job_url, "applied", result or "Submitted")
    except Exception as exc:
        return ApplyResult("cutshort", job_url, "failed", str(exc))


# Platform handler registry
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
) -> ApplyResult:
    """Apply to any job that has its own application form (Workday, Greenhouse, Lever, etc.).

    This is the universal fallback — it uses the form_filler_service to intelligently
    fill any form using the user's profile data.
    """
    from app.services.form_filler_service import fill_and_submit_form

    await _human_delay()
    result = await fill_and_submit_form(
        llm=llm,
        user_id=user_id,
        job_url=job_url,
        resume_path=resume_path,
        cover_letter=cover_letter,
        job_description=job_description,
    )

    status_map = {"applied": "applied", "requires_manual": "requires_manual", "failed": "failed"}
    return ApplyResult(
        platform="external",
        job_url=job_url,
        status=status_map.get(result["status"], "failed"),
        message=result.get("message", ""),
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
) -> ApplyResult:
    """Apply to a job on any supported platform.

    Routes to the correct platform-specific handler. If the platform is unknown
    or the job redirects to an external form, uses the universal form filler.

    Args:
        llm: LLM for browser agent
        user_id: User ID for persistent session
        platform: Platform key (linkedin, naukri, etc.)
        job_url: Direct URL to the job posting
        resume_path: Optional path to tailored resume file
        message: Optional cover message (for platforms that support it)
        cover_letter: Full cover letter text for form fields
        job_description: JD text for "why this role" fields

    Returns:
        ApplyResult with status
    """
    handler = PLATFORM_HANDLERS.get(platform)

    # If no specific handler, use universal form filler
    if not handler:
        return await apply_to_external_form(
            llm, user_id, job_url, resume_path, cover_letter, job_description
        )

    # Try platform-specific handler first
    if platform == "instahyre":
        result = await handler(llm, user_id, job_url, message)
    elif platform == "cutshort":
        result = await handler(llm, user_id, job_url)
    else:
        result = await handler(llm, user_id, job_url, resume_path)

    # If platform handler reports REQUIRES_MANUAL (external redirect), use form filler
    if result.status == "requires_manual" and "redirect" in result.message.lower():
        return await apply_to_external_form(
            llm, user_id, job_url, resume_path, cover_letter, job_description
        )

    return result
