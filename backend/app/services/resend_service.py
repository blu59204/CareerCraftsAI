import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_BASE = "https://api.resend.com"
_FROM_EMAIL = "noreply@jobagent.ai"


def send_transactional_email(to: str, subject: str, html: str) -> dict:
    """Send system transactional email (alerts, notifications) via Resend.
    NOT for job outreach — that goes via Gmail MCP through user's account.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — transactional email skipped")
        return {"skipped": True}
    try:
        resp = httpx.post(
            f"{_RESEND_BASE}/emails",
            headers={
                "Authorization": f"Bearer {settings.RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            json={"from": _FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        logger.error("Resend delivery failed to %s: %s", to, exc)
        raise RuntimeError(f"Email delivery failed: {exc}") from exc
