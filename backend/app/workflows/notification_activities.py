"""Activities behind NotificationWorkflow.

create_notification_activity and mark_delivery_dead_activity run on the
"notifications" task queue; send_notification_email_activity runs on the
separate, rate-limited "notifications-email" queue (see
app/notification_worker.py) so Resend's rate limit is enforced independent
of everything else these activities' worker(s) are doing.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import timedelta

from temporalio import activity
from temporalio.exceptions import ApplicationError

logger = logging.getLogger(__name__)


@activity.defn
async def create_notification_activity(params: dict) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.services.notification_service import create_notification, get_pending_email_delivery

    # Derived from the workflow, so a retry after a lost reply finds the
    # notification it already created instead of adding a second.
    notification_id = uuid.uuid5(uuid.NAMESPACE_URL, activity.info().workflow_id)

    async with AsyncSessionLocal() as db:
        from app.models.db import Notification

        if await db.get(Notification, notification_id) is not None:
            delivery = await get_pending_email_delivery(db, notification_id)
            return {
                "notification_id": str(notification_id),
                "email_delivery_id": str(delivery.id) if delivery else None,
            }
        notification = await create_notification(
            db,
            uuid.UUID(params["user_id"]),
            type=params["type"],
            title=params["title"],
            body=params.get("body"),
            link=params.get("link"),
            notification_id=notification_id,
        )
        if notification is None:
            await db.commit()
            return {"notification_id": None, "email_delivery_id": None}

        delivery = await get_pending_email_delivery(db, notification.id)
        await db.commit()
        return {
            "notification_id": str(notification.id),
            "email_delivery_id": str(delivery.id) if delivery else None,
        }


def _email_html(title: str, body: str | None, link: str | None) -> str:
    """Notification text can carry scraped job and company names, so it is
    escaped before it goes into HTML. Only app-relative links are added."""
    from html import escape

    from app.core.config import settings

    parts = [f"<p>{escape(body or title).replace(chr(10), '<br>')}</p>"]
    if link and link.startswith("/"):
        url = settings.FRONTEND_URL.rstrip("/") + link
        parts.append(f'<p><a href="{escape(url, quote=True)}">Open CareerCraft</a></p>')
    return "".join(parts)


@activity.defn
async def send_notification_email_activity(params: dict) -> dict:
    from app.core.database import AsyncSessionLocal
    from app.models.db import User
    from app.services.notification_service import mark_delivery_attempt
    from app.services.resend_service import (
        EmailRateLimited,
        EmailRejected,
        send_transactional_email,
    )

    delivery_id = uuid.UUID(params["delivery_id"])
    user_id = uuid.UUID(params["user_id"])
    title = params["title"]
    body = params.get("body")

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if user is None or not user.email:
            await mark_delivery_attempt(db, delivery_id, status="dead", error="No email on file")
            await db.commit()
            return {"status": "skipped"}

        html = _email_html(title, body, params.get("link"))
        try:
            await asyncio.to_thread(
                send_transactional_email,
                user.email,
                title,
                html,
                idempotency_key=f"notification-email/{delivery_id}",
            )
        except EmailRateLimited as exc:
            await mark_delivery_attempt(db, delivery_id, status="pending", error=str(exc))
            await db.commit()
            # Honor Resend's own Retry-After instead of Temporal's default
            # backoff — a 429 means "not yet", not "something is wrong".
            raise ApplicationError(
                str(exc), next_retry_delay=timedelta(seconds=exc.retry_after or 5)
            ) from exc
        except EmailRejected as exc:
            await mark_delivery_attempt(db, delivery_id, status="dead", error=str(exc))
            await db.commit()
            # A 4xx other than 429/409 will fail identically on retry —
            # stop immediately rather than burn the retry budget.
            raise ApplicationError(str(exc), non_retryable=True) from exc
        except Exception as exc:
            await mark_delivery_attempt(db, delivery_id, status="pending", error=str(exc))
            await db.commit()
            raise

        await mark_delivery_attempt(db, delivery_id, status="sent")
        await db.commit()

    return {"status": "sent"}


@activity.defn
async def mark_delivery_dead_activity(params: dict) -> None:
    """Called once the email activity's own retry budget is exhausted —
    the durable DLQ marker (notification_deliveries.status='dead') an
    operator can query, since Temporal keeps no such record past namespace
    retention."""
    from app.core.database import AsyncSessionLocal
    from app.services.notification_service import mark_delivery_dead

    async with AsyncSessionLocal() as db:
        await mark_delivery_dead(db, uuid.UUID(params["delivery_id"]))
        await db.commit()
