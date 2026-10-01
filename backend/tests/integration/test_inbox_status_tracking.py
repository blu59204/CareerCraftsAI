"""Inbox replies move applications forward once, against a real database.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_inbox_status_tracking.py.
"""

import os
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1",
    reason="Disposable workflow infrastructure required",
)

ASYNC_URL = "postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"


@pytest.fixture
async def factory(monkeypatch):
    import app.services.application_status_service as service
    from app.core.database import Base

    engine = create_async_engine(ASYNC_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(service, "AsyncSessionLocal", maker)
    yield maker
    await engine.dispose()


async def _member(maker, *companies):
    from app.models.db import JobApplication, User

    user_id = uuid.uuid4()
    async with maker() as db:
        db.add(User(id=user_id, email=f"{user_id}@example.test"))
        await db.flush()
        for company, status in companies:
            db.add(JobApplication(user_id=user_id, company=company, role="Engineer", status=status))
        await db.commit()
    return str(user_id)


async def _statuses(maker, user_id):
    from app.models.db import JobApplication

    async with maker() as db:
        rows = await db.execute(
            select(JobApplication.company, JobApplication.status).where(
                JobApplication.user_id == uuid.UUID(user_id)
            )
        )
        return dict(rows.all())


def _mail(message_id, category, company="Acme", sender="Acme Careers <jobs@acme.com>"):
    return {
        "message_id": message_id,
        "category": category,
        "company": company,
        "sender": sender,
        "subject": f"{category} from {company}",
    }


async def test_replies_move_the_right_application_once(factory):
    from app.services.application_status_service import (
        apply_inbox_updates,
        processed_message_ids,
    )

    user = await _member(factory, ("Acme Inc", "applied"), ("Globex", "applied"))

    changes = await apply_inbox_updates(user, [_mail("m1", "INTERVIEW")])
    assert [(c["company"], c["from_status"], c["to_status"]) for c in changes] == [
        ("Acme Inc", "applied", "interview")
    ]
    assert await _statuses(factory, user) == {"Acme Inc": "interview", "Globex": "applied"}

    # The same message on a later scan changes nothing and is reported as seen.
    assert await apply_inbox_updates(user, [_mail("m1", "REJECTED")]) == []
    assert await processed_message_ids(user, ["m1", "m9"]) == {"m1"}
    assert (await _statuses(factory, user))["Acme Inc"] == "interview"

    # A later, different message can still move it, but never backwards.
    assert await apply_inbox_updates(user, [_mail("m2", "VIEWED")]) == []
    rejected = await apply_inbox_updates(user, [_mail("m3", "REJECTED")])
    assert rejected[0]["to_status"] == "rejected"
    assert await apply_inbox_updates(user, [_mail("m4", "INTERVIEW")]) == []
    assert (await _statuses(factory, user))["Acme Inc"] == "rejected"


async def test_unmatched_and_ambiguous_mail_is_recorded_but_changes_nothing(factory):
    from app.models.db import ApplicationStatusEvent
    from app.services.application_status_service import apply_inbox_updates

    user = await _member(factory, ("Acme", "applied"), ("Acme Labs", "applied"))
    stranger = _mail("m1", "INTERVIEW", company="Initech", sender="HR <hr@initech.com>")
    ambiguous = _mail("m2", "INTERVIEW")

    assert await apply_inbox_updates(user, [stranger, ambiguous]) == []

    assert await _statuses(factory, user) == {"Acme": "applied", "Acme Labs": "applied"}
    async with factory() as db:
        events = (
            (
                await db.execute(
                    select(ApplicationStatusEvent).where(
                        ApplicationStatusEvent.user_id == uuid.UUID(user)
                    )
                )
            )
            .scalars()
            .all()
        )
    assert {e.gmail_message_id for e in events} == {"m1", "m2"}
    assert all(e.job_application_id is None and e.new_status is None for e in events)


async def test_only_opted_in_members_with_gmail_are_scanned(factory):
    from app.models.db import IntegrationConnection, UserModelSettings, UserPreferences
    from app.services.application_status_service import list_inbox_tracking_users

    async def member(opted_in, gmail_status):
        user = await _member(factory)
        async with factory() as db:
            db.add(UserPreferences(user_id=uuid.UUID(user), inbox_tracking_enabled=opted_in))
            db.add(UserModelSettings(user_id=uuid.UUID(user), provider="openai", is_active=True))
            db.add(
                IntegrationConnection(
                    user_id=uuid.UUID(user),
                    provider="gmail",
                    provider_config_key="google-mail",
                    status=gmail_status,
                )
            )
            await db.commit()
        return user

    eligible = await member(True, "connected")
    not_opted_in = await member(False, "connected")
    disconnected = await member(True, "revoked")

    listed = await list_inbox_tracking_users()

    assert eligible in listed
    assert not_opted_in not in listed
    assert disconnected not in listed
