"""Recruiter outreach: queue, approve, send within a daily cap, follow up once,
and stop the moment the company answers.

Rules this module enforces:
- Every initial email and follow-up requires explicit approval of its payload.
- Address validation cannot grant approval; invalid addresses are never queued.
- Daily caps and reply/bounce detection apply after approval.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import re
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError

from app.core.database import AsyncSessionLocal
from app.models.db import RecruiterOutreach, User, UserPreferences

logger = logging.getLogger(__name__)

FOLLOWUP_AFTER_DAYS = 6
DEFAULT_DAILY_CAP = 25
# New senders start low and earn the member's cap slowly so Gmail does not
# flag the account: RAMP_START a day, RAMP_STEP more each full week.
RAMP_START = 20
RAMP_STEP = 2
STUCK_SENDING_AFTER = timedelta(hours=1)
_PENDING = ("held", "draft", "approved")
_BOUNCE_SENDERS = ("mailer-daemon", "postmaster")


def initial_state(verdict: str, auto_send_allowed: bool) -> str | None:
    """Where a new email starts: None for an address that must never be used."""
    if verdict == "invalid":
        return None
    if verdict != "valid":
        return "held"
    return "draft"


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


def ramp_cap(first_sent_at: datetime | None, now: datetime, ceiling: int) -> int:
    """Today's allowed sends: the member's cap, reached gradually."""
    weeks = 0 if first_sent_at is None else max((now - first_sent_at).days, 0) // 7
    return max(min(ceiling, RAMP_START + RAMP_STEP * weeks), 0)


def domain_of(address: str) -> str:
    return address.rsplit("@", 1)[-1].strip().lower()


def company_key(address: str) -> str:
    """What identifies a company in an address: its domain, or the whole
    address for free-mail providers, where the domain says nothing about who
    works there."""
    from app.services.recruiter_email import _FREE_MAIL, registrable_domain

    domain = domain_of(address)
    if registrable_domain(domain) in _FREE_MAIL:
        return address.strip().lower()
    return domain


def _same_company(address: str):
    key = company_key(address)
    if key == domain_of(address):
        return func.lower(func.split_part(RecruiterOutreach.to_email, "@", 2)) == key
    return func.lower(RecruiterOutreach.to_email) == key


async def replied_domains(db, user_id: uuid.UUID) -> set[str]:
    """Companies where anyone has answered the member (see company_key)."""
    rows = await db.execute(
        select(RecruiterOutreach.to_email).where(
            RecruiterOutreach.user_id == user_id,
            RecruiterOutreach.replied_at.is_not(None),
        )
    )
    return {company_key(address) for address in rows.scalars().all()}


def pixel_base() -> str | None:
    """Public address recipients' mail apps can load the pixel from, or None
    when none is configured (localhost or plain http would never work)."""
    from urllib.parse import urlsplit

    from app.core.config import settings

    base = (settings.PUBLIC_API_URL or "").rstrip("/")
    parts = urlsplit(base)
    if (
        parts.scheme != "https"
        or not parts.hostname
        or parts.hostname in {"localhost", "127.0.0.1"}
    ):
        return None
    return base


def tracked_html(body: str, token: str) -> str | None:
    """HTML version of a plain email with the open-tracking pixel. The text
    part stays the readable original. None when there is no public address."""
    from html import escape

    base = pixel_base()
    if base is None:
        return None
    pixel = f"{base}/api/v1/outreach/open/{token}.gif"
    text = escape(body).replace("\n", "<br>")
    return f'<div>{text}</div><img src="{escape(pixel, quote=True)}" width="1" height="1" alt="">'


async def record_open(token: str) -> bool:
    """First load of the tracking pixel marks the email opened. Mail apps
    that preload images can mark it early, so this is a hint, not proof."""
    if not token or len(token) > 40:
        return False
    async with AsyncSessionLocal() as db:
        result = await db.execute(
            update(RecruiterOutreach)
            .where(
                RecruiterOutreach.open_token == token,
                RecruiterOutreach.opened_at.is_(None),
            )
            .values(opened_at=datetime.now(UTC))
        )
        await db.commit()
        return result.rowcount > 0


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


def payload_hash(row, attachments: list[tuple[str, bytes]]) -> str:
    """Bind approval to the exact wording, recipient and attachment bytes."""
    payload = {
        "to": row.to_email,
        "subject": row.subject,
        "body": row.body,
        "resume_document_id": (str(row.resume_document_id) if row.resume_document_id else None),
        "attachments": [(name, hashlib.sha256(data).hexdigest()) for name, data in attachments],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


async def _attachments(row) -> list[tuple[str, bytes]]:
    if not row.resume_document_id:
        return []
    from app.applications.submission import load_resume

    pdf, _ = await load_resume(row.user_id, str(row.resume_document_id))
    return [("Resume.pdf", pdf)]


def has_current_approval(row, attachments) -> bool:
    return bool(
        row.approved_at
        and row.approved_payload_hash
        and hmac.compare_digest(row.approved_payload_hash, payload_hash(row, attachments))
    )


async def sent_in_last_day(db, user_id: uuid.UUID, now: datetime) -> int:
    return (
        await db.execute(
            select(func.count()).where(
                RecruiterOutreach.user_id == user_id,
                RecruiterOutreach.state.in_(("sending", "sent")),
                func.coalesce(RecruiterOutreach.sent_at, RecruiterOutreach.sending_at)
                > now - timedelta(hours=24),
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
    resume_document_id: str | None = None,
) -> RecruiterOutreach | None:
    """Add an email to the member's outreach. Returns None when the address is
    invalid or this application already has a first email."""
    owner = uuid.UUID(user_id)
    async with AsyncSessionLocal() as db:
        state = initial_state(verdict, False)
        if state is None:
            return None
        row = RecruiterOutreach(
            id=uuid.uuid4(),
            user_id=owner,
            job_application_id=(uuid.UUID(job_application_id) if job_application_id else None),
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
            resume_document_id=(uuid.UUID(str(resume_document_id)) if resume_document_id else None),
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
        row = (
            await db.execute(
                select(RecruiterOutreach)
                .where(
                    RecruiterOutreach.id == uuid.UUID(outreach_id),
                    RecruiterOutreach.user_id == uuid.UUID(user_id),
                    RecruiterOutreach.state.in_(("held", "draft")),
                )
                .with_for_update()
            )
        ).scalar_one_or_none()
        if row is None:
            return False
        # Missing/replaced attachments cannot inherit approval of the old file.
        try:
            attachments = await _attachments(row)
        except Exception:
            return False
        row.approved_payload_hash = payload_hash(row, attachments)
        row.state, row.approved_at = "approved", datetime.now(UTC)
        await db.commit()
        return True


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
            func.count(RecruiterOutreach.opened_at),
        )
        .where(RecruiterOutreach.user_id == user_id)
        .group_by(RecruiterOutreach.state)
    )
    stats = {
        "held": 0,
        "draft": 0,
        "approved": 0,
        "sent": 0,
        "failed": 0,
        "cancelled": 0,
    }
    replied = bounced = opened = 0
    for state, count, replies, bounces, opens in rows.all():
        stats[state] = stats.get(state, 0) + count
        replied += replies
        bounced += bounces
        opened += opens
    stats["replied"], stats["bounced"], stats["opened"] = replied, bounced, opened
    return stats


async def _eligible_sender(db, owner, now) -> bool:
    user = (
        await db.execute(
            select(User)
            .where(User.id == owner)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    return bool(
        user is not None
        and (user.deletion_scheduled_for is None or user.deletion_scheduled_for > now)
    )


async def send_approved(user_id: str, gmail_factory=None) -> dict:
    """Send approved emails, oldest first, until the daily cap is reached."""
    from app.services.gmail_service import GmailMCPClient, GmailSendError

    owner = uuid.UUID(user_id)
    gmail = (gmail_factory or GmailMCPClient)(user_id)
    sent = failed = 0
    async with AsyncSessionLocal() as db:
        now = datetime.now(UTC)
        # Always acquire the owner before outreach rows, matching account erasure.
        if not await _eligible_sender(db, owner, now):
            return {"sent": 0, "failed": 0, "cap_reached": False}
        prefs = await _preferences(db, owner)
        cap = prefs.outreach_daily_cap if prefs else DEFAULT_DAILY_CAP
        track = bool(prefs and prefs.outreach_track_opens)
        first_sent = (
            await db.execute(
                select(func.min(RecruiterOutreach.sent_at)).where(
                    RecruiterOutreach.user_id == owner
                )
            )
        ).scalar_one()
        cap = ramp_cap(first_sent, now, cap)
        # A send interrupted by a crash is never retried blindly: the email
        # may have gone out, so the member checks the Sent folder.
        await db.execute(
            update(RecruiterOutreach)
            .where(
                RecruiterOutreach.user_id == owner,
                RecruiterOutreach.state == "sending",
                or_(
                    RecruiterOutreach.sending_at.is_(None),
                    RecruiterOutreach.sending_at < now - STUCK_SENDING_AFTER,
                ),
            )
            .values(
                state="failed",
                last_error="Sending was interrupted. Check your Sent folder before retrying.",
            )
        )
        await db.execute(
            update(RecruiterOutreach)
            .where(
                RecruiterOutreach.user_id == owner,
                RecruiterOutreach.state == "approved",
                or_(
                    RecruiterOutreach.approved_at.is_(None),
                    RecruiterOutreach.approved_payload_hash.is_(None),
                ),
            )
            .values(state="draft", approved_at=None, approved_payload_hash=None)
        )
        room = max(cap - await sent_in_last_day(db, owner, now), 0)
        if room == 0:
            await db.commit()
            return {"sent": 0, "failed": 0, "cap_reached": True}
        answered = await replied_domains(db, owner)
        rows = (
            (
                await db.execute(
                    select(RecruiterOutreach)
                    .where(
                        RecruiterOutreach.user_id == owner,
                        RecruiterOutreach.state == "approved",
                    )
                    .order_by(RecruiterOutreach.created_at)
                    .limit(room)
                    .with_for_update(skip_locked=True)
                )
            )
            .scalars()
            .all()
        )
        for candidate in rows:
            # Serialize quota reservation across send workers. A sending row's
            # timestamp counts before Gmail returns, so two workers cannot both
            # spend the last remaining slot.
            if not await _eligible_sender(db, owner, datetime.now(UTC)):
                await db.commit()
                return {"sent": sent, "failed": failed, "cap_reached": False}
            if await sent_in_last_day(db, owner, datetime.now(UTC)) >= cap:
                await db.commit()
                return {"sent": sent, "failed": failed, "cap_reached": True}
            # A previous send commits and releases all selected locks. Reacquire
            # and reload each row before claiming it, including across workers.
            row = (
                await db.execute(
                    select(RecruiterOutreach)
                    .where(
                        RecruiterOutreach.id == candidate.id,
                        RecruiterOutreach.user_id == owner,
                        RecruiterOutreach.state == "approved",
                    )
                    .with_for_update(skip_locked=True)
                    .execution_options(populate_existing=True)
                )
            ).scalar_one_or_none()
            if row is None:
                continue
            if company_key(row.to_email) in answered:
                # Someone at this company already replied: nothing more goes out.
                row.state = "cancelled"
                await db.commit()
                continue
            try:
                attachments = await _attachments(row)
            except Exception:
                row.state, row.last_error = (
                    "failed",
                    "The tailored resume is unavailable.",
                )
                failed += 1
                await db.commit()
                continue
            if not has_current_approval(row, attachments):
                row.state = "draft"
                row.approved_at = row.approved_payload_hash = None
                row.last_error = "Message or attachment changed; review and approve again."
                await db.commit()
                continue
            # Freeze the values used by Gmail before releasing the SQL row lock.
            recipient, subject, body = row.to_email, row.subject, row.body
            # Recorded before the send so a crash can never send it twice.
            row.state, row.sending_at = "sending", now
            await db.commit()
            extra = {}
            if attachments:
                extra["attachments"] = attachments
            if track:
                token = secrets.token_urlsafe(24)
                if html := tracked_html(body, token):
                    row.open_token = token
                    extra["html"] = html
            try:
                response = await asyncio.to_thread(
                    gmail.send_message, recipient, subject, body, **extra
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
        await db.commit()
    return {"sent": sent, "failed": failed, "cap_reached": False}


async def queue_due_followups(user_id: str, now: datetime | None = None) -> int:
    """One follow-up per sent first email that is due and unanswered."""
    owner = uuid.UUID(user_id)
    now = now or datetime.now(UTC)
    queued = 0
    async with AsyncSessionLocal() as db:
        answered = await replied_domains(db, owner)
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
            if company_key(original.to_email) in answered:
                original.followup_due_at = None
                continue
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
                    state="draft",
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
                await db.execute(
                    update(RecruiterOutreach)
                    .where(
                        RecruiterOutreach.user_id == owner,
                        RecruiterOutreach.id != row.id,
                        RecruiterOutreach.state.in_(_PENDING),
                        or_(
                            _same_company(row.to_email),
                            RecruiterOutreach.job_application_id == row.job_application_id,
                        ),
                    )
                    .values(state="cancelled")
                )
        await db.commit()
    return {"replied": replied, "bounced": bounced}
