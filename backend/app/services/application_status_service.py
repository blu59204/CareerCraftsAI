"""Moves job applications forward from replies found in the member's inbox.

The email monitor classifies mail; this module decides what that means for a
member's applications and records it. Rules:

- A Gmail message is acted on once (unique per member and message id).
- Status only moves forward (applied, viewed, interview), or to rejected from
  any of those. An offer or a rejection is never overwritten by later mail.
- Mail is matched to an application only when exactly one of the member's
  open applications fits its company; otherwise it is recorded unmatched and
  nothing changes.
"""

from __future__ import annotations

import logging
import re
import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.database import AsyncSessionLocal
from app.models.db import ApplicationStatusEvent, JobApplication

logger = logging.getLogger(__name__)

# Applications still waiting on a reply. "saved" jobs were never applied to,
# so mail from that company says nothing about them.
OPEN_STATUSES = ("applied", "viewed", "interview")
_RANK = {"applied": 1, "viewed": 2, "interview": 3}
_CATEGORY_STATUS = {
    "VIEWED": "viewed",
    "SHORTLISTED": "viewed",
    "INTERVIEW": "interview",
    "REJECTED": "rejected",
}
_COMPANY_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|limited|pvt|private|corp|corporation|co|gmbh|technologies|technology|"
    r"solutions|labs|india)\b\.?",
    re.IGNORECASE,
)


def next_status(current: str, category: str) -> str | None:
    """The status an email of this category moves an application to, or None
    when it should not move (no mapping, not an open application, or not
    forward)."""
    target = _CATEGORY_STATUS.get(category)
    if target is None or current not in _RANK:
        return None
    if target == "rejected":
        return target
    return target if _RANK[target] > _RANK[current] else None


def normalize_company(name: str) -> str:
    cleaned = _COMPANY_SUFFIX.sub(" ", name.lower())
    return re.sub(r"[^a-z0-9]+", " ", cleaned).strip()


def match_application(applications: list[JobApplication], update: dict) -> JobApplication | None:
    """The one open application the email is about, else None.

    The company counts as mentioned when its normalized name appears in the
    email's company, sender or subject. Two open applications at the same
    company are ambiguous (which role replied?), so they match nothing.
    """
    haystack = " ".join(
        normalize_company(str(update.get(key) or "")) for key in ("company", "sender", "subject")
    )
    haystack = f" {haystack} "
    hits = []
    for application in applications:
        company = normalize_company(application.company or "")
        if len(company) >= 3 and f" {company} " in haystack:
            hits.append(application)
    return hits[0] if len(hits) == 1 else None


async def processed_message_ids(user_id: str, message_ids: list[str]) -> set[str]:
    """Which of these Gmail messages were already acted on."""
    if not message_ids:
        return set()
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(ApplicationStatusEvent.gmail_message_id).where(
                ApplicationStatusEvent.user_id == uuid.UUID(user_id),
                ApplicationStatusEvent.gmail_message_id.in_(message_ids),
            )
        )
        return set(rows.scalars().all())


async def apply_inbox_updates(user_id: str, updates: list[dict]) -> list[dict]:
    """Record each classified email and advance the application it belongs to.

    Returns the changes made: {application_id, company, role, from_status,
    to_status, subject}. Safe to repeat: a message already recorded is skipped.
    """
    owner = uuid.UUID(user_id)
    changes: list[dict] = []
    async with AsyncSessionLocal() as db:
        applications = list(
            (
                await db.execute(
                    select(JobApplication)
                    .where(
                        JobApplication.user_id == owner,
                        JobApplication.status.in_(OPEN_STATUSES),
                    )
                    .order_by(JobApplication.id)
                    .with_for_update()
                )
            )
            .scalars()
            .all()
        )
        for update in updates:
            message_id = update.get("message_id")
            if not message_id:
                continue
            application = match_application(applications, update)
            previous = application.status if application else None
            new_status = next_status(previous, update["category"]) if application else None
            inserted = await db.execute(
                pg_insert(ApplicationStatusEvent)
                .values(
                    id=uuid.uuid4(),
                    user_id=owner,
                    job_application_id=application.id if application else None,
                    gmail_message_id=message_id,
                    category=update["category"],
                    company=(update.get("company") or None),
                    subject=(update.get("subject") or "")[:200] or None,
                    previous_status=previous,
                    new_status=new_status,
                )
                .on_conflict_do_nothing(index_elements=["user_id", "gmail_message_id"])
                .returning(ApplicationStatusEvent.id)
            )
            if inserted.scalar() is None:
                continue  # seen on an earlier scan
            if application and new_status:
                application.status = new_status
                changes.append(
                    {
                        "application_id": str(application.id),
                        "company": application.company,
                        "role": application.role,
                        "from_status": previous,
                        "to_status": new_status,
                        "subject": update.get("subject"),
                    }
                )
        await db.commit()
    if changes:
        logger.info("Inbox moved %d application(s) for user %s", len(changes), user_id)
    return changes


def inbox_tracking_member_ids():
    """Members who opted into inbox tracking, have Gmail connected and an
    active model, and have not asked for their account to be deleted."""
    from app.models.db import IntegrationConnection, UserModelSettings, UserPreferences
    from app.models.db import User as UserModel

    return (
        select(UserModel.id)
        .join(UserPreferences, UserPreferences.user_id == UserModel.id)
        .join(UserModelSettings, UserModelSettings.user_id == UserModel.id)
        .join(IntegrationConnection, IntegrationConnection.user_id == UserModel.id)
        .where(
            UserPreferences.inbox_tracking_enabled == True,  # noqa: E712
            UserModelSettings.is_active == True,  # noqa: E712
            IntegrationConnection.provider == "gmail",
            IntegrationConnection.status == "connected",
            UserModel.deletion_scheduled_for.is_(None),
        )
        .distinct()
    )


async def list_inbox_tracking_users() -> list[str]:
    async with AsyncSessionLocal() as db:
        rows = await db.execute(inbox_tracking_member_ids())
        return [str(user_id) for user_id in rows.scalars().all()]


def scan_inbox_for_member(user_id: str) -> dict:
    """One member's scan, run on a worker thread (the monitor is synchronous)."""
    from app.agents.email_monitor_agent import email_monitor_node

    state = {
        "user_id": user_id,
        "run_id": "",
        "task_type": "email_monitor",
        "context": {},
        "messages": [],
        "status": "running",
        "pending_action": None,
        "result": None,
        "error": None,
    }
    final = email_monitor_node(state)  # type: ignore[arg-type]
    return {"status": final.get("status"), "result": final.get("result")}
