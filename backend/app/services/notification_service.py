"""In-app notifications, gated by the user's notify_* preferences.

Every caller creating a notification goes through create_notification() —
never inserts a Notification row directly — so the preference gate stays in
exactly one place. Callers that want the notification actually started
(rather than just persisted, e.g. from an activity that already has a
Notification-worthy event) should go through
app.workflows.starters.start_notification instead, which runs
NotificationWorkflow — this keeps notification creation, and any email
dispatch, out of the caller's own Temporal retry scope so a notification
failure can never retry the caller's real work (see NotificationWorkflow).
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import Notification, NotificationDelivery, UserPreferences

logger = logging.getLogger(__name__)

# type -> which UserPreferences boolean must be true for this notification
# to be created at all. A type with no entry is always created (never
# preference-gated) — reserved for account/security notices, not used yet.
_PREFERENCE_GATE: dict[str, str] = {
    "job_matches": "notify_agent_alerts",
    "followup_ready": "notify_followup_reminders",
    "application_update": "notify_agent_alerts",
    "daily_summary": "notify_daily_summary",
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
    notification_id: uuid.UUID | None = None,
) -> Notification | None:
    """Create an in-app notification, and a pending email NotificationDelivery
    row alongside it if the user's notify_email preference and this type's
    own preference are both on.

    Returns None (and creates nothing) when this type's gating preference is
    explicitly off. Missing preferences (new user, never saved any) default
    to the on-by-default behavior the settings page itself ships with.

    This function only persists rows — it never sends email itself. The
    email delivery row it creates is picked up and actually sent by
    send_notification_email_activity, driven by NotificationWorkflow.
    """
    prefs = await _get_preferences(db, user_id)
    gate = _PREFERENCE_GATE.get(type)
    if gate is not None and prefs is not None and getattr(prefs, gate) is False:
        return None

    notification = Notification(
        id=notification_id or uuid.uuid4(),
        user_id=user_id,
        type=type,
        title=title,
        body=body,
        link=link,
    )
    db.add(notification)
    await db.flush()

    should_email = prefs is None or prefs.notify_email is not False
    if should_email:
        db.add(
            NotificationDelivery(
                id=uuid.uuid4(),
                notification_id=notification.id,
                channel="email",
                status="pending",
                idempotency_key=f"notification-email/{notification.id}",
            )
        )
        await db.flush()

    return notification


async def get_pending_email_delivery(
    db: AsyncSession, notification_id: uuid.UUID
) -> NotificationDelivery | None:
    result = await db.execute(
        select(NotificationDelivery).where(
            NotificationDelivery.notification_id == notification_id,
            NotificationDelivery.channel == "email",
            NotificationDelivery.status == "pending",
        )
    )
    return result.scalar_one_or_none()


async def mark_delivery_attempt(
    db: AsyncSession,
    delivery_id: uuid.UUID,
    status: str,
    error: str | None = None,
) -> None:
    """Record one delivery attempt. status is the delivery's new state
    ("sent", "pending" for a retryable failure, or "dead" for a terminal
    one) — the caller (the activity) decides which, this just persists it."""
    delivery = await db.get(NotificationDelivery, delivery_id)
    if delivery is None:
        return
    delivery.attempts += 1
    delivery.status = status
    delivery.last_error = error


async def mark_delivery_dead(db: AsyncSession, delivery_id: uuid.UUID) -> None:
    """Called once Temporal's own retry budget for this delivery's activity
    is fully exhausted — the durable DLQ marker for operator triage."""
    delivery = await db.get(NotificationDelivery, delivery_id)
    if delivery is None or delivery.status == "sent":
        return
    delivery.status = "dead"


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
