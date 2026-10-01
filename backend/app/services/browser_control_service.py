"""Browser compatibility helpers. Server task execution is retired.

Application filling and submission use the paired extension with mandatory
review. LinkedIn login retains its explicit credential-login helper.
"""

import asyncio
import logging
import secrets
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.event_bus import emit

logger = logging.getLogger(__name__)
_RANDOM = secrets.SystemRandom()

# Persistent browser data directory — cookies survive restarts
BROWSER_DATA_DIR = (
    Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".") / ".browser_data"
)

# browser_use is imported lazily inside functions so the module loads cleanly
# in test environments that don't have Chromium/Playwright installed.
# All production code paths go through _build_bu_llm() / run_browser_task()
# which perform the import at call time.

# ── Session concurrency cap ──────────────────────────────────────────────────
_session_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    global _session_semaphore
    if _session_semaphore is None:
        _session_semaphore = asyncio.Semaphore(settings.BROWSER_USE_MAX_CONCURRENT_SESSIONS)
    return _session_semaphore


# ---------------------------------------------------------------------------
# Site challenges stop automation; only the user may resolve them.
# Strings that look like a CAPTCHA / WAF / anti-bot block page.
_CAPTCHA_MARKERS: tuple[str, ...] = (
    "captcha",
    "unusual traffic",
    "are you a human",
    "verify you are",
    "access denied",
    "rate limit",
    "too many requests",
    "bot detection",
    "please complete the security check",
    "are you a robot",
    "checking your browser",
    "cloudflare",
    "perimeterx",
    "datadome",
    "incapsula",
    "distil",
    "akamai",
    "just a moment",
)


class CaptchaBlocked(RuntimeError):
    """A site challenge requires manual intervention; automation stops."""


def _looks_like_captcha(text: str) -> bool:
    return any(marker in (text or "").lower() for marker in _CAPTCHA_MARKERS)


async def run_browser_task_with_captcha_retry(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Compatibility entry point: one attempt, stop on challenge, never evade it."""
    result = await run_browser_task(
        llm, task, user_id, max_steps=max_steps, live_browser=live_browser, run_id=run_id
    )
    if _looks_like_captcha(result):
        raise CaptchaBlocked("Site challenge requires manual intervention")
    return result


async def run_browser_task(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Server browser execution is retired; never bypass the paired extension."""
    raise RuntimeError("Use a public job connector or the paired browser extension")


async def linkedin_login(
    llm: BaseChatModel,
    user_id: str,
    email: str,
    password: str,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Login to LinkedIn. Cookies are saved for future sessions.

    Credentials are filled directly through Playwright so they never enter an
    LLM prompt, SSE event, or provider-side trace.
    """
    del llm  # Login must not route credentials through an LLM.

    if run_id:
        emit(
            run_id,
            "browser",
            {
                "phase": "login_starting",
                "mode": "visible" if live_browser else "headless",
                "site": "linkedin",
            },
        )

    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - dependency is optional in some test envs
        raise RuntimeError("Playwright is required for secure LinkedIn login") from exc

    user_dir = BROWSER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=not live_browser,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await page.fill('input[name="session_key"], input#username', email)
            await page.fill('input[name="session_password"], input#password', password)
            await page.click('button[type="submit"]')
            try:
                await page.wait_for_url("**/feed/**", timeout=15000)
                status = "Login completed"
            except PlaywrightTimeoutError:
                title = (await page.title()).lower()
                if "checkpoint" in page.url or "security" in title:
                    status = "LinkedIn security checkpoint requires manual review"
                else:
                    status = "Login submitted; verify browser state before continuing"
            if run_id:
                emit(run_id, "browser", {"phase": "login_completed", "site": "linkedin"})
            return status
        finally:
            await context.close()


async def linkedin_send_connection(
    llm: BaseChatModel,
    user_id: str,
    profile_url: str,
    note: str,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Send a LinkedIn connection request with a personalized note."""
    task = (
        f"Go to {profile_url}. "
        f"Click the 'Connect' button. If there's a 'More' button, click it first to find Connect. "
        f"When the modal appears, click 'Add a note'. "
        f"Type this note: '{note[:280]}'. "
        f"Click 'Send'. Confirm the request was sent."
    )
    return await run_browser_task_with_captcha_retry(
        llm, task, user_id, max_steps=12, live_browser=live_browser, run_id=run_id
    )


async def apply_to_job(
    llm: BaseChatModel,
    user_id: str,
    job_url: str,
    applicant_info: str,
    submit: bool = False,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Autonomously fill any job application form via the browser agent.

    submit=False: fill through to the final review screen and stop (READY_FOR_REVIEW).
    submit=True: fill and click the final Submit/Apply button (SUBMITTED).
    """
    final = (
        "Click the final Submit/Apply button to submit the application, then confirm SUBMITTED."
        if submit
        else "Stop before the final Submit/Apply button and report READY_FOR_REVIEW with what was filled."
    )
    task = (
        f"Go to {job_url}. Click the Apply / Easy Apply / Apply now button. "
        f"Fill every required field of the application form using this applicant profile:\n{applicant_info[:1500]}\n"
        f"Use reasonable, truthful answers; leave optional fields blank if unknown. "
        f"Upload a resume only if a file picker requires it and a file is available, otherwise skip. "
        f"Proceed through multi-step forms. {final} "
        f"If login, CAPTCHA, OTP, payment, account creation, or missing required personal data blocks "
        f"progress, stop and report REQUIRES_MANUAL."
    )
    return await run_browser_task_with_captcha_retry(
        llm, task, user_id, max_steps=25, live_browser=live_browser, run_id=run_id
    )
