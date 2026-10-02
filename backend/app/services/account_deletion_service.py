"""Hard-deletes accounts whose 15-day deletion grace period has elapsed.

Requesting deletion (see app.api.v1.users) never removes anything itself —
it only stamps deletion_scheduled_for. This module is the other half: a
periodic sweep (called from the maintenance activity) that finds accounts
past that date and actually deletes them.

Deleting the users row cascades to every table keyed to it, but some of a
member's data lives elsewhere: running workflows, Nango grants, uploaded
files, RAG collections and agent memory (keyed by a text user_id with no
foreign key), Redis keys, and the Clerk identity. Each of those is erased
first, Clerk last; only then is the row deleted. Every step is idempotent,
so when one fails the row stays and the next sweep finishes the job.
"""

import logging
import shutil
import uuid
from datetime import UTC, datetime

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.db import AgentRun, JobApplication, User

logger = logging.getLogger(__name__)

_OPEN_RUN_STATUSES = ("queued", "running", "awaiting_approval")
# Agent memory tables (created by MemoryManager, so possibly absent) and the
# statement that clears one member from each.
_MEMORY_DELETES = {
    "public.agent_memory_episodes": "DELETE FROM public.agent_memory_episodes WHERE user_id = :uid",
    "public.agent_memory_learnings": (
        "DELETE FROM public.agent_memory_learnings WHERE user_id = :uid"
    ),
    "public.agent_memory_preferences": (
        "DELETE FROM public.agent_memory_preferences WHERE user_id = :uid"
    ),
    "public.agent_memory_procedures": (
        "DELETE FROM public.agent_memory_procedures WHERE user_id = :uid"
    ),
}


async def _terminate_workflows(user_id: uuid.UUID) -> int:
    """Stop anything still running on the member's behalf, so no workflow
    sends an email or submits an application after the account is gone."""
    from temporalio.service import RPCError, RPCStatusCode

    from app.core.database import AsyncSessionLocal
    from app.core.temporal_client import get_temporal_client
    from app.workflows.auto_apply import auto_apply_workflow_id
    from app.workflows.followup import followup_workflow_id
    from app.workflows.job_activities import _workflow_id_for

    async with AsyncSessionLocal() as db:
        runs = (
            (
                await db.execute(
                    select(AgentRun).where(
                        AgentRun.user_id == user_id, AgentRun.status.in_(_OPEN_RUN_STATUSES)
                    )
                )
            )
            .scalars()
            .all()
        )
        application_ids = (
            (
                await db.execute(
                    select(JobApplication.id)
                    .where(JobApplication.user_id == user_id)
                    .execution_options(include_deleted=True)
                )
            )
            .scalars()
            .all()
        )

    workflow_ids = [_workflow_id_for(run) for run in runs]
    for application_id in application_ids:
        workflow_ids.append(auto_apply_workflow_id(str(user_id), str(application_id)))
        workflow_ids.append(followup_workflow_id(str(application_id)))

    client = await get_temporal_client()
    terminated = 0
    for workflow_id in workflow_ids:
        try:
            await client.get_workflow_handle(workflow_id).terminate(reason="Account deleted")
            terminated += 1
        except RPCError as exc:
            if exc.status != RPCStatusCode.NOT_FOUND:  # never started or already closed
                raise
    return terminated


async def _revoke_integrations(user_id: uuid.UUID) -> None:
    from app.integrations.exceptions import IntegrationDisabledError
    from app.integrations.factory import build_integration_gateway

    gateway = build_integration_gateway()
    try:
        try:
            connections = await gateway.list_connections(user_id=user_id)
        except IntegrationDisabledError:
            return
        for connection in connections:
            await gateway.revoke_connection(user_id=user_id, provider=connection.provider)
    finally:
        close = getattr(gateway, "aclose", None)
        if close is not None:
            await close()


def _delete_files(user_id: uuid.UUID) -> None:
    from app.services.storage_service import _root

    root = _root()
    folder = (root / str(user_id)).resolve()
    if folder.parent != root:
        raise PermissionError(f"Refusing to delete {folder}")
    if folder.exists():
        shutil.rmtree(folder)


async def _delete_unlinked_rows(user_id: uuid.UUID) -> None:
    """RAG collections are named "{user_id}_..." and agent memory stores the
    id as text; neither has a foreign key, so the users cascade misses both."""
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        if (
            await db.execute(text("SELECT to_regclass('public.langchain_pg_collection')"))
        ).scalar():
            prefix = f"{user_id}\\_%"
            await db.execute(
                text(
                    "DELETE FROM public.langchain_pg_embedding WHERE collection_id IN "
                    "(SELECT uuid FROM public.langchain_pg_collection WHERE name LIKE :prefix)"
                ),
                {"prefix": prefix},
            )
            await db.execute(
                text("DELETE FROM public.langchain_pg_collection WHERE name LIKE :prefix"),
                {"prefix": prefix},
            )
        for table, statement in _MEMORY_DELETES.items():
            exists = await db.execute(text("SELECT to_regclass(:table)"), {"table": table})
            if exists.scalar():
                await db.execute(text(statement), {"uid": str(user_id)})
        await db.commit()


async def _delete_redis_keys(user_id: uuid.UUID) -> None:
    from app.core.redis_client import get_redis

    redis = get_redis()
    for pattern in (f"token_budget:{user_id}:*", f"{user_id}:*"):
        keys = [key async for key in redis.scan_iter(match=pattern, count=500)]
        if keys:
            await redis.delete(*keys)


async def erase_external_data(user: User) -> None:
    """Remove everything the users cascade cannot reach. Raises on the first
    failure; every step is safe to repeat."""
    from app.core.clerk_auth import delete_clerk_user

    await _terminate_workflows(user.id)
    await _revoke_integrations(user.id)
    _delete_files(user.id)
    await _delete_unlinked_rows(user.id)
    await _delete_redis_keys(user.id)
    if user.clerk_user_id:
        # Last, so a failure above leaves the member able to sign in and
        # cancel while the sweep retries.
        await delete_clerk_user(str(user.clerk_user_id), strict=True)


async def reap_expired_account_deletions(db: AsyncSession) -> int:
    """Hard-delete every account whose grace period has passed. Returns the
    count removed. Callers are expected to commit the session afterward."""
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
        # The list above is a moment old. A member who cancelled since then
        # (the grace period's last minute) must not lose anything: re-check
        # under a row lock, which the cancel request takes too.
        fresh = (
            await db.execute(
                select(User)
                .where(
                    User.id == user.id,
                    User.deletion_scheduled_for.is_not(None),
                    User.deletion_scheduled_for <= datetime.now(UTC),
                )
                .with_for_update(skip_locked=True)
            )
        ).scalar_one_or_none()
        if fresh is None:
            continue
        try:
            await erase_external_data(user)
        except Exception:
            logger.exception("Erasing account %s failed; retrying next sweep", user.id)
            continue
        await db.delete(user)
        await db.flush()
        logger.info(
            "Account hard-deleted after grace period: %s (requested %s)",
            user.clerk_user_id or user.id,
            user.deletion_requested_at,
        )
        removed += 1

    return removed
