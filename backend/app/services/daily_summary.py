"""The once-a-day email: what happened with applications and recruiter
emails, and what is waiting for the member. Skipped when nothing happened, so
it never becomes noise."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.database import AsyncSessionLocal
from app.models.db import (
    ApplicationStatusEvent,
    JobApplication,
    RecruiterOutreach,
    User,
    UserPreferences,
)


def format_summary(stats: dict) -> tuple[str, str] | None:
    """(title, body) for the email, or None when there is nothing to say."""
    lines = []
    if stats["applied"]:
        lines.append(f"Applications submitted: {stats['applied']}")
    if stats["status_changes"]:
        lines.append(f"Applications that moved forward or were answered: {stats['status_changes']}")
    if stats["emails_sent"]:
        lines.append(f"Recruiter emails sent: {stats['emails_sent']}")
    if stats["replies"]:
        lines.append(f"Recruiters who replied: {stats['replies']}")
    if stats["bounces"]:
        lines.append(f"Emails that bounced: {stats['bounces']}")
    waiting = []
    if stats["needs_approval"]:
        waiting.append(f"{stats['needs_approval']} recruiter email(s) waiting for your approval")
    if lines or waiting:
        if waiting:
            lines.append("Waiting for you: " + ", ".join(waiting))
        return "Your CareerCraft day in review", "\n".join(lines)
    return None


async def build_summary(user_id: str, now: datetime | None = None) -> dict:
    owner = uuid.UUID(user_id)
    since = (now or datetime.now(UTC)) - timedelta(hours=24)
    async with AsyncSessionLocal() as db:

        async def count(query) -> int:
            return (await db.execute(query)).scalar_one()

        return {
            "applied": await count(
                select(func.count()).where(
                    JobApplication.user_id == owner, JobApplication.applied_at > since
                )
            ),
            "status_changes": await count(
                select(func.count()).where(
                    ApplicationStatusEvent.user_id == owner,
                    ApplicationStatusEvent.new_status.is_not(None),
                    ApplicationStatusEvent.created_at > since,
                )
            ),
            "emails_sent": await count(
                select(func.count()).where(
                    RecruiterOutreach.user_id == owner, RecruiterOutreach.sent_at > since
                )
            ),
            "replies": await count(
                select(func.count()).where(
                    RecruiterOutreach.user_id == owner, RecruiterOutreach.replied_at > since
                )
            ),
            "bounces": await count(
                select(func.count()).where(
                    RecruiterOutreach.user_id == owner, RecruiterOutreach.bounced_at > since
                )
            ),
            "needs_approval": await count(
                select(func.count()).where(
                    RecruiterOutreach.user_id == owner,
                    RecruiterOutreach.state.in_(("held", "draft")),
                )
            ),
        }


async def list_summary_users() -> list[str]:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(UserPreferences.user_id)
            .join(User, User.id == UserPreferences.user_id)
            .where(
                UserPreferences.notify_daily_summary == True,  # noqa: E712
                User.deletion_scheduled_for.is_(None),
            )
        )
        return [str(user_id) for user_id in rows.scalars().all()]


async def send_summary(user_id: str) -> bool:
    """Notify one member (in-app, and email per their settings) if there is
    anything to report. Returns whether a notification was started."""
    from app.workflows.starters import start_notification

    text = format_summary(await build_summary(user_id))
    if text is None:
        return False
    await start_notification(
        user_id, type="daily_summary", title=text[0], body=text[1], link="/applications"
    )
    return True
