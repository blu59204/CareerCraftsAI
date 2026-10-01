"""Recruiter outreach: queue, approve, send within a daily cap, follow up once,
and stop the moment the company answers.

Rules this module enforces:
- Only a verified-valid address can be sent without the member looking at it;
  unverified ones are held for the member, invalid ones are never queued.
- Every email is approved by the member until a few have been, and then only
  if the member turned on auto-send.
- At most `outreach_daily_cap` emails go out per rolling 24 hours.
- One follow-up, FOLLOWUP_AFTER_DAYS after the first, and none once the
  company has replied or the address bounced.
"""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.db import RecruiterOutreach, UserPreferences

logger = logging.getLogger(__name__)

FOLLOWUP_AFTER_DAYS = 6
AUTO_SEND_AFTER_APPROVED = 3  # emails the member approved by hand first
DEFAULT_DAILY_CAP = 25
_PENDING = ("held", "draft", "approved")
_BOUNCE_SENDERS = ("mailer-daemon", "postmaster")


def initial_state(verdict: str, auto_send_allowed: bool) -> str | None:
    """Where a new email starts: None for an address that must never be used."""
    if verdict == "invalid":
        return None
    if verdict != "valid":
        return "held"
    return "approved" if auto_send_allowed else "draft"


def followup_text(company: str, role: str | None, contact_name: str = "") -> tuple[str, str]:
    """A short, fixed-wording follow-up. No model writes it, so it cannot
    claim anything the member did not say."""
    greeting = f"Hi {contact_name.split()[0]}," if contact_name.strip() else "Hello,"
    position = f" for the {role} role" if role else ""
    subject = f"Following up: {role} at {company}" if role else f"Following up: {company}"
    body = (
        f"{greeting}\n\nI wanted to follow up on my earlier note about my application{position} "
        f"at {company}. I'm still very interested and happy to share anything else that "
        "would help.\n\nThank you for your time."
    )
    return subject, body


def summarize_outreach(rows: list[RecruiterOutreach]) -> dict | None:
    """One line of status for an application's recruiter emails."""
    if not rows:
        return None
    ordered = sorted(rows, key=lambda r: (r.kind == "followup", r.created_at or datetime.min))
    to_email = ordered[0].to_email
    if any(r.replied_at for r in rows):
        status = "replied"
    elif any(r.bounced_at for r in rows):
        status = "bounced"
    else:
        latest = ordered[-1]
        status = (
            "followed up" if latest.kind == "followup" and latest.state == "sent" else latest.state
        )
    return {"status": status, "to_email": to_email}


def classify_thread(messages: list[dict], sent_message_id: str | None) -> str | None:
    """'bounced' or 'replied' for a thread we started, else None.

    The first message is ours; its sender is the member. Anything from
    another sender is a reply, unless it is a mail-system bounce notice.
    """
    if not messages:
        return None
    own = _address(messages[0].get("from", ""))
    for message in messages:
        if sent_message_id and message.get("id") == sent_message_id:
            own = _address(message.get("from", ""))
            break
    for message in messages:
        sender = _address(message.get("from", ""))
        if not sender or sender == own:
            continue
        if any(token in sender.split("@")[0] for token in _BOUNCE_SENDERS):
            return "bounced"
        return "replied"
    return None


def _address(header: str) -> str:
    match = re.search(r"[\w.+-]+@[\w.-]+", header or "")
    return match.group(0).lower() if match else ""


async def _preferences(db, user_id: uuid.UUID) -> UserPreferences | None:
    return (
        await db.execute(select(UserPreferences).where(UserPreferences.user_id == user_id))
    ).scalar_one_or_none()


async def auto_send_allowed(db, user_id: uuid.UUID) -> bool:
    prefs = await _preferences(db, user_id)
    if not prefs or not prefs.outreach_auto_send:
        return False
    approved = (
        await db.execute(
            select(func.count()).where(
                RecruiterOutreach.user_id == user_id,
                RecruiterOutreach.state == "sent",
                RecruiterOutreach.approved_at.is_not(None),
            )
        )
    ).scalar_one()
    return approved >= AUTO_SEND_AFTER_APPROVED


async def sent_in_last_day(db, user_id: uuid.UUID, now: datetime) -> int:
    return (
        await db.execute(
            select(func.count()).where(
                RecruiterOutreach.user_id == user_id,
                RecruiterOutreach.state.in_(("sending", "sent")),
                RecruiterOutreach.sent_at > now - timedelta(hours=24),
            )
        )
    ).scalar_one()


async def list_outreach_users() -> list[str]:
    """Members with something to send or a sent email still awaiting an answer."""
    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(RecruiterOutreach.user_id)
            .where(
                or_(
                    RecruiterOutreach.state == "approved",
                    (RecruiterOutreach.state == "sent")
                    & RecruiterOutreach.replied_at.is_(None)
                    & RecruiterOutreach.bounced_at.is_(None)
                    & (RecruiterOutreach.sent_at > datetime.now(UTC) - timedelta(days=30)),
                )
            )
            .distinct()
        )
        return [str(user_id) for user_id in rows.scalars().all()]


async def queue_outreach(
    user_id: str,
    *,
    company: str,
    to_email: str,
    verdict: str,
    subject: str,
    body: str,
    job_application_id: str | None = None,
    role: str | None = None,
    email_source: str | None = None,
    verified_by: str | None = None,
    resume_version: str | None = None,
) -> RecruiterOutreach | None:
    """Add an email to the member's outreach. Returns None when the address is
    invalid or this application already has a first email."""
    owner = uuid.UUID(user_id)
    async with AsyncSessionLocal() as db:
        state = initial_state(verdict, await auto_send_allowed(db, owner))
        if state is None:
            return None
        row = RecruiterOutreach(
            id=uuid.uuid4(),
            user_id=owner,
            job_application_id=uuid.UUID(job_application_id) if job_application_id else None,
            kind="initial",
            company=company,
            role=role,
            to_email=to_email.lower(),
            email_source=email_source,
            verdict=verdict,
            verified_by=verified_by,
            subject=subject,
            body=body,
            resume_version=resume_version,
            state=state,
            approved_at=None,
        )
        db.add(row)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return None
        return row


async def approve_outreach(user_id: str, outreach_id: str) -> bool:
    """The member's go-ahead for a held or draft email. Held (unverified)
    emails need this too: approving one is the member vouching for it."""
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(RecruiterOutreach)
            .where(
                RecruiterOutreach.id == uuid.UUID(outreach_id),
                RecruiterOutreach.user_id == uuid.UUID(user_id),
                RecruiterOutreach.state.in_(("held", "draft")),
            )
            .values(state="approved", approved_at=datetime.now(UTC))
        )
        await db.commit()
        return result.rowcount == 1


async def cancel_outreach(user_id: str, outreach_id: str) -> bool:
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(RecruiterOutreach)
            .where(
                RecruiterOutreach.id == uuid.UUID(outreach_id),
                RecruiterOutreach.user_id == uuid.UUID(user_id),
                RecruiterOutreach.state.in_(_PENDING),
            )
            .values(state="cancelled")
        )
        await db.commit()
        return result.rowcount == 1


async def edit_outreach(
    user_id: str, outreach_id: str, subject: str | None, body: str | None
) -> bool:
    """Change the wording of an email that has not been approved yet."""
    values = {k: v for k, v in (("subject", subject), ("body", body)) if v is not None}
    if not values:
        return False
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(RecruiterOutreach)
            .where(
                RecruiterOutreach.id == uuid.UUID(outreach_id),
                RecruiterOutreach.user_id == uuid.UUID(user_id),
                RecruiterOutreach.state.in_(("held", "draft")),
            )
            .values(**values)
        )
        await db.commit()
        return result.rowcount == 1


async def outreach_stats(db, user_id: uuid.UUID) -> dict:
    """Counts for the dashboard: how many emails are in each stage."""
    rows = await db.execute(
        select(
            RecruiterOutreach.state,
            func.count(),
            func.count(RecruiterOutreach.replied_at),
            func.count(RecruiterOutreach.bounced_at),
        )
        .where(RecruiterOutreach.user_id == user_id)
        .group_by(RecruiterOutreach.state)
    )
    stats = {"held": 0, "draft": 0, "approved": 0, "sent": 0, "failed": 0, "cancelled": 0}
    replied = bounced = 0
    for state, count, replies, bounces in rows.all():
        stats[state] = stats.get(state, 0) + count
        replied += replies
        bounced += bounces
    stats["replied"], stats["bounced"] = replied, bounced
    return stats


async def send_approved(user_id: str, gmail_factory=None) -> dict:
    """Send approved emails, oldest first, until the daily cap is reached."""
    from app.services.gmail_service import GmailMCPClient, GmailSendError

    owner = uuid.UUID(user_id)
    gmail = (gmail_factory or GmailMCPClient)(user_id)
    sent = failed = 0
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC)
        prefs = await _preferences(db, owner)
        cap = prefs.outreach_daily_cap if prefs else DEFAULT_DAILY_CAP
        room = max(cap - await sent_in_last_day(db, owner, now), 0)
        if room == 0:
            return {"sent": 0, "failed": 0, "cap_reached": True}
        rows = (
            (
                await db.execute(
                    select(RecruiterOutreach)
                    .where(
                        RecruiterOutreach.user_id == owner, RecruiterOutreach.state == "approved"
                    )
                    .order_by(RecruiterOutreach.created_at)
                    .limit(room)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            # Recorded before the send so a crash can never send it twice.
            row.state = "sending"
            await db.commit()
            try:
                response = await asyncio.to_thread(
                    gmail.send_message, row.to_email, row.subject, row.body
                )
            except GmailSendError as exc:
                row.state, row.last_error = "failed", str(exc)[:500]
                failed += 1
            else:
                row.state = "sent"
                row.sent_at = datetime.now(UTC)
                row.gmail_message_id = response.get("id")
                row.gmail_thread_id = response.get("threadId")
                if row.kind == "initial":
                    row.followup_due_at = row.sent_at + timedelta(days=FOLLOWUP_AFTER_DAYS)
                sent += 1
            await db.commit()
    return {"sent": sent, "failed": failed, "cap_reached": False}


async def queue_due_followups(user_id: str, now: datetime | None = None) -> int:
    """One follow-up per sent first email that is due and unanswered."""
    owner = uuid.UUID(user_id)
    now = now or datetime.now(UTC)
    queued = 0
    async with AsyncSessionLocal() as db:
        allow_auto = await auto_send_allowed(db, owner)
        due = (
            (
                await db.execute(
                    select(RecruiterOutreach).where(
                        RecruiterOutreach.user_id == owner,
                        RecruiterOutreach.kind == "initial",
                        RecruiterOutreach.state == "sent",
                        RecruiterOutreach.followup_due_at <= now,
                        RecruiterOutreach.replied_at.is_(None),
                        RecruiterOutreach.bounced_at.is_(None),
                    )
                )
            )
            .scalars()
            .all()
        )
        for original in due:
            subject, body = followup_text(original.company, original.role)
            db.add(
                RecruiterOutreach(
                    id=uuid.uuid4(),
                    user_id=owner,
                    job_application_id=original.job_application_id,
                    parent_id=original.id,
                    kind="followup",
                    company=original.company,
                    role=original.role,
                    to_email=original.to_email,
                    email_source=original.email_source,
                    verdict=original.verdict,
                    verified_by=original.verified_by,
                    subject=subject,
                    body=body,
                    resume_version=original.resume_version,
                    state="approved" if allow_auto and original.verdict == "valid" else "draft",
                )
            )
            original.followup_due_at = None  # never queue a second follow-up
            queued += 1
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return 0
    return queued


async def record_replies(user_id: str, gmail_factory=None) -> dict:
    """Check the threads of sent emails for a reply or a bounce. A reply from
    the company ends the sequence: pending follow-ups are cancelled."""
    from app.services.gmail_service import GmailMCPClient

    owner = uuid.UUID(user_id)
    gmail = (gmail_factory or GmailMCPClient)(user_id)
    replied = bounced = 0
    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(RecruiterOutreach).where(
                        RecruiterOutreach.user_id == owner,
                        RecruiterOutreach.state == "sent",
                        RecruiterOutreach.replied_at.is_(None),
                        RecruiterOutreach.bounced_at.is_(None),
                        RecruiterOutreach.gmail_thread_id.is_not(None),
                        RecruiterOutreach.sent_at > datetime.now(UTC) - timedelta(days=30),
                    )
                )
            )
            .scalars()
            .all()
        )
        for row in rows:
            messages = await asyncio.to_thread(gmail.get_thread_headers, row.gmail_thread_id)
            outcome = classify_thread(messages, row.gmail_message_id)
            if outcome is None:
                continue
            now = datetime.now(UTC)
            if outcome == "replied":
                row.replied_at = now
                replied += 1
            else:
                row.bounced_at = now
                bounced += 1
            row.followup_due_at = None
            if outcome == "replied":
                # Any reply from the company stops everything still waiting to
                # go to it, on this application or another.
                company_domain = "%@" + row.to_email.split("@")[-1]
                await db.execute(
                    update(RecruiterOutreach)
                    .where(
                        RecruiterOutreach.user_id == owner,
                        RecruiterOutreach.id != row.id,
                        RecruiterOutreach.state.in_(_PENDING),
                        or_(
                            RecruiterOutreach.to_email.like(company_domain),
                            RecruiterOutreach.job_application_id == row.job_application_id,
                        ),
                    )
                    .values(state="cancelled")
                )
        await db.commit()
    return {"replied": replied, "bounced": bounced}
