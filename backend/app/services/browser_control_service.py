"""
browser_control_service.py — AI browser automation via browser-use.

The user's active BYOK model drives a real Chromium browser (Playwright under
the hood) to perform tasks on LinkedIn, Gmail, job boards, and any website —
just like a human would. A persistent per-user profile keeps cookies/logins
across runs. browser-use is the sole browser-control engine.
"""
import logging
from pathlib import Path

from browser_use import (
    Agent,
    Browser,
    ChatAnthropic,
    ChatGoogle,
    ChatOllama,
    ChatOpenAI,
)
from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.event_bus import emit

logger = logging.getLogger(__name__)

# Persistent browser data directory — cookies survive restarts
BROWSER_DATA_DIR = Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".") / ".browser_data"


def _build_bu_llm(user_id: str):
    """Build a browser-use LLM from the user's active BYOK model settings.

    browser-use uses its own LLM client classes (not LangChain), so we map the
    stored provider/model/key onto them. OpenAI-compatible providers (incl.
    NVIDIA NIM) route through ChatOpenAI with a custom base_url.
    """
    from app.core.security import decrypt_api_key
    from app.core.sync_db import fetch_model_settings

    ms = fetch_model_settings(user_id)
    if not ms:
        raise RuntimeError("No active model settings configured")
    key = decrypt_api_key(ms.api_key_enc, settings.APP_SECRET_KEY)
    provider = ms.provider
    model = ms.model_name
    if provider == "anthropic":
        return ChatAnthropic(model=model, api_key=key)
    if provider == "google":
        return ChatGoogle(model=model, api_key=key)
    if provider == "ollama":
        return ChatOllama(model=model, host=ms.ollama_url)
    if provider == "nvidia_nim":
        return ChatOpenAI(model=model, api_key=key, base_url="https://integrate.api.nvidia.com/v1")
    # openai + any OpenAI-compatible default
    return ChatOpenAI(model=model, api_key=key)


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
    """
    del llm  # browser-use builds its own LLM client from model settings.

    user_dir = BROWSER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    if run_id:
        emit(run_id, "browser", {
            "phase": "starting",
            "mode": "visible" if live_browser else "headless",
            "task": task[:240],
        })

    bu_llm = _build_bu_llm(user_id)
    browser = Browser(headless=not live_browser, user_data_dir=str(user_dir))

    async def _emit_frame(browser_state_summary, model_output, n_steps):
        # Stream the live screenshot to the UI (in-page browser view).
        if not run_id:
            return
        shot = getattr(browser_state_summary, "screenshot", None)
        if not shot:
            return
        try:
            emit(run_id, "browser_frame", {
                "step": n_steps,
                "url": getattr(browser_state_summary, "url", "") or "",
                "title": getattr(browser_state_summary, "title", "") or "",
                "screenshot": shot,
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
        result = await agent.run(max_steps=max_steps)
        final = (result.final_result() if result else None) or "Task completed"
        if run_id:
            emit(run_id, "browser", {"phase": "completed", "result": str(final)[:500]})
        return str(final)
    except Exception as exc:
        logger.warning("Browser task failed for run %s: %s", run_id, exc)
        if run_id:
            emit(run_id, "browser", {"phase": "failed", "error": "Browser task failed"})
        raise
    finally:
        try:
            await browser.kill()
        except Exception:
            pass
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
    return await run_browser_task(llm, task, user_id, max_steps=12, live_browser=live_browser, run_id=run_id)


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
    return await run_browser_task(llm, task, user_id, max_steps=10, live_browser=live_browser, run_id=run_id)


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
    return await run_browser_task(llm, task, user_id, max_steps=20, live_browser=live_browser, run_id=run_id)


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
    return await run_browser_task(llm, task, user_id, max_steps=25, live_browser=live_browser, run_id=run_id)


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
    return await run_browser_task(llm, task, user_id, max_steps=15, live_browser=live_browser, run_id=run_id)


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
    return await run_browser_task(llm, task, user_id, max_steps=12, live_browser=live_browser, run_id=run_id)
