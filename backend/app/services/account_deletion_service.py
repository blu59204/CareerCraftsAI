"""Hard-deletes accounts whose 15-day deletion grace period has elapsed.

Requesting deletion (see app.api.v1.users) never removes anything itself —
it only stamps deletion_scheduled_for. This module is the other half: a
periodic sweep (called from the maintenance activity) that finds accounts
past that date and actually deletes them.
"""

import logging
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import User

logger = logging.getLogger(__name__)


async def reap_expired_account_deletions(db: AsyncSession) -> int:
    """Hard-delete every account whose grace period has passed. Returns the
    count removed. Callers are expected to commit the session afterward."""
    from app.core.supabase_auth import delete_clerk_user

    now = datetime.now(UTC)
    users = (
        (
            await db.execute(
                select(User).where(
                    User.deletion_scheduled_for.is_not(None),
                    User.deletion_scheduled_for <= now,
                )
            )
        )
        .scalars()
        .all()
    )

    removed = 0
    for user in users:
        auth_subject = str(user.supabase_uid or "")
        await db.delete(user)
        await db.flush()
        if auth_subject:
            try:
                await delete_clerk_user(auth_subject)
            except Exception:
                logger.exception(
                    "Failed to delete Clerk identity %s during scheduled reap", auth_subject
                )
        logger.info(
            "Account hard-deleted after grace period: %s (requested %s)",
            auth_subject or user.id,
            user.deletion_requested_at,
        )
        removed += 1

    return removed
