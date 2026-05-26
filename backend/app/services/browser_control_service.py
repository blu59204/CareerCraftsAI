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
import logging
import os
from pathlib import Path
from typing import Any

from browser_use import Agent, Browser, BrowserConfig
from langchain_core.language_models import BaseChatModel

from app.core.config import settings

logger = logging.getLogger(__name__)

# Persistent browser data directory — cookies survive restarts
BROWSER_DATA_DIR = Path(settings.BASE_DIR if hasattr(settings, "BASE_DIR") else ".") / ".browser_data"


def _get_browser_config(user_id: str) -> BrowserConfig:
    """Get browser config with persistent user data directory."""
    user_dir = BROWSER_DATA_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    return BrowserConfig(
        headless=True,
        user_data_dir=str(user_dir),
    )


async def run_browser_task(
    llm: BaseChatModel,
    task: str,
    user_id: str,
    max_steps: int = 15,
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
    config = _get_browser_config(user_id)
    browser = Browser(config=config)

    agent = Agent(
        task=task,
        llm=llm,
        browser=browser,
        max_actions_per_step=3,
    )

    try:
        result = await agent.run(max_steps=max_steps)
        return result.final_result() if result else "Task completed"
    finally:
        await browser.close()


async def linkedin_login(llm: BaseChatModel, user_id: str, email: str, password: str) -> str:
    """Login to LinkedIn. Cookies are saved for future sessions."""
    task = (
        f"Go to https://www.linkedin.com/login. "
        f"Enter email '{email}' in the email field and password '{password}' in the password field. "
        f"Click Sign in. Wait for the feed page to load. "
        f"If there's a security check, stop and report it."
    )
    return await run_browser_task(llm, task, user_id, max_steps=10)


async def linkedin_send_connection(
    llm: BaseChatModel, user_id: str, profile_url: str, note: str
) -> str:
    """Send a LinkedIn connection request with a personalized note."""
    task = (
        f"Go to {profile_url}. "
        f"Click the 'Connect' button. If there's a 'More' button, click it first to find Connect. "
        f"When the modal appears, click 'Add a note'. "
        f"Type this note: '{note[:280]}'. "
        f"Click 'Send'. Confirm the request was sent."
    )
    return await run_browser_task(llm, task, user_id, max_steps=12)


async def linkedin_send_message(
    llm: BaseChatModel, user_id: str, profile_url: str, message: str
) -> str:
    """Send a LinkedIn direct message to a 1st-degree connection."""
    task = (
        f"Go to {profile_url}. "
        f"Click the 'Message' button to open the messaging window. "
        f"Type this message: '{message}'. "
        f"Click the Send button. Confirm the message was sent."
    )
    return await run_browser_task(llm, task, user_id, max_steps=10)


async def linkedin_easy_apply(
    llm: BaseChatModel, user_id: str, job_url: str
) -> str:
    """Apply to a job via LinkedIn Easy Apply."""
    task = (
        f"Go to {job_url}. "
        f"Click the 'Easy Apply' button. "
        f"Fill in any required fields using reasonable defaults. "
        f"Upload resume if prompted (skip if no file available). "
        f"Click through all steps (Next, Review, Submit). "
        f"Confirm the application was submitted."
    )
    return await run_browser_task(llm, task, user_id, max_steps=20)


async def linkedin_update_profile(
    llm: BaseChatModel, user_id: str,
    headline: str | None = None,
    about: str | None = None,
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
    parts.append("Confirm changes were saved.")
    task = " ".join(parts)
    return await run_browser_task(llm, task, user_id, max_steps=15)


async def send_email_via_browser(
    llm: BaseChatModel, user_id: str,
    to: str, subject: str, body: str,
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
    return await run_browser_task(llm, task, user_id, max_steps=12)
