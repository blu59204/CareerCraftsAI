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

    def send_message(self, to, subject, body, html=None):
        self.sent.append(to)
        self.html = html
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


async def test_replying_to_the_needs_you_email_saves_the_answers(maker, monkeypatch):
    import base64

    import app.services.email_answers as answers
    from app.models.db import CandidateAnswer, ExtensionTask

    monkeypatch.setattr(answers, "AsyncSessionLocal", maker)
    sent = []

    async def fake_start(*args, **kwargs):
        sent.append(kwargs)

    monkeypatch.setattr("app.workflows.starters.start_notification", fake_start)
    user = await _member(maker)
    task_id = uuid.uuid4()
    async with maker() as db:
        db.add(
            ExtensionTask(
                id=task_id,
                user_id=uuid.UUID(user),
                workflow_id=f"w-{task_id}",
                status="needs_input",
                payload={
                    "company": "Acme",
                    "open_questions": [
                        {"key": "notice_period", "label": "Notice period"},
                        {"key": "salary", "label": "Expected salary"},
                    ],
                },
            )
        )
        await db.commit()

    def body(text):
        return base64.urlsafe_b64encode(text.encode()).decode()

    class Gmail:
        def __init__(self, user_id):
            pass

        def search_threads(self, query, max_results=5):
            assert answers.ref_for(task_id) in query
            return [{"id": "m1", "threadId": "t1"}]

        def get_thread(self, thread_id):
            return {
                "messages": [
                    {
                        "id": "m1",
                        "internalDate": "1",
                        "payload": {"headers": [{"name": "From", "value": "noreply@jobagent.ai"}]},
                    },
                    {
                        "id": "m2",
                        "internalDate": "2",
                        "payload": {
                            "headers": [{"name": "From", "value": f"Me <{user}@example.test>"}],
                            "mimeType": "text/plain",
                            "body": {"data": body("1: 30 days\n\n> 2: ignore me")},
                        },
                    },
                ]
            }

    result = await answers.collect_answers(user, gmail_factory=Gmail)
    assert result == {"answers_saved": 1, "tasks_answered": 1, "restarted": 0}
    async with maker() as db:
        rows = (await db.execute(select(CandidateAnswer))).scalars().all()
        mine = [r for r in rows if str(r.user_id) == user]
        assert [(r.question_key, r.answer["value"], r.approved_by_user) for r in mine] == [
            ("notice_period", "30 days", True)
        ]
        task = await db.get(ExtensionTask, task_id)
        assert [q["key"] for q in task.payload["open_questions"]] == ["salary"]
    assert "1 question is still open" in sent[0]["body"]
    # the same reply is not applied twice
    assert (await answers.collect_answers(user, gmail_factory=Gmail))["answers_saved"] == 0


async def test_a_fully_answered_application_restarts_by_itself(maker, monkeypatch):
    import app.services.email_answers as answers
    from app.models.db import ExtensionTask, JobApplication

    monkeypatch.setattr(answers, "AsyncSessionLocal", maker)
    monkeypatch.setattr(answers.asyncio, "sleep", lambda s: _noop())
    user = await _member(maker)
    application_id, task_id = uuid.uuid4(), uuid.uuid4()
    async with maker() as db:
        db.add(
            JobApplication(id=application_id, user_id=uuid.UUID(user), company="Acme", role="Eng")
        )
        await db.flush()
        db.add(
            ExtensionTask(
                id=task_id,
                user_id=uuid.UUID(user),
                job_application_id=application_id,
                workflow_id=f"w-{task_id}",
                status="needs_input",
                payload={"restart_pending": True},
            )
        )
        await db.commit()
    signals, starts = [], []

    async def fake_signal(workflow_id, update):
        signals.append(workflow_id)
        async with maker() as db:
            (await db.get(ExtensionTask, task_id)).status = "cancelled"
            await db.commit()

    async def fake_start(owner, application, auto=False):
        starts.append(application)
        return {"status": "queued"}

    monkeypatch.setattr("app.workflows.starters.signal_extension_update", fake_signal)
    monkeypatch.setattr("app.workflows.starters.start_auto_apply", fake_start)
    assert await answers.restart_answered(user) == 1
    assert signals == [f"w-{task_id}"] and starts == [application_id]
    async with maker() as db:
        assert "restart_pending" not in (await db.get(ExtensionTask, task_id)).payload
    # nothing left to restart on the next pass
    assert await answers.restart_answered(user) == 0


async def _noop():
    return None


async def test_open_tracking_is_off_by_default_and_marks_the_first_load_when_on(maker):
    from app.models.db import UserPreferences
    from app.services import outreach_service as service

    user = await _member(maker)
    row = await _queue(user, "a@acme.com")
    await service.approve_outreach(user, str(row.id))
    gmail = FakeGmail(user)
    await service.send_approved(user, gmail_factory=lambda _u: gmail)
    assert gmail.html is None and (await _rows(maker, user))[0].open_token is None

    async with maker() as db:
        prefs = await db.scalar(
            select(UserPreferences).where(UserPreferences.user_id == uuid.UUID(user))
        )
        prefs.outreach_track_opens = True
        await db.commit()
    second = await _queue(user, "b@beta.com", company="Beta")
    await service.approve_outreach(user, str(second.id))
    await service.send_approved(user, gmail_factory=lambda _u: gmail)
    token = next(r.open_token for r in await _rows(maker, user) if r.to_email == "b@beta.com")
    assert token and f"/outreach/open/{token}.gif" in gmail.html and "Body" in gmail.html

    assert await service.record_open(token) is True
    assert await service.record_open(token) is False  # only the first load counts
    assert await service.record_open("unknown") is False
    async with maker() as db:
        assert (await service.outreach_stats(db, uuid.UUID(user)))["opened"] == 1


async def test_agent_metrics_count_hands_off_applications_verified_emails_and_bounces(maker):
    from app.models.db import ApplicationAttempt, ExtensionTask, JobApplication
    from app.services.agent_metrics import agent_metrics

    user = await _member(maker)
    owner = uuid.UUID(user)
    ids = [uuid.uuid4() for _ in range(4)]
    async with maker() as db:
        for i, application in enumerate(ids):
            db.add(JobApplication(id=application, user_id=owner, company=f"C{i}", role="Eng"))
        await db.flush()
        for i, application in enumerate(ids[:3]):  # the fourth never submitted
            db.add(
                ApplicationAttempt(
                    id=uuid.uuid4(),
                    user_id=owner,
                    job_application_id=application,
                    workflow_id=f"wf-{application}",
                    state="submitted",
                    submitted_at=datetime.now(UTC),
                )
            )
            db.add(
                ExtensionTask(
                    id=uuid.uuid4(),
                    user_id=owner,
                    job_application_id=application,
                    workflow_id=f"t-{application}",
                    status="completed",
                    payload={"needed_you": True} if i == 0 else {},
                )
            )
        await db.commit()
    first = await _queue(user, "a@c0.com", "valid", "C0", str(ids[0]))
    second = await _queue(user, "b@c1.com", "unknown", "C1", str(ids[1]))
    third = await _queue(user, "c@c2.com", "valid", "C2", str(ids[2]))
    async with maker() as db:
        from app.models.db import RecruiterOutreach

        for row_id, bounced in ((first.id, True), (third.id, False)):
            row = await db.get(RecruiterOutreach, row_id)
            row.state, row.sent_at = "sent", datetime.now(UTC)
            row.bounced_at = datetime.now(UTC) if bounced else None
        await db.commit()
        result = await agent_metrics(db, owner)
    assert result["applications"] == 3 and result["hands_off"] == 2
    assert result["hands_off_rate"] == 0.667
    assert result["verified_emails"] == 2 and result["verified_email_rate"] == 0.667
    assert result["emails_sent"] == 2 and result["bounce_rate"] == 0.5
    assert second is not None


async def test_agent_metrics_are_empty_not_zero_without_data(maker):
    from app.services.agent_metrics import agent_metrics

    user = await _member(maker)
    async with maker() as db:
        result = await agent_metrics(db, uuid.UUID(user))
    assert result["applications"] == 0
    assert result["hands_off_rate"] is None and result["bounce_rate"] is None
