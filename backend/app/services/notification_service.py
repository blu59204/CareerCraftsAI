"""In-app notifications, gated by the user's notify_* preferences.

Every caller creating a notification goes through create_notification() —
never inserts a Notification row directly — so the preference gate and
optional email dispatch stay in exactly one place.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.background import spawn_background
from app.models.db import Notification, User, UserPreferences

logger = logging.getLogger(__name__)

# type -> which UserPreferences boolean must be true for this notification
# to be created at all. A type with no entry is always created (never
# preference-gated) — reserved for account/security notices, not used yet.
_PREFERENCE_GATE: dict[str, str] = {
    "job_matches": "notify_agent_alerts",
    "followup_ready": "notify_followup_reminders",
}


async def _get_preferences(db: AsyncSession, user_id: uuid.UUID) -> UserPreferences | None:
    result = await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    return result.scalar_one_or_none()


async def create_notification(
    db: AsyncSession,
    user_id: uuid.UUID,
    type: str,
    title: str,
    body: str | None = None,
    link: str | None = None,
) -> Notification | None:
    """Create an in-app notification, and email it too if the user's
    notify_email preference and this type's own preference are both on.

    Returns None (and creates nothing) when this type's gating preference is
    explicitly off. Missing preferences (new user, never saved any) default
    to the on-by-default behavior the settings page itself ships with.
    """
    prefs = await _get_preferences(db, user_id)
    gate = _PREFERENCE_GATE.get(type)
    if gate is not None and prefs is not None and getattr(prefs, gate) is False:
        return None

    notification = Notification(
        id=uuid.uuid4(), user_id=user_id, type=type, title=title, body=body, link=link
    )
    db.add(notification)
    await db.flush()

    should_email = prefs is None or prefs.notify_email is not False
    if should_email:
        spawn_background(_send_email_best_effort(user_id, title, body))

    return notification


async def _send_email_best_effort(user_id: uuid.UUID, title: str, body: str | None) -> None:
    """Fire-and-forget: a failed email must never fail notification creation
    or roll back the caller's transaction. Runs in its own DB session since
    the caller's session may already be committed/closed by the time this
    scheduled task actually runs."""
    from app.core.database import AsyncSessionLocal
    from app.services.resend_service import send_transactional_email

    try:
        async with AsyncSessionLocal() as session:
            user = await session.get(User, user_id)
            if user is None or not user.email:
                return
            html = f"<p>{body}</p>" if body else f"<p>{title}</p>"
            await asyncio.to_thread(send_transactional_email, user.email, title, html)
    except Exception as exc:
        logger.warning("Notification email to user %s failed: %s", user_id, exc)


async def list_notifications(
    db: AsyncSession, user_id: uuid.UUID, limit: int = 30
) -> tuple[list[Notification], int]:
    notifications = (
        (
            await db.execute(
                select(Notification)
                .where(Notification.user_id == user_id)
                .order_by(Notification.created_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    unread_count = await count_unread(db, user_id)
    return list(notifications), unread_count


async def count_unread(db: AsyncSession, user_id: uuid.UUID) -> int:
    result = await db.execute(
        select(func.count())
        .select_from(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
    )
    return result.scalar_one()


async def mark_read(db: AsyncSession, user_id: uuid.UUID, notification_id: uuid.UUID) -> bool:
    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user_id
        )
    )
    notification = result.scalar_one_or_none()
    if notification is None:
        return False
    if notification.read_at is None:
        notification.read_at = datetime.now(UTC)
    return True


async def mark_all_read(db: AsyncSession, user_id: uuid.UUID) -> None:
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user_id, Notification.read_at.is_(None))
        .values(read_at=datetime.now(UTC))
    )
