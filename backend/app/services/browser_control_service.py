"""
browser_control_service.py — AI browser automation via browser-use.

The user's active BYOK model drives a real Chromium browser (Playwright under
the hood) to perform tasks on LinkedIn, Gmail, job boards, and any website —
just like a human would. A persistent per-user profile keeps cookies/logins
across runs. browser-use is the sole browser-control engine.
"""

import asyncio
import base64
import logging
import secrets
import time
from pathlib import Path

from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.event_bus import emit
from app.services.browser_logger import log_browser_action, save_debug_screenshot

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


def _build_bu_llm(user_id: str):
    """Build a browser-use LLM from the user's active BYOK model settings.

    Wires TokenTrackingCallback so browser-use token usage is tracked against
    the user's daily budget, consistent with all other agent LLM calls.

    If BROWSER_USE_OLLAMA_URL is set, uses that Ollama instance for navigation
    steps (cost-efficient); otherwise falls back to the user's BYOK model.
    """
    # Lazy browser_use imports — keeps the module loadable without Chromium installed
    from browser_use import ChatAnthropic, ChatGoogle, ChatOllama, ChatOpenAI  # noqa: PLC0415

    from app.core.model_router import TokenTrackingCallback
    from app.core.security import decrypt_api_key
    from app.core.sync_db import fetch_model_settings

    # Prefer Ollama for browser navigation when configured (cheap, local).
    if settings.BROWSER_USE_OLLAMA_URL:
        llm = ChatOllama(
            model=settings.BROWSER_USE_OLLAMA_MODEL,
            host=settings.BROWSER_USE_OLLAMA_URL,
        )
        # Ollama doesn't need a token callback — usage is local/free.
        return llm

    ms = fetch_model_settings(user_id)
    if not ms:
        raise RuntimeError("No active model settings configured")
    key = decrypt_api_key(ms.api_key_enc, settings.APP_SECRET_KEY)
    provider = ms.provider
    model = ms.model_name

    if provider == "anthropic":
        llm = ChatAnthropic(model=model, api_key=key)
    elif provider == "google":
        llm = ChatGoogle(model=model, api_key=key)
    elif provider == "ollama":
        llm = ChatOllama(model=model, host=ms.ollama_url)
    elif provider == "nvidia_nim":
        llm = ChatOpenAI(model=model, api_key=key, base_url="https://integrate.api.nvidia.com/v1")
    else:
        # openai + any OpenAI-compatible default
        llm = ChatOpenAI(model=model, api_key=key)

    # Wire token tracking so browser-use consumption counts against budget.
    # browser-use LLM classes accept .callbacks the same way langchain models do.
    try:
        llm.callbacks = [TokenTrackingCallback(user_id)]
    except Exception:
        pass  # not all browser-use client types expose .callbacks
    return llm


async def run_browser_task(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Run a natural-language browser task with browser-use.

    `llm` is accepted for call-site compatibility but the browser-use LLM is
    built from the user's active model settings (browser-use needs its own
    client). The agent sees the screen (vision), reasons, and acts step by step.

    Enforces BROWSER_USE_MAX_CONCURRENT_SESSIONS — callers that exceed the cap
    wait in queue rather than spawning unbounded Chromium processes.
    """
    del llm  # browser-use builds its own LLM client from model settings.

    user_dir = BROWSER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    log_browser_action(run_id=run_id, action="navigate", url="", detail=f"task_start: {task[:120]}")

    if run_id:
        emit(
            run_id,
            "browser",
            {
                "phase": "starting",
                "mode": "visible" if live_browser else "headless",
                "task": task[:240],
            },
        )

    sem = _get_semaphore()
    async with sem:
        # Lazy browser_use imports — module loads cleanly without Chromium installed
        from browser_use import Agent, Browser  # noqa: PLC0415

        bu_llm = _build_bu_llm(user_id)
        if settings.APP_ENV == "production":
            raise RuntimeError("Server browser tasks are disabled; use the browser extension")
        browser = Browser(headless=not live_browser, user_data_dir=str(user_dir))

        _last_frame_emit: dict[str, float] = {}

        async def _emit_frame(browser_state_summary, model_output, n_steps):
            if not run_id:
                return
            shot = getattr(browser_state_summary, "screenshot", None)
            current_url = getattr(browser_state_summary, "url", "") or ""
            # Structured log every step
            log_browser_action(
                run_id=run_id,
                action="navigate",
                url=current_url,
                detail=f"step={n_steps}",
            )
            if not shot:
                return
            now = time.monotonic()
            last = _last_frame_emit.get(run_id, 0.0)
            if now - last < 1.0:
                return
            _last_frame_emit[run_id] = now
            try:
                b64 = shot if isinstance(shot, str) else base64.b64encode(shot).decode("ascii")
                emit(
                    run_id,
                    "browser_frame",
                    {
                        "step": n_steps,
                        "url": current_url,
                        "title": getattr(browser_state_summary, "title", "") or "",
                        "screenshot_b64": b64,
                        "mime": "image/png",
                    },
                )
            except Exception:
                pass

        agent = Agent(
            task=task,
            llm=bu_llm,
            browser=browser,
            use_vision=True,
            register_new_step_callback=_emit_frame,
        )
        try:
            if run_id:
                emit(run_id, "browser", {"phase": "running"})
            start = time.monotonic()
            result = await agent.run(max_steps=max_steps)
            duration_ms = int((time.monotonic() - start) * 1000)
            final = result.final_result() if result else None
            if not final:
                raise RuntimeError("Browser stopped without a verified result")
            log_browser_action(
                run_id=run_id,
                action="extract",
                detail=f"completed: {str(final)[:120]}",
                duration_ms=duration_ms,
            )
            if run_id:
                emit(run_id, "browser", {"phase": "completed", "result": str(final)[:500]})
            return str(final)
        except Exception as exc:
            logger.warning("Browser task failed for run %s: %s", run_id, exc)
            log_browser_action(run_id=run_id, action="error", detail=str(exc)[:300], success=False)
            if run_id:
                emit(run_id, "browser", {"phase": "failed", "error": "Browser task failed"})
            # Screenshot-on-failure: try to grab the current page state
            try:
                _page = await browser.get_current_page()
                save_debug_screenshot(run_id=run_id, page=_page, reason="task_failure")
            except Exception:
                pass
            raise
        finally:
            try:
                await browser.kill()
            except Exception:
                pass
            _last_frame_emit.pop(run_id, None)
            if run_id:
                emit(run_id, "browser", {"phase": "closed"})


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
