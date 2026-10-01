"""How well the agent is doing, in the three numbers the goal is judged by:
applications that needed nothing from the member, recruiter addresses that
were verified, and emails that bounced."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.models.db import ApplicationAttempt, ExtensionTask, RecruiterOutreach

WINDOW_DAYS = 30
TARGETS = {"hands_off_rate": 0.9, "verified_email_rate": 0.5, "bounce_rate": 0.03}


def ratio(part: int, whole: int) -> float | None:
    """Share of the whole, or None when there is nothing to measure yet."""
    return round(part / whole, 3) if whole else None


def needed_member(payload: dict | None) -> bool:
    return bool((payload or {}).get("needed_you"))


async def agent_metrics(db, user_id: uuid.UUID, now: datetime | None = None) -> dict:
    since = (now or datetime.now(UTC)) - timedelta(days=WINDOW_DAYS)
    submitted = (
        (
            await db.execute(
                select(ApplicationAttempt.job_application_id).where(
                    ApplicationAttempt.user_id == user_id,
                    ApplicationAttempt.submitted_at.is_not(None),
                    ApplicationAttempt.submitted_at > since,
                )
            )
        )
        .scalars()
        .all()
    )
    applications = set(submitted)
    needed = set()
    if applications:
        payloads = await db.execute(
            select(ExtensionTask.job_application_id, ExtensionTask.payload).where(
                ExtensionTask.user_id == user_id,
                ExtensionTask.job_application_id.in_(applications),
            )
        )
        needed = {app_id for app_id, payload in payloads.all() if needed_member(payload)}
    verified = 0
    if applications:
        verified = (
            await db.execute(
                select(func.count(func.distinct(RecruiterOutreach.job_application_id))).where(
                    RecruiterOutreach.user_id == user_id,
                    RecruiterOutreach.job_application_id.in_(applications),
                    RecruiterOutreach.verdict == "valid",
                )
            )
        ).scalar_one()
    sent, bounced = (
        await db.execute(
            select(func.count(), func.count(RecruiterOutreach.bounced_at)).where(
                RecruiterOutreach.user_id == user_id,
                RecruiterOutreach.sent_at.is_not(None),
                RecruiterOutreach.sent_at > since,
            )
        )
    ).one()
    hands_off = len(applications) - len(needed)
    return {
        "window_days": WINDOW_DAYS,
        "applications": len(applications),
        "hands_off": hands_off,
        "hands_off_rate": ratio(hands_off, len(applications)),
        "verified_emails": verified,
        "verified_email_rate": ratio(verified, len(applications)),
        "emails_sent": sent,
        "emails_bounced": bounced,
        "bounce_rate": ratio(bounced, sent),
        "targets": TARGETS,
    }
