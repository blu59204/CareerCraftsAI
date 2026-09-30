import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

_RESEND_BASE = "https://api.resend.com"


class EmailDeliveryError(RuntimeError):
    """Base for any failed Resend send. Retryable unless a subclass says
    otherwise — callers that care about the distinction should catch the
    specific subclasses below, not this base class."""


class EmailRateLimited(EmailDeliveryError):
    """429 from Resend (default cap: 10 req/s/team), or a 409 idempotency
    conflict — both mean "try again shortly", never "this request is bad"."""

    def __init__(self, retry_after: float | None = None):
        super().__init__("Resend rate limit exceeded")
        self.retry_after = retry_after


class EmailRejected(EmailDeliveryError):
    """4xx other than 429/409 — a bad request, invalid recipient, or auth
    failure. Retrying with the same payload will fail the same way."""


def send_transactional_email(
    to: str, subject: str, html: str, idempotency_key: str | None = None
) -> dict:
    """Send system transactional email (alerts, notifications) via Resend.
    NOT for job outreach — that goes via Gmail MCP through user's account.

    idempotency_key, when set, is sent as Resend's Idempotency-Key header:
    a retried send with the same key returns the original result instead of
    sending twice (valid 24h). Pass a stable per-delivery key, not a
    per-attempt one.
    """
    if not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not configured — transactional email skipped")
        return {"skipped": True}

    headers = {
        "Authorization": f"Bearer {settings.RESEND_API_KEY}",
        "Content-Type": "application/json",
    }
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key

    try:
        resp = httpx.post(
            f"{_RESEND_BASE}/emails",
            headers=headers,
            json={"from": settings.RESEND_FROM_EMAIL, "to": [to], "subject": subject, "html": html},
            timeout=10,
        )
    except httpx.HTTPError as exc:
        logger.error("Resend request failed to %s: %s", to, exc)
        raise EmailDeliveryError("Email delivery request failed") from exc

    if resp.status_code == 429:
        retry_after = _parse_retry_after(resp.headers.get("Retry-After"))
        logger.warning("Resend rate limit hit sending to %s (retry_after=%s)", to, retry_after)
        raise EmailRateLimited(retry_after)

    if resp.status_code == 409:
        # A concurrent_idempotent_requests conflict means the same delivery
        # is already in flight; invalid_idempotent_request means the key was
        # reused with a different payload (shouldn't happen — each delivery
        # gets its own key). Either way, retrying later is safe.
        logger.warning("Resend idempotency conflict sending to %s: %s", to, resp.text)
        raise EmailRateLimited(retry_after=5)

    if 400 <= resp.status_code < 500:
        logger.error("Resend rejected email to %s (%s): %s", to, resp.status_code, resp.text)
        raise EmailRejected(f"Resend rejected the request ({resp.status_code})")

    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.error("Resend delivery failed to %s: %s", to, exc)
        raise EmailDeliveryError("Email delivery failed") from exc

    return resp.json()


def _parse_retry_after(value: str | None) -> float | None:
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None
