"""naukri_service.py — Naukri.com Job Search + Auto-Apply pilot (Browser Use).

This module is the Naukri-specific pilot for the Browser Use migration.  It
covers two flows:

  1. Job Search: navigate to Naukri, search by role/location, extract job
     listings (title, company, URL, description) into the existing JobListing
     schema used by all other sources.

  2. Auto-Apply: login flow → navigate to job posting → fill all application
     form fields from resume/RAG context → STOP at HITL checkpoint before
     submission.  Never submits without explicit user approval.

Human-like delays are read from config so they can be tuned without a code
deploy.  All browser actions are logged via BrowserActionTimer for
structured tracing.

Anti-detection trigger: if CAPTCHA block rate exceeds 20% over any rolling
10-run window, route Naukri traffic through a paid proxy (Scrapfly /
Browserbase) — see CONFIGURATION.md for env vars.  Do not add proxies
preemptively.
"""
from __future__ import annotations

import asyncio
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import quote_plus

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.event_bus import emit
from app.services.browser_logger import BrowserActionTimer, log_browser_action, save_debug_screenshot
from app.services.job_platforms_service import JobListing

logger = logging.getLogger(__name__)
_RANDOM = secrets.SystemRandom()

NAUKRI_BASE_URL = "https://www.naukri.com"


# ---------------------------------------------------------------------------
# Human-like delay helpers (values from config, not hardcoded)
# ---------------------------------------------------------------------------

async def _delay_navigate() -> None:
    """Pause after a page navigation."""
    lo = settings.BROWSER_DELAY_NAVIGATE_MIN_MS / 1000
    hi = settings.BROWSER_DELAY_NAVIGATE_MAX_MS / 1000
    await asyncio.sleep(_RANDOM.uniform(lo, hi))


async def _delay_fill() -> None:
    """Pause between form field fills."""
    lo = settings.BROWSER_DELAY_FILL_MIN_MS / 1000
    hi = settings.BROWSER_DELAY_FILL_MAX_MS / 1000
    await asyncio.sleep(_RANDOM.uniform(lo, hi))


async def _delay_click() -> None:
    """Pause before/after a button click."""
    lo = settings.BROWSER_DELAY_CLICK_MIN_MS / 1000
    hi = settings.BROWSER_DELAY_CLICK_MAX_MS / 1000
    await asyncio.sleep(_RANDOM.uniform(lo, hi))


async def _delay_extract() -> None:
    """Pause after page load to let dynamic content settle before extraction."""
    lo = settings.BROWSER_DELAY_EXTRACT_MIN_MS / 1000
    hi = settings.BROWSER_DELAY_EXTRACT_MAX_MS / 1000
    await asyncio.sleep(_RANDOM.uniform(lo, hi))


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class NaukriLoginResult:
    success: bool
    message: str
    requires_manual: bool = False


@dataclass
class NaukriApplyResult:
    job_url: str
    status: str   # "ready_for_review" | "requires_manual" | "failed"
    filled_fields: list[str]
    message: str


# ---------------------------------------------------------------------------
# Job Search — navigate Naukri, extract listings
# ---------------------------------------------------------------------------

_SEARCH_TASK_TEMPLATE = """Go to {url}.
Wait for the job listings to load (up to 10 seconds).
Extract up to {limit} job listings visible on the search results page.
For each job card extract:
  - Job title
  - Company name
  - Location (city/remote)
  - Experience required (if shown)
  - Brief description or skills (first 150 chars of the card text)
  - The URL of the job detail page (href of the title link)

Return the results as a structured list, one job per line, in EXACTLY this format:
TITLE: <title> | COMPANY: <company> | LOCATION: <location> | EXP: <exp> | URL: <url> | DESC: <description>

Do NOT click individual jobs.
Do NOT scroll or paginate.
If no results are found, return NO_RESULTS."""


def _parse_naukri_results(raw: str, query: str, location: str) -> list[JobListing]:
    """Parse the pipe-delimited extraction output into JobListing objects."""
    if not raw or "NO_RESULTS" in raw.upper():
        return []
    jobs: list[JobListing] = []
    for line in raw.strip().splitlines():
        line = line.strip()
        if "TITLE:" not in line:
            continue
        try:
            parts: dict[str, str] = {}
            for segment in line.split(" | "):
                if ":" in segment:
                    key, val = segment.split(":", 1)
                    parts[key.strip().upper()] = val.strip()
            title = parts.get("TITLE", "")
            if not title:
                continue
            job_url = parts.get("URL", "")
            # Normalise relative URLs
            if job_url and not job_url.startswith("http"):
                job_url = NAUKRI_BASE_URL + job_url
            jobs.append(JobListing(
                title=title,
                company=parts.get("COMPANY", "Unknown"),
                location=parts.get("LOCATION", location),
                description=f"{parts.get('EXP', '')} {parts.get('DESC', '')}".strip()[:2000],
                job_url=job_url or NAUKRI_BASE_URL,
                platform="naukri",
            ))
        except Exception as exc:
            logger.debug("Skipping unparsable Naukri job line: %s", exc)
    return jobs


async def search_naukri_jobs(
    llm: BaseChatModel,
    user_id: str,
    search_term: str,
    location: str = "bangalore",
    results_wanted: int = 10,
    run_id: str | None = None,
) -> list[JobListing]:
    """Search Naukri for job listings and return structured JobListing objects.

    Uses browser-use to navigate to Naukri's search results page and extract
    listings directly from the DOM.  No login required for public search.

    Structured log events are emitted for every browser action phase so
    failures can be diagnosed from logs alone (no live session needed).
    """
    from app.services.browser_control_service import run_browser_task_with_captcha_retry

    query_slug = search_term.lower().replace(" ", "-").replace(",", "")
    location_slug = location.lower().replace(" ", "-").replace(",", "")
    search_url = f"{NAUKRI_BASE_URL}/{query_slug}-jobs-in-{location_slug}"

    task = _SEARCH_TASK_TEMPLATE.format(url=search_url, limit=results_wanted)

    log_browser_action(
        run_id=run_id,
        action="navigate",
        url=search_url,
        detail=f"naukri_search: query={search_term!r} location={location!r}",
    )

    try:
        await _delay_navigate()
        with BrowserActionTimer(run_id=run_id, action="extract", url=search_url,
                                detail=f"extract_listings limit={results_wanted}"):
            raw = await run_browser_task_with_captcha_retry(
                llm, task, user_id, max_steps=12, run_id=run_id,
            )
        await _delay_extract()

        jobs = _parse_naukri_results(raw, search_term, location)
        log_browser_action(
            run_id=run_id,
            action="extract",
            url=search_url,
            detail=f"parsed {len(jobs)} jobs from naukri",
        )
        return jobs

    except Exception as exc:
        log_browser_action(run_id=run_id, action="error", url=search_url,
                           detail=f"naukri_search failed: {exc}", success=False)
        logger.error("Naukri job search failed for user %s: %s", user_id, exc)
        return []


# ---------------------------------------------------------------------------
# Login flow
# ---------------------------------------------------------------------------

_LOGIN_TASK_TEMPLATE = """Go to https://www.naukri.com/nlogin/login.
Wait for the login form to appear.
Enter email: {email}
Enter password: {password}
Click the Login button.
Wait up to 10 seconds for the page to redirect to the home/jobs page.
If redirected to a security challenge, OTP screen, or CAPTCHA, report REQUIRES_MANUAL.
If login succeeds, report LOGIN_SUCCESS.
Do not navigate away or perform any other actions."""


async def login_naukri(
    llm: BaseChatModel,
    user_id: str,
    email: str,
    password: str,
    run_id: str | None = None,
) -> NaukriLoginResult:
    """Log in to Naukri.com.  Cookies are persisted in the user's browser profile.

    Credentials are passed directly in the task prompt.  They are NOT logged,
    NOT stored in state, and NOT emitted over SSE — the task string containing
    them is consumed entirely within the browser-use agent and never surfaces
    in structured log events (BrowserActionTimer logs only action type + URL).
    """
    from app.services.browser_control_service import run_browser_task_with_captcha_retry

    log_browser_action(
        run_id=run_id, action="login",
        url="https://www.naukri.com/nlogin/login",
        detail="naukri_login: starting",
    )

    task = _LOGIN_TASK_TEMPLATE.format(email=email, password=password)

    try:
        await _delay_navigate()
        with BrowserActionTimer(run_id=run_id, action="login",
                                url="https://www.naukri.com/nlogin/login"):
            raw = await run_browser_task_with_captcha_retry(
                llm, task, user_id, max_steps=8, run_id=run_id,
            )

        result_text = (raw or "").upper()
        if "REQUIRES_MANUAL" in result_text:
            return NaukriLoginResult(success=False, message=raw, requires_manual=True)
        if "LOGIN_SUCCESS" in result_text:
            return NaukriLoginResult(success=True, message="Login completed")
        # Ambiguous — treat as success and let the apply step surface any issues
        return NaukriLoginResult(success=True, message=raw or "Login submitted")

    except Exception as exc:
        log_browser_action(run_id=run_id, action="error",
                           url="https://www.naukri.com/nlogin/login",
                           detail=f"login failed: {exc}", success=False)
        logger.error("Naukri login failed for user %s: %s", user_id, exc)
        return NaukriLoginResult(success=False, message=str(exc))


# ---------------------------------------------------------------------------
# Auto-Apply — form fill, HITL stop before submission
# ---------------------------------------------------------------------------

_APPLY_TASK_TEMPLATE = """Go to {job_url}.
Wait for the page to load.
Click the 'Apply' button to open the application.

Fill in the application form using the following applicant profile:
{applicant_profile}

Instructions:
- Fill every required field (experience years, current salary, expected salary, notice period, skills).
- If asked for a resume, use the already-uploaded profile resume — do NOT upload a new file.
- Navigate through all multi-step form pages (Next buttons).
- STOP at the final review/confirmation screen WITHOUT clicking the Submit / Apply / Confirm button.
- Report READY_FOR_REVIEW followed by a bullet list of every field you filled.
- If login is required, report REQUIRES_MANUAL.
- If OTP, CAPTCHA, payment, or account creation blocks progress, report REQUIRES_MANUAL.
- If the job has already been applied to, report ALREADY_APPLIED."""


async def apply_naukri_with_hitl(
    llm: BaseChatModel,
    user_id: str,
    job_url: str,
    applicant_profile: str,
    run_id: str | None = None,
) -> NaukriApplyResult:
    """Fill a Naukri application form and stop at the HITL checkpoint.

    NEVER submits.  Returns status="ready_for_review" when the form has been
    filled and the agent is paused at the final review screen.  The caller
    (auto_apply_pipeline) must set state["status"] = "awaiting_approval" and
    emit a checkpoint event so the user can review before submission proceeds.

    `applicant_profile` is the plaintext profile extracted from RAG context —
    it is passed to the browser-use agent so it can fill name/experience/skills
    without hallucinating.
    """
    from app.services.browser_control_service import run_browser_task_with_captcha_retry

    task = _APPLY_TASK_TEMPLATE.format(
        job_url=job_url,
        applicant_profile=applicant_profile[:1200],
    )

    log_browser_action(
        run_id=run_id, action="navigate", url=job_url,
        detail="naukri_apply: starting form fill",
    )

    try:
        await _delay_navigate()
        with BrowserActionTimer(run_id=run_id, action="fill", url=job_url,
                                detail="naukri_apply form fill"):
            raw = await run_browser_task_with_captcha_retry(
                llm, task, user_id, max_steps=25, run_id=run_id,
            )
        await _delay_extract()

        result_text = (raw or "").strip()
        upper = result_text.upper()

        if "REQUIRES_MANUAL" in upper:
            log_browser_action(run_id=run_id, action="fill", url=job_url,
                               detail="requires_manual", success=False)
            return NaukriApplyResult(
                job_url=job_url,
                status="requires_manual",
                filled_fields=[],
                message=result_text,
            )

        if "ALREADY_APPLIED" in upper:
            return NaukriApplyResult(
                job_url=job_url,
                status="requires_manual",
                filled_fields=[],
                message="Already applied to this job",
            )

        # Extract filled fields from the bullet list in the agent's output
        filled: list[str] = []
        for line in result_text.splitlines():
            line = line.strip()
            if line.startswith(("-", "•", "*")) or line.lower().startswith("filled"):
                filled.append(line.lstrip("-•* "))

        log_browser_action(
            run_id=run_id, action="fill", url=job_url,
            detail=f"ready_for_review: filled {len(filled)} fields",
        )

        # Emit HITL checkpoint event — orchestrator watches for this to set
        # state["status"] = "awaiting_approval" and pause the run.
        if run_id:
            emit(run_id, "checkpoint", {
                "type": "naukri_apply_review",
                "job_url": job_url,
                "filled_fields": filled,
                "message": "Application form filled. Review and approve to submit.",
            })

        return NaukriApplyResult(
            job_url=job_url,
            status="ready_for_review",
            filled_fields=filled,
            message=result_text,
        )

    except Exception as exc:
        log_browser_action(run_id=run_id, action="error", url=job_url,
                           detail=f"apply failed: {exc}", success=False)
        logger.error("Naukri apply failed for user %s job %s: %s", user_id, job_url, exc)
        return NaukriApplyResult(
            job_url=job_url,
            status="failed",
            filled_fields=[],
            message=str(exc),
        )
