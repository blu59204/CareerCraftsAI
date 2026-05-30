"""
browser_control_service.py — AI-powered browser automation via browser-use.

Open source, self-hostable. Uses Playwright under the hood.
The LLM agent controls a real Chrome browser to perform actions on LinkedIn,
Gmail, and any website — just like a human would.

Replaces PinchTab with a fully open-source stack:
  - browser-use (AI browser agent)
  - Playwright (browser automation engine)
  - Persistent cookies (no re-login every time)
"""
import asyncio
import json
import logging
import os
from pathlib import Path
from typing import Any

try:
    from browser_use import Agent, Browser, BrowserConfig
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    Agent = Browser = BrowserConfig = None  # type: ignore
from langchain_core.language_models import BaseChatModel

from app.core.config import settings
from app.core.event_bus import emit

logger = logging.getLogger(__name__)

# Persistent browser data directory — cookies survive restarts
BROWSER_DATA_DIR = Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".") / ".browser_data"


def _get_browser_config(user_id: str, live_browser: bool = False) -> BrowserConfig:
    """Get browser config with persistent user data directory."""
    user_dir = BROWSER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return BrowserConfig(
        headless=not live_browser,
        user_data_dir=str(user_dir),
    )


async def _page_snapshot(page, limit: int = 80) -> list[dict[str, Any]]:
    """Return compact interactive DOM snapshot and tag nodes for action lookup."""
    return await page.evaluate(
        """(limit) => {
            const selectors = [
              'button', 'a[href]', 'input', 'textarea', 'select',
              '[role="button"]', '[contenteditable="true"]'
            ].join(',');
            const visible = (el) => {
              const style = window.getComputedStyle(el);
              const box = el.getBoundingClientRect();
              return style && style.visibility !== 'hidden' && style.display !== 'none'
                && box.width > 0 && box.height > 0;
            };
            return Array.from(document.querySelectorAll(selectors))
              .filter(visible)
              .slice(0, limit)
              .map((el, i) => {
                el.setAttribute('data-cc-agent-id', String(i));
                const text = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                return {
                  index: i,
                  tag: el.tagName.toLowerCase(),
                  type: el.getAttribute('type') || '',
                  role: el.getAttribute('role') || '',
                  name: el.getAttribute('name') || '',
                  label: el.getAttribute('aria-label') || el.getAttribute('placeholder') || text,
                  href: el.getAttribute('href') || '',
                  value: el.tagName.toLowerCase() === 'input' && el.getAttribute('type') === 'password'
                    ? ''
                    : (el.value || '').slice(0, 120)
                };
              });
        }""",
        limit,
    )


def _extract_json_action(text: str) -> dict[str, Any]:
    content = text.strip()
    if content.startswith("```"):
        content = "\n".join(line for line in content.splitlines() if not line.startswith("```"))
    start = content.find("{")
    end = content.rfind("}")
    if start >= 0 and end > start:
        content = content[start:end + 1]
    try:
        action = json.loads(content)
    except json.JSONDecodeError:
        return {"action": "done", "summary": text[:1000]}
    if not isinstance(action, dict):
        return {"action": "done", "summary": text[:1000]}
    return action


async def _run_playwright_agent(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int,
    live_browser: bool,
    run_id: str | None,
) -> str:
    """Fallback browser agent: selected LLM controls Playwright via JSON actions."""
    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - dependency optional in tests
        raise RuntimeError("Playwright is required for browser control") from exc

    from langchain_core.messages import HumanMessage, SystemMessage

    user_dir = BROWSER_DATA_DIR / user_id / "agent"
    user_dir.mkdir(parents=True, exist_ok=True)

    system = """You control a real browser through JSON tool actions.
Return JSON only. Valid actions:
{"action":"navigate","url":"https://..."}
{"action":"click","index":0}
{"action":"fill","index":0,"value":"text"}
{"action":"select","index":0,"value":"option text/value"}
{"action":"press","key":"Enter"}
{"action":"wait","ms":1000}
{"action":"done","summary":"what happened"}

Rules:
- Use page elements by index from OBSERVATION.
- For job applications, fill forms but stop before final Submit/Send Application unless task explicitly says submission is already approved.
- If CAPTCHA, OTP, payment, account creation, missing required user data, or final review page appears, return done with REQUIRES_MANUAL.
- Never invent credentials, degrees, work authorization, or certifications.
- Keep actions small and human-like."""

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=not live_browser,
            viewport={"width": 1366, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        history: list[str] = []
        try:
            for step in range(max_steps):
                elements = await _page_snapshot(page)
                body_text = ""
                try:
                    body_text = (await page.locator("body").inner_text(timeout=2500))[:2500]
                except Exception:
                    body_text = ""

                prompt = {
                    "task": task,
                    "step": step + 1,
                    "url": page.url,
                    "title": await page.title(),
                    "page_text": body_text,
                    "elements": elements,
                    "recent_actions": history[-5:],
                }
                if run_id:
                    emit(run_id, "browser", {
                        "phase": "observing",
                        "url": page.url,
                        "step": step + 1,
                        "elements": len(elements),
                    })

                response = llm.invoke([
                    SystemMessage(content=system),
                    HumanMessage(content=json.dumps(prompt, ensure_ascii=False)),
                ])
                action = _extract_json_action(str(response.content))
                name = str(action.get("action", "done")).lower()

                if run_id:
                    safe_action = {k: v for k, v in action.items() if k != "value"}
                    emit(run_id, "browser", {"phase": "action", "step": step + 1, "action": safe_action})

                try:
                    if name == "navigate":
                        url = str(action.get("url") or "")
                        if not url:
                            return "REQUIRES_MANUAL: agent requested navigate without URL"
                        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                        history.append(f"navigate {url}")
                    elif name == "click":
                        index = int(action.get("index"))
                        await page.locator(f'[data-cc-agent-id="{index}"]').first.click(timeout=5000)
                        history.append(f"click {index}")
                    elif name == "fill":
                        index = int(action.get("index"))
                        value = str(action.get("value") or "")
                        node = page.locator(f'[data-cc-agent-id="{index}"]').first
                        await node.fill(value, timeout=5000)
                        history.append(f"fill {index}")
                    elif name == "select":
                        index = int(action.get("index"))
                        value = str(action.get("value") or "")
                        await page.locator(f'[data-cc-agent-id="{index}"]').first.select_option(
                            label=value,
                            timeout=5000,
                        )
                        history.append(f"select {index}")
                    elif name == "press":
                        key = str(action.get("key") or "Enter")
                        await page.keyboard.press(key)
                        history.append(f"press {key}")
                    elif name == "wait":
                        await page.wait_for_timeout(int(action.get("ms") or 1000))
                        history.append("wait")
                    else:
                        return str(action.get("summary") or "Browser task completed")
                except PlaywrightTimeoutError as exc:
                    history.append(f"{name} failed: timeout")
                    logger.warning("Playwright browser action timed out: %s", exc)
                except Exception as exc:
                    history.append(f"{name} failed")
                    logger.warning("Playwright browser action failed: %s", exc)

                await page.wait_for_timeout(1200)

            return "REQUIRES_MANUAL: reached max browser steps before completion"
        finally:
            if live_browser:
                await page.wait_for_timeout(3000)
            await context.close()


async def run_browser_task(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
    live_browser: bool = False,
    run_id: str | None = None,
) -> str:
    """Run a browser task using AI agent.

    The agent controls a real browser and executes the task described in natural language.

    Args:
        llm: The LangChain LLM to use for decision-making
        task: Natural language description of what to do
        user_id: User ID for persistent browser session
        max_steps: Max browser actions before stopping

    Returns:
        Result text from the agent
    """
    if run_id:
        emit(run_id, "browser", {
            "phase": "starting",
            "mode": "visible" if live_browser else "headless",
            "task": task[:240],
        })

    if not BROWSER_USE_AVAILABLE:
        if run_id:
            emit(run_id, "browser", {"phase": "fallback", "engine": "playwright_llm"})
        final = await _run_playwright_agent(llm, task, user_id, max_steps, live_browser, run_id)
        if run_id:
            emit(run_id, "browser", {"phase": "completed", "result": final[:500]})
        return final

    config = _get_browser_config(user_id, live_browser=live_browser)
    browser = Browser(config=config)

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        max_actions_per_step=3,
    )

    try:
        if run_id:
            emit(run_id, "browser", {"phase": "running"})
        result = await agent.run(max_steps=max_steps)
        final = result.final_result() if result else "Task completed"
        if run_id:
            emit(run_id, "browser", {"phase": "completed", "result": final[:500]})
        return final
    except Exception as exc:
        logger.warning("Browser task failed for run %s: %s", run_id, exc)
        if run_id:
            emit(run_id, "browser", {"phase": "failed", "error": "Browser task failed"})
        raise
    finally:
        await browser.close()
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
