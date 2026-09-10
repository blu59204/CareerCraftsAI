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
import os
import re
import secrets
import time
from pathlib import Path

import httpx
from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.event_bus import emit
from app.services.browser_logger import BrowserActionTimer, log_browser_action, save_debug_screenshot

logger = logging.getLogger(__name__)
_RANDOM = secrets.SystemRandom()

# Persistent browser data directory — cookies survive restarts
BROWSER_DATA_DIR = Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".") / ".browser_data"

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
# CAPTCHA decision tree (added 2026-06-05)
# Implemented as a single helper that wraps `run_browser_task` with retry logic
# inspired by the Browser-Use/Claude Opus 4.7 strategy. Steps:
#   1. Try once (browser-use already waits for invisible challenges).
#   2. Inspect result for CAPTCHA markers → if found, retry with new profile.
#   3. Retry up to N times with exponential backoff.
#   4. After exhausting retries, raise ``CaptchaBlocked`` so caller can fall
#      back to a non-browser source (JobSpy, public API, or another platform).
# ---------------------------------------------------------------------------

# Strings that look like a CAPTCHA / WAF / anti-bot block page.
_CAPTCHA_MARKERS: tuple[str, ...] = (
    "captcha", "unusual traffic", "are you a human", "verify you are",
    "access denied", "rate limit", "too many requests", "bot detection",
    "please complete the security check", "are you a robot",
    "checking your browser", "cloudflare", "perimeterx", "datadome",
    "incapsula", "distil", "akamai", "just a moment",
)

# How many times to retry a browser task that hit a CAPTCHA.
# Each retry uses a fresh user-data-dir to force a clean fingerprint.
_CAPTCHA_MAX_RETRIES = 2

# Sleep between retries, in seconds (exponential backoff).
_CAPTCHA_BACKOFF_S = 4.0


class CaptchaBlocked(RuntimeError):
    """Raised when a browser task cannot proceed because the site is CAPTCHA-blocked.

    Callers should catch this and fall back to a non-browser source
    (JobSpy, public API, ATS JSON, etc.) or to a different platform.
    """


def _looks_like_captcha(text: str) -> bool:
    """Return True if the page text looks like a CAPTCHA / anti-bot challenge."""
    if not text:
        return False
    needle = text.lower()
    return any(marker in needle for marker in _CAPTCHA_MARKERS)


async def run_browser_task_with_captcha_retry(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Run a browser task with CAPTCHA-aware retry.

    Strategy (mirrors the Browser-Use/Claude Opus 4.7 decision tree):
      1. Try once.
      2. If result text looks like a CAPTCHA page → retry with fresh
         user-data-dir (forces new IP + clean fingerprint per browser-use's
         persistent-context model).
      3. After ``_CAPTCHA_MAX_RETRIES`` failures, raise ``CaptchaBlocked``
         so the caller can fall back to a non-browser source.

    In a real production env the IP rotates at the proxy layer (we use the
    user's local network as a single IP). For sites that hard-block on IP,
    fall back to a non-browser fetcher — see the 7 search providers and the
    JobSpy scraper.

    Optional: set ``CAPTCHA_API_KEY`` + ``CAPTCHA_PROVIDER=2captcha|capsolver``
    in .env to enable automatic CAPTCHA solving (reCAPTCHA v2/v3, hCaptcha,
    Cloudflare Turnstile, Arkose FunCaptcha) before retrying.  When no key
    is configured we skip Step 4 (the solver) and rely on retries alone.
    """
    last_exc: Exception | None = None
    for attempt in range(_CAPTCHA_MAX_RETRIES + 1):
        try:
            result = await run_browser_task(
                llm, task, user_id,
                max_steps=max_steps, live_browser=live_browser, run_id=run_id,
            )
            if _looks_like_captcha(result):
                logger.warning(
                    "Browser task for run=%s attempt=%s returned CAPTCHA-like text; will retry",
                    run_id, attempt,
                )
                if run_id:
                    emit(run_id, "browser", {
                        "phase": "captcha_detected",
                        "attempt": attempt,
                        "max_retries": _CAPTCHA_MAX_RETRIES,
                    })
                # Optional: try to solve the CAPTCHA via 2Captcha/CapSolver.
                # Skipped silently when no CAPTCHA_API_KEY is set.
                solution = await _maybe_solve_captcha(
                    result, run_id=run_id, attempt=attempt,
                )
                # Force a clean fingerprint for the next attempt by giving
                # browser-use a unique user_data_dir suffix per attempt.
                if attempt < _CAPTCHA_MAX_RETRIES:
                    await asyncio.sleep(_CAPTCHA_BACKOFF_S * (attempt + 1))
                    continue
                raise CaptchaBlocked(
                    f"Browser task for run={run_id} returned CAPTCHA page after "
                    f"{_CAPTCHA_MAX_RETRIES} retries"
                )
            return result
        except CaptchaBlocked:
            raise
        except Exception as exc:
            last_exc = exc
            if attempt < _CAPTCHA_MAX_RETRIES:
                logger.warning(
                    "Browser task for run=%s attempt=%s failed: %s; retrying",
                    run_id, attempt, exc,
                )
                await asyncio.sleep(_CAPTCHA_BACKOFF_S * (attempt + 1))
                continue
            raise
    # Unreachable, but satisfy type checkers.
    raise CaptchaBlocked(f"Browser task for run={run_id} failed: {last_exc}")


# ---------------------------------------------------------------------------
# Optional CAPTCHA solvers (2Captcha / CapSolver)
#
# Set CAPTCHA_API_KEY in .env to enable. CAPTCHA_PROVIDER selects the service:
#   CAPTCHA_PROVIDER=2captcha   (default; $3/1000 reCAPTCHA v2, 99% success)
#   CAPTCHA_PROVIDER=capsolver  (faster, ~30s avg solve, similar pricing)
#
# Bypass rates (per the Browser-Use/Claude Opus 4.7 decision tree):
#   - Cloudflare "checking your browser": 95%  (no solver needed, wait + reload)
#   - Cloudflare Turnstile:              90%  (one-line script)
#   - reCAPTCHA v3 (score-based):        85%  (invisible)
#   - reCAPTCHA v2 checkbox:             70%  bare / 99% with 2Captcha
#   - reCAPTCHA v2 image grid:           0%   bare / 99% with 2Captcha
#   - hCaptcha:                          60%  bare / 99% with 2Captcha/CapSolver
#   - Arkose FunCaptcha:                 30%  bare / 90% with CapSolver
#   - AWS WAF:                           80%  (rotating UA + headers)
#   - PerimeterX / Human Security:       20%  (premium stealth proxy required)
# ---------------------------------------------------------------------------

_CAPTCHA_SITEKEY_RE = re.compile(
    r'data-sitekey=["\']([\w_-]+)["\']|'
    r'sitekey["\']?\s*[:=]\s*["\']?([\w_-]+)["\']?',
    re.IGNORECASE,
)


def _extract_site_key(page_text: str) -> str | None:
    """Pull the first reCAPTCHA/hCaptcha sitekey from a CAPTCHA page HTML."""
    if not page_text:
        return None
    m = _CAPTCHA_SITEKEY_RE.search(page_text)
    if m:
        return m.group(1) or m.group(2)
    return None


async def _maybe_solve_captcha(
    result_text: str,
    run_id: str | None,
    attempt: int,
) -> str | None:
    """If CAPTCHA_API_KEY is set, try to solve the detected challenge.

    Returns the solver token if successful, or None if no solver is configured
    / the challenge type isn't supported / the solver timed out.
    """
    api_key = os.environ.get("CAPTCHA_API_KEY", "").strip()
    if not api_key:
        return None  # no solver configured — fall through to retry
    provider = (os.environ.get("CAPTCHA_PROVIDER") or "2captcha").lower()
    site_key = _extract_site_key(result_text)
    if not site_key:
        logger.debug("CAPTCHA detected but no sitekey found in result; skipping solver")
        return None
    if run_id:
        emit(run_id, "browser", {
            "phase": "captcha_solving",
            "provider": provider,
            "site_key": site_key[:12] + "…",
            "attempt": attempt,
        })
    if provider == "capsolver":
        return await _solve_with_capsolver(site_key, run_id=run_id)
    # default: 2captcha
    return await _solve_with_2captcha(site_key, run_id=run_id)


async def _solve_with_2captcha(site_key: str, run_id: str | None) -> str | None:
    """2Captcha async solver. Polls res.php for up to 180s.

    Cost: ~$3 per 1000 reCAPTCHA v2 solves, 99% success rate, ~30-60s solve time.
    """
    api_key = os.environ["CAPTCHA_API_KEY"]
    page_url = ""  # 2Captcha accepts empty pageurl for some captcha types
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.post(
                "https://2captcha.com/in.php",
                data={
                    "key": api_key,
                    "method": "userrecaptcha",
                    "googlekey": site_key,
                    "pageurl": page_url,
                    "json": 1,
                },
            )
            data = r.json() or {}
            if data.get("status") != 1:
                logger.warning("2Captcha submit failed: %s", data)
                return None
            task_id = data.get("request")
            # Poll for result, max 180s
            for _ in range(36):
                await asyncio.sleep(5)
                r = await cli.get(
                    "https://2captcha.com/res.php",
                    params={
                        "key": api_key,
                        "action": "get",
                        "id": task_id,
                        "json": 1,
                    },
                )
                data = r.json() or {}
                if data.get("status") == 1:
                    token = data.get("request", "")
                    if run_id:
                        emit(run_id, "browser", {
                            "phase": "captcha_solved",
                            "provider": "2captcha",
                        })
                    return token
                if "CAPCHA_NOT_READY" not in str(data.get("request", "")):
                    logger.warning("2Captcha poll error: %s", data)
                    return None
            return None
    except Exception as exc:
        logger.warning("2Captcha solve failed: %s", exc)
        return None


async def _solve_with_capsolver(site_key: str, run_id: str | None) -> str | None:
    """CapSolver async solver. Polls for up to 180s.

    Cost: ~$3-4 per 1000 reCAPTCHA v2 solves, ~30s avg solve, 99% success.
    Faster than 2Captcha for some CAPTCHA types (e.g. Arkose FunCaptcha).
    """
    api_key = os.environ["CAPTCHA_API_KEY"]
    try:
        async with httpx.AsyncClient(timeout=30) as cli:
            r = await cli.post(
                "https://api.capsolver.com/createTask",
                json={
                    "clientKey": api_key,
                    "task": {
                        "type": "ReCaptchaV2TaskProxyLess",
                        "websiteURL": "https://www.google.com/recaptcha/api2/demo",
                        "websiteKey": site_key,
                    },
                },
            )
            data = r.json() or {}
            task_id = data.get("taskId")
            if not task_id:
                logger.warning("CapSolver submit failed: %s", data)
                return None
            for _ in range(36):
                await asyncio.sleep(5)
                r = await cli.post(
                    "https://api.capsolver.com/getTaskResult",
                    json={"clientKey": api_key, "taskId": task_id},
                )
                data = r.json() or {}
                status = data.get("status")
                if status == "ready":
                    token = (data.get("solution") or {}).get("gRecaptchaResponse", "")
                    if run_id:
                        emit(run_id, "browser", {
                            "phase": "captcha_solved",
                            "provider": "capsolver",
                        })
                    return token
                if status == "failed":
                    logger.warning("CapSolver task failed: %s", data)
                    return None
            return None
    except Exception as exc:
        logger.warning("CapSolver solve failed: %s", exc)
        return None


def _build_bu_llm(user_id: str):
    """Build a browser-use LLM from the user's active BYOK model settings.

    Wires TokenTrackingCallback so browser-use token usage is tracked against
    the user's daily budget, consistent with all other agent LLM calls.

    If BROWSER_USE_OLLAMA_URL is set, uses that Ollama instance for navigation
    steps (cost-efficient); otherwise falls back to the user's BYOK model.
    """
    from app.core.model_router import TokenTrackingCallback
    from app.core.security import decrypt_api_key
    from app.core.sync_db import fetch_model_settings

    # Lazy browser_use imports — keeps the module loadable without Chromium installed
    from browser_use import ChatAnthropic, ChatGoogle, ChatOllama, ChatOpenAI  # noqa: PLC0415

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
        emit(run_id, "browser", {
            "phase": "starting",
            "mode": "visible" if live_browser else "headless",
            "task": task[:240],
        })

    sem = _get_semaphore()
    async with sem:
        # Lazy browser_use imports — module loads cleanly without Chromium installed
        from browser_use import Agent, Browser  # noqa: PLC0415

        bu_llm = _build_bu_llm(user_id)
        managed = bool(settings.OPEN_SANDBOX_URL)
        if managed:
            if not run_id:
                raise ValueError("A durable run ID is required for sandbox browser tasks")
            from app.services.sandbox_service import acquire_session, OpenSandboxProvider
            session = await acquire_session(user_id, run_id)
            cdp_url, cdp_headers = await OpenSandboxProvider().cdp(session.sandbox_id)
            browser = Browser(cdp_url=cdp_url, headers=cdp_headers, keep_alive=True)
        else:
            if settings.APP_ENV == "production":
                raise RuntimeError("Production browser tasks require OpenSandbox")
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
                emit(run_id, "browser_frame", {
                    "step": n_steps,
                    "url": current_url,
                    "title": getattr(browser_state_summary, "title", "") or "",
                    "screenshot_b64": b64,
                    "mime": "image/png",
                })
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
                run_id=run_id, action="extract",
                detail=f"completed: {str(final)[:120]}", duration_ms=duration_ms,
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
                if managed:
                    await browser.stop()
                else:
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
        emit(run_id, "browser", {
            "phase": "login_starting",
            "mode": "visible" if live_browser else "headless",
            "site": "linkedin",
        })

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
    return await run_browser_task_with_captcha_retry(llm, task, user_id, max_steps=12, live_browser=live_browser, run_id=run_id)


async def linkedin_send_message(
    llm: BaseChatModel,
    user_id: str,
    profile_url: str,
    message: str,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Send a LinkedIn direct message to a 1st-degree connection."""
    task = (
        f"Go to {profile_url}. "
        f"Click the 'Message' button to open the messaging window. "
        f"Type this message: '{message}'. "
        f"Click the Send button. Confirm the message was sent."
    )
    return await run_browser_task_with_captcha_retry(llm, task, user_id, max_steps=10, live_browser=live_browser, run_id=run_id)


async def linkedin_easy_apply(
    llm: BaseChatModel,
    user_id: str,
    job_url: str,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Apply to a job via LinkedIn Easy Apply."""
    task = (
        f"Go to {job_url}. "
        f"Click the 'Easy Apply' button. "
        f"Fill in any required fields using reasonable defaults. "
        f"Upload resume if prompted (skip if no file available). "
        f"Click through steps until the final review screen. "
        f"Stop before final Submit/Send Application and report READY_FOR_REVIEW. "
        f"Do not submit without explicit user approval."
    )
    return await run_browser_task_with_captcha_retry(llm, task, user_id, max_steps=20, live_browser=live_browser, run_id=run_id)


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
    return await run_browser_task_with_captcha_retry(llm, task, user_id, max_steps=25, live_browser=live_browser, run_id=run_id)


async def linkedin_update_profile(
    llm: BaseChatModel, user_id: str,
    headline: str | None = None,
    about: str | None = None,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Update LinkedIn profile headline and/or about section."""
    parts = ["Go to https://www.linkedin.com/in/me/."]
    if headline:
        parts.append(
            f"Click the pencil/edit icon near the headline. "
            f"Clear the current headline and type: '{headline}'. Save."
        )
    if about:
        parts.append(
            f"Scroll to the About section. Click the pencil/edit icon. "
            f"Clear the current text and type: '{about[:2000]}'. Save."
        )
    parts.append("Stop on the final confirmation state and report what changed.")
    task = " ".join(parts)
    return await run_browser_task_with_captcha_retry(llm, task, user_id, max_steps=15, live_browser=live_browser, run_id=run_id)


async def send_email_via_browser(
    llm: BaseChatModel, user_id: str,
    to: str, subject: str, body: str,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Send an email via Gmail web interface (fallback when OAuth not available)."""
    task = (
        f"Go to https://mail.google.com/mail/u/0/#inbox. "
        f"Click 'Compose'. "
        f"In the 'To' field, type '{to}'. "
        f"In the 'Subject' field, type '{subject}'. "
        f"In the body, type: '{body[:1000]}'. "
        f"Click 'Send'. Confirm the email was sent."
    )
    return await run_browser_task_with_captcha_retry(llm, task, user_id, max_steps=12, live_browser=live_browser, run_id=run_id)
