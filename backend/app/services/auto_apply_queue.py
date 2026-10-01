"""Queues applications on the member's behalf, if they opted in.

For saved jobs at or above the match-score threshold, tailor a resume, check
it against the member's own documents, attach it and hand the application to
the member's browser extension. The member still reviews every filled form in
the extension before anything is submitted. Limits (daily cap, pacing, score)
are enforced where the attempt is reserved, not here, so they hold however an
application is started.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.db import (
    ApplicationAttempt,
    ExtensionDevice,
    JobApplication,
    User,
    UserModelSettings,
    UserPreferences,
)
from app.services import apply_limits

logger = logging.getLogger(__name__)


def pick_candidates(applications: list[JobApplication], room: int, minimum: int) -> list:
    """Highest-scoring saved jobs with a real URL, at most `room` of them."""
    eligible = [
        a
        for a in applications
        if a.job_url
        and not a.job_url.startswith("https://example.com")
        and apply_limits.score_error(a.match_score, minimum) is None
    ]
    eligible.sort(key=lambda a: a.match_score or 0, reverse=True)
    return eligible[: max(room, 0)]


async def list_auto_apply_users() -> list[str]:
    """Opted-in members with an active model and a paired browser extension."""
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(User.id)
            .join(UserPreferences, UserPreferences.user_id == User.id)
            .join(UserModelSettings, UserModelSettings.user_id == User.id)
            .join(ExtensionDevice, ExtensionDevice.user_id == User.id)
            .where(
                UserPreferences.auto_apply_enabled == True,  # noqa: E712
                UserModelSettings.is_active == True,  # noqa: E712
                ExtensionDevice.revoked_at.is_(None),
                User.deletion_scheduled_for.is_(None),
            )
            .distinct()
        )
        return [str(user_id) for user_id in rows.scalars().all()]


async def _candidates(user_id: uuid.UUID, now: datetime) -> list[JobApplication]:
    async with AsyncSessionLocal() as db:
        started = (
            await db.execute(
                select(func.count()).where(
                    ApplicationAttempt.user_id == user_id,
                    ApplicationAttempt.created_at > now - timedelta(hours=24),
                )
            )
        ).scalar_one()
        room = min(settings.APPLY_DAILY_CAP - started, settings.AUTO_APPLY_QUEUE_BATCH)
        if room <= 0:
            return []
        attempted = select(ApplicationAttempt.job_application_id).where(
            ApplicationAttempt.user_id == user_id
        )
        saved = (
            (
                await db.execute(
                    select(JobApplication).where(
                        JobApplication.user_id == user_id,
                        JobApplication.status == "saved",
                        JobApplication.id.not_in(attempted),
                        JobApplication.match_score >= settings.AUTO_APPLY_MIN_SCORE,
                    )
                )
            )
            .scalars()
            .all()
        )
        return pick_candidates(list(saved), room, settings.AUTO_APPLY_MIN_SCORE)


def _tailor(user_id: str, application: JobApplication) -> dict:
    """Tailor a resume for one job on a worker thread (the agent is synchronous)."""
    from langchain_core.messages import HumanMessage

    from app.agents.resume_agent import resume_agent_node

    jd = (application.jd_text or f"{application.role} at {application.company}")[:3000]
    state = {
        "user_id": user_id,
        "run_id": str(uuid.uuid4()),
        "task_type": "resume_optimize",
        "messages": [HumanMessage(content=jd)],
        "context": {"jd_text": jd, "template": "modern"},
        "status": "running",
        "pending_action": None,
        "result": None,
        "error": None,
    }
    result = resume_agent_node(state)  # type: ignore[arg-type]
    return result.get("pending_action") or {}


async def queue_for_member(user_id: str) -> dict:
    """Tailor and queue the member's best saved jobs. One job failing never
    stops the others; a resume with unsupported claims is never used."""
    from app.workflows.starters import start_auto_apply

    owner = uuid.UUID(user_id)
    queued = skipped = 0
    for application in await _candidates(owner, datetime.now(UTC)):
        try:
            draft = await asyncio.wait_for(
                asyncio.to_thread(_tailor, user_id, application), timeout=300
            )
            document_id = draft.get("pdf_document_id")
            if not document_id or (draft.get("grounding") or {}).get("unsupported"):
                skipped += 1
                continue
            async with AsyncSessionLocal() as db:
                row = await db.get(JobApplication, application.id)
                if row is None or row.status != "saved":
                    continue
                row.resume_id = uuid.UUID(document_id)
                await db.commit()
            await start_auto_apply(owner, application.id, auto=True)
            queued += 1
        except Exception:
            logger.warning("Auto-apply queueing failed for one job", exc_info=True)
            skipped += 1
    return {"queued": queued, "skipped": skipped}
