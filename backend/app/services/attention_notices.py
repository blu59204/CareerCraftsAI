"""Tells the member when an application is stuck on something only they can do.

Applications pause for a human on screening questions the agent cannot
answer, login or one-time-code walls, and low-confidence reviews. Waiting
silently loses the application, so each new pause emails and notifies the
member with a link back to it.
"""

from __future__ import annotations

import logging
import uuid

logger = logging.getLogger(__name__)

# stage -> what the member has to do
_NEEDS = {
    "needs_input": "answer a few questions the agent could not",
    "login_required": "sign in to the job site (login, CAPTCHA or one-time code)",
}


def attention_text(stage: str, company: str | None, role: str | None) -> tuple[str, str] | None:
    """(title, body) for a stage that needs the member, else None."""
    need = _NEEDS.get(stage)
    if need is None:
        return None
    where = f"{role} at {company}" if company and role else (company or "your application")
    return f"Your application to {where} is waiting for you", f"Please {need}, then it continues."


async def notify_needs_attention(
    user_id: uuid.UUID | str, stage: str, previous_stage: str | None, payload: dict | None
) -> bool:
    """Send one notice when a task newly enters a stage that needs the member.
    Best effort: a notification failure never blocks the application."""
    if stage == previous_stage:
        return False
    payload = payload or {}
    text = attention_text(stage, payload.get("company"), payload.get("role"))
    if text is None:
        return False
    from app.workflows.starters import start_notification

    try:
        await start_notification(
            user_id,
            type="application_needs_you",
            title=text[0],
            body=text[1],
            link="/applications",
        )
    except Exception:
        logger.warning("Could not start needs-attention notification", exc_info=True)
        return False
    return True
