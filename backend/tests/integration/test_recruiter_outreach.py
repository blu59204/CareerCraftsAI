"""Outreach rules against a real database: caps, approval, follow-up, replies."""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1",
    reason="Disposable workflow infrastructure required",
)

ASYNC_URL = "postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"


@pytest.fixture
async def maker(monkeypatch):
    import app.services.outreach_service as service
    from app.core.database import Base

    engine = create_async_engine(ASYNC_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    session_maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(service, "AsyncSessionLocal", session_maker)
    yield session_maker
    await engine.dispose()


class FakeGmail:
    def __init__(self, user_id, threads=None):
        self.sent = []
        self.threads = threads or {}

    def send_message(self, to, subject, body):
        self.sent.append(to)
        return {"id": f"msg-{len(self.sent)}", "threadId": f"thr-{len(self.sent)}"}

    def get_thread_headers(self, thread_id):
        return self.threads.get(thread_id, [])


async def _member(maker, cap=25, auto=False):
    from app.models.db import User, UserPreferences

    user_id = uuid.uuid4()
    async with maker() as db:
        db.add(User(id=user_id, email=f"{user_id}@example.test"))
        await db.flush()
        db.add(UserPreferences(user_id=user_id, outreach_daily_cap=cap, outreach_auto_send=auto))
        await db.commit()
    return str(user_id)


async def _queue(user_id, email, verdict="valid", company="Acme", application=None):
    from app.services.outreach_service import queue_outreach

    return await queue_outreach(
        user_id,
        company=company,
        to_email=email,
        verdict=verdict,
        subject="Hello",
        body="Body",
        job_application_id=application,
    )


async def _rows(maker, user_id):
    from app.models.db import RecruiterOutreach

    async with maker() as db:
        rows = await db.execute(
            select(RecruiterOutreach).where(RecruiterOutreach.user_id == uuid.UUID(user_id))
        )
        return list(rows.scalars().all())


async def test_unverified_is_held_invalid_is_dropped_valid_waits_for_approval(maker):
    user = await _member(maker)
    assert (await _queue(user, "a@acme.com", "valid")).state == "draft"
    assert (await _queue(user, "b@acme.com", "unknown")).state == "held"
    assert await _queue(user, "c@acme.com", "invalid") is None


async def test_nothing_is_sent_until_approved_and_the_daily_cap_holds(maker):
    from app.services import outreach_service as service

    user = await _member(maker, cap=2)
    first = await _queue(user, "a@acme.com")
    for address in ("b@acme.com", "c@acme.com", "d@acme.com"):
        row = await _queue(user, address)
        await service.approve_outreach(user, str(row.id))

    gmail = FakeGmail(user)
    assert (await service.send_approved(user, lambda _: gmail))["sent"] == 2
    assert len(gmail.sent) == 2 and "a@acme.com" not in gmail.sent  # never approved
    again = await service.send_approved(user, lambda _: gmail)
    assert again == {"sent": 0, "failed": 0, "cap_reached": True}
    assert (await service.approve_outreach(user, str(first.id))) is True


async def test_auto_send_starts_only_after_three_hand_approved_sends(maker):
    from app.services import outreach_service as service

    user = await _member(maker, auto=True)
    assert (await _queue(user, "a@acme.com")).state == "draft"
    for i in range(3):
        row = await _queue(user, f"p{i}@acme.com")
        await service.approve_outreach(user, str(row.id))
    gmail = FakeGmail(user)
    await service.send_approved(user, lambda _: gmail)
    assert (await _queue(user, "next@acme.com")).state == "approved"
    # an unverified address is still held, auto-send or not
    assert (await _queue(user, "maybe@acme.com", "unknown")).state == "held"


async def test_one_followup_after_six_days_and_none_after_a_reply(maker):
    from app.models.db import JobApplication
    from app.services import outreach_service as service

    user = await _member(maker)
    async with maker() as db:
        apps = [
            JobApplication(user_id=uuid.UUID(user), company="Acme", role="Eng"),
            JobApplication(user_id=uuid.UUID(user), company="Beta", role="Eng"),
        ]
        db.add_all(apps)
        await db.commit()
        ids = [str(a.id) for a in apps]
    gmail = FakeGmail(user)
    for email, app_id, company in (("a@acme.com", ids[0], "Acme"), ("b@beta.io", ids[1], "Beta")):
        row = await _queue(user, email, company=company, application=app_id)
        await service.approve_outreach(user, str(row.id))
    await service.send_approved(user, lambda _: gmail)

    soon = datetime.now(UTC) + timedelta(days=5)
    assert await service.queue_due_followups(user, soon) == 0
    later = datetime.now(UTC) + timedelta(days=7)

    # Acme answers before the follow-up is due
    gmail.threads = {
        "thr-1": [
            {"id": "msg-1", "from": "Me <me@gmail.com>"},
            {"id": "x", "from": "Jane <jane@acme.com>"},
        ]
    }
    assert (await service.record_replies(user, lambda _: gmail))["replied"] == 1
    assert await service.queue_due_followups(user, later) == 1  # Beta only
    assert await service.queue_due_followups(user, later) == 0  # never twice
    kinds = {r.company: r.kind for r in await _rows(maker, user) if r.kind == "followup"}
    assert kinds == {"Beta": "followup"}


async def test_a_reply_cancels_everything_waiting_for_that_company(maker):
    from app.services import outreach_service as service

    user = await _member(maker)
    sent = await _queue(user, "a@acme.com")
    await service.approve_outreach(user, str(sent.id))
    gmail = FakeGmail(user)
    await service.send_approved(user, lambda _: gmail)
    waiting = await _queue(user, "other@acme.com", "unknown")  # same company, different person

    gmail.threads = {
        "thr-1": [{"id": "msg-1", "from": "me@gmail.com"}, {"id": "y", "from": "hr@acme.com"}]
    }
    await service.record_replies(user, lambda _: gmail)
    states = {r.to_email: r.state for r in await _rows(maker, user)}
    assert states["other@acme.com"] == "cancelled"
    assert waiting.state == "held"  # the object we hold is stale; the row is what changed


async def test_edit_cancel_and_stats(maker):
    from app.services import outreach_service as service

    user = await _member(maker)
    row = await _queue(user, "a@acme.com")
    assert await service.edit_outreach(user, str(row.id), "New subject", None)
    assert await service.approve_outreach(user, str(row.id))
    # wording is locked once approved
    assert not await service.edit_outreach(user, str(row.id), "Sneaky", None)
    assert await service.cancel_outreach(user, str(row.id))
    assert not await service.cancel_outreach(user, str(row.id))
    other = await _member(maker)
    held = await _queue(other, "b@acme.com", "unknown")
    assert not await service.cancel_outreach(user, str(held.id))  # not theirs

    async with maker() as db:
        stats = await service.outreach_stats(db, uuid.UUID(user))
    assert stats["cancelled"] == 1 and stats["sent"] == 0


async def test_daily_summary_counts_the_last_day_and_respects_the_opt_in(maker, monkeypatch):
    import app.services.daily_summary as summary
    from app.services import outreach_service as service

    monkeypatch.setattr(summary, "AsyncSessionLocal", maker)
    user = await _member(maker)
    row = await _queue(user, "a@acme.com")
    await service.approve_outreach(user, str(row.id))
    await service.send_approved(user, lambda _: FakeGmail(user))
    await _queue(user, "b@acme.com", "unknown")

    stats = await summary.build_summary(user)
    assert stats["emails_sent"] == 1 and stats["needs_approval"] == 1
    assert user not in await summary.list_summary_users()  # opt-in, off by default


async def test_applications_list_carries_resume_and_email_status(maker):
    from app.api.v1.jobs import _with_tracking
    from app.models.db import JobApplication, UserDocument
    from app.services import outreach_service as service

    user = await _member(maker)
    async with maker() as db:
        document = UserDocument(
            user_id=uuid.UUID(user),
            doc_type="resume",
            filename="jane-acme.pdf",
            storage_path="x",
            raw_text="Jane Doe resume",
        )
        db.add(document)
        await db.flush()
        tracked = JobApplication(
            user_id=uuid.UUID(user), company="Acme", role="Eng", resume_id=document.id
        )
        bare = JobApplication(user_id=uuid.UUID(user), company="Beta", role="Eng")
        db.add_all([tracked, bare])
        await db.commit()
        tracked_id = str(tracked.id)
    row = await _queue(user, "a@acme.com", application=tracked_id)
    await service.approve_outreach(user, str(row.id))
    await service.send_approved(user, lambda _: FakeGmail(user))

    async with maker() as db:
        apps = (await db.execute(select(JobApplication))).scalars().all()
        mine = [a for a in apps if str(a.user_id) == user]
        result = {a.company: a for a in await _with_tracking(db, uuid.UUID(user), mine)}
    assert result["Acme"].resume_label.startswith("jane-acme.pdf · ")
    assert result["Acme"].outreach_status == "sent" and result["Acme"].outreach_to == "a@acme.com"
    assert result["Beta"].resume_label is None and result["Beta"].outreach_status is None


async def test_auto_apply_queue_tailors_attaches_and_starts_only_safe_jobs(maker, monkeypatch):
    import app.services.auto_apply_queue as queue
    from app.models.db import JobApplication, UserDocument

    monkeypatch.setattr(queue, "AsyncSessionLocal", maker)
    user = await _member(maker)
    async with maker() as db:
        docs = [
            UserDocument(
                user_id=uuid.UUID(user),
                doc_type="resume",
                filename=f"r{i}.pdf",
                storage_path="x",
            )
            for i in range(2)
        ]
        db.add_all(docs)
        apps = [
            JobApplication(
                user_id=uuid.UUID(user),
                company=name,
                role="Eng",
                job_url=f"https://boards.greenhouse.io/{name}/jobs/1",
                match_score=score,
                status="saved",
            )
            for name, score in (("hi", 95), ("mid", 85), ("low", 40))
        ]
        db.add_all(apps)
        await db.commit()
        doc_ids = [str(d.id) for d in docs]
        ids = {a.company: a.id for a in apps}

    drafts = {
        "hi": {"pdf_document_id": doc_ids[0], "grounding": {"checked": True, "unsupported": []}},
        # a resume that claims something unsupported must never be used
        "mid": {"pdf_document_id": doc_ids[1], "grounding": {"unsupported": ["Kubernetes"]}},
    }
    monkeypatch.setattr(queue, "_tailor", lambda uid, app: drafts[app.company])
    started = []

    async def fake_start(user_id, application_id, auto=False):
        started.append((application_id, auto))

    monkeypatch.setattr("app.workflows.starters.start_auto_apply", fake_start)

    assert await queue.queue_for_member(user) == {"queued": 1, "skipped": 1}
    assert started == [(ids["hi"], True)]
    async with maker() as db:
        hi = await db.get(JobApplication, ids["hi"])
        mid = await db.get(JobApplication, ids["mid"])
    assert str(hi.resume_id) == doc_ids[0] and mid.resume_id is None
