"""Resume facts and resume pin lookups against a real, migrated PostgreSQL.

Covers what the unit fakes cannot: row locks, savepoints, the unique
(user_id, question_key) constraint and the JSONB pin conditions. Run against
a disposable database with deploy/oracle-vm/postgres-bootstrap.sql and
supabase/migrations/*.sql applied:

    INTEGRATION=1 DATABASE_URL=postgresql+asyncpg://... \
        pytest tests/integration/test_resume_facts_pg.py

Every row is created for throwaway users that are deleted afterwards.
"""

import asyncio
import os
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL", "")

pytestmark = pytest.mark.skipif(
    os.getenv("INTEGRATION") != "1" or not DATABASE_URL.startswith("postgresql"),
    reason="Set INTEGRATION=1 and DATABASE_URL to a migrated, disposable PostgreSQL",
)

# How long a statement must stay blocked to count as waiting on a lock.
_BLOCKED_FOR = 0.5

EXPERIENCE = {"role": "SE", "employer_match": "Acme", "start": "2020", "submitted": ["start"]}


@pytest.fixture
async def factory():
    engine = create_async_engine(DATABASE_URL, poolclass=NullPool)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
async def make_user(factory):
    from app.models.db import User

    created: list[uuid.UUID] = []

    async def _make():
        user = User(id=uuid.uuid4(), email=f"facts-{uuid.uuid4().hex}@example.test")
        async with factory() as db:
            db.add(user)
            await db.commit()
        created.append(user.id)
        return user

    yield _make
    async with factory() as db:
        # Cascades to documents, applications, attempts, runs and answers.
        await db.execute(delete(User).where(User.id.in_(created)))
        await db.commit()


async def _add(factory, *rows):
    async with factory() as db:
        db.add_all(rows)
        await db.commit()
    return rows


def _tailored_doc(user):
    from app.models.db import UserDocument

    return UserDocument(
        id=uuid.uuid4(),
        user_id=user.id,
        doc_type="resume_tailored",
        filename="resume.pdf",
        storage_path=f"{user.id}/resume.pdf",
        raw_text="# Jane Doe\n",
        ats_data={"template": "modern"},
    )


async def _stays_blocked(task: asyncio.Task) -> bool:
    await asyncio.sleep(_BLOCKED_FOR)
    return not task.done()


# ── save_facts ───────────────────────────────────────────────────────────────


async def test_conflicting_first_save_merges_into_the_winner_and_keeps_pending_changes(
    factory, make_user
):
    from app.models.db import UserDocument
    from app.services.resume_facts import load_facts_row, save_facts

    user = await make_user()
    [doc] = await _add(factory, _tailored_doc(user))

    async with factory() as winner, factory() as loser:
        await save_facts(winner, user.id, contact={"phone": "+91 1"}, experience=[], education=[])

        # The loser has its own pending change (the fixed document) in the
        # same transaction; the failed insert must only roll back itself.
        pending = await loser.get(UserDocument, doc.id)
        pending.raw_text = "# Jane Doe\njane@example.test\n"
        await loser.flush()
        task = asyncio.create_task(
            save_facts(
                loser,
                user.id,
                contact={"email": "jane@example.test"},
                experience=[EXPERIENCE],
                education=[],
            )
        )
        # Blocked on the unique index until the winner's insert commits.
        assert await _stays_blocked(task)
        await winner.commit()
        stored = await task
        await loser.commit()

    async with factory() as db:
        row = await load_facts_row(db, user.id)
        assert row.answer == stored
        assert row.answer["contact"] == {"phone": "+91 1", "email": "jane@example.test"}
        assert row.answer["experience"] == [EXPERIENCE]
        assert row.approved_by_user is True
        assert (await db.get(UserDocument, doc.id)).raw_text == "# Jane Doe\njane@example.test\n"


async def test_concurrent_saves_of_an_existing_row_both_land(factory, make_user):
    from app.services.resume_facts import load_facts_row, save_facts

    user = await make_user()
    async with factory() as db:
        await save_facts(db, user.id, contact={"phone": "+91 1"}, experience=[], education=[])
        await db.commit()

    education = [{"degree": "B.Tech", "institution": "SPPU"}]
    async with factory() as first, factory() as second:
        await save_facts(first, user.id, contact=None, experience=[EXPERIENCE], education=[])
        task = asyncio.create_task(
            save_facts(second, user.id, contact=None, experience=[], education=education)
        )
        # Waits on the first save's row lock instead of reading stale facts.
        assert await _stays_blocked(task)
        await first.commit()
        await task
        await second.commit()

    async with factory() as db:
        answer = (await load_facts_row(db, user.id)).answer
    assert answer["contact"] == {"phone": "+91 1"}
    assert answer["experience"] == [EXPERIENCE]
    assert answer["education"] == education


async def test_fix_document_lookup_serialises_concurrent_fixes(factory, make_user):
    from app.api.v1.resume import _get_tailored_doc

    user = await make_user()
    [doc] = await _add(factory, _tailored_doc(user))
    owner = SimpleNamespace(id=user.id)

    async with factory() as first, factory() as second:
        await _get_tailored_doc(first, str(doc.id), owner, for_update=True)
        # A plain read (GET) is never blocked by the lock.
        assert (await _get_tailored_doc(second, str(doc.id), owner)).id == doc.id
        task = asyncio.create_task(_get_tailored_doc(second, str(doc.id), owner, for_update=True))
        assert await _stays_blocked(task)
        await first.commit()
        assert (await task).id == doc.id
        await second.rollback()


# ── Pending-approval pins ────────────────────────────────────────────────────


async def _attempt(factory, user, doc, *, state, run_status):
    """An application of ``user`` using ``doc``, with its attempt and run."""
    from app.models.db import AgentRun, ApplicationAttempt, JobApplication

    run = AgentRun(id=uuid.uuid4(), user_id=user.id, agent_type="apply_prepare", status=run_status)
    application = JobApplication(
        id=uuid.uuid4(), user_id=user.id, company="Acme", role="SE", resume_id=doc.id
    )
    await _add(factory, run, application)
    attempt = ApplicationAttempt(
        id=uuid.uuid4(),
        user_id=user.id,
        job_application_id=application.id,
        run_id=run.id,
        state=state,
    )
    await _add(factory, attempt)
    return attempt


async def _checkpoint(factory, user, output, status="awaiting_approval"):
    from app.models.db import AgentRun

    await _add(
        factory,
        AgentRun(
            id=uuid.uuid4(),
            user_id=user.id,
            agent_type="apply_prepare",
            status=status,
            output=output,
        ),
    )


async def _pinned(factory, doc) -> bool:
    from app.api.v1.resume import _pinned_by_pending_approval

    async with factory() as db:
        return await _pinned_by_pending_approval(db, doc)


async def test_only_the_owners_open_attempt_pins_the_resume(factory, make_user):
    owner, other = await make_user(), await make_user()
    [doc] = await _add(factory, _tailored_doc(owner))
    assert await _pinned(factory, doc) is False

    # Another user's in-flight application naming this document.
    await _attempt(factory, other, doc, state="awaiting_approval", run_status="awaiting_approval")
    # The owner's abandoned attempts: approval expired by the reaper, a
    # rejected browser_input checkpoint (attempt left "preparing"), and a
    # finished application.
    await _attempt(factory, owner, doc, state="awaiting_approval", run_status="expired")
    await _attempt(factory, owner, doc, state="preparing", run_status="failed")
    await _attempt(factory, owner, doc, state="verified", run_status="completed")
    assert await _pinned(factory, doc) is False

    await _attempt(factory, owner, doc, state="awaiting_approval", run_status="awaiting_approval")
    assert await _pinned(factory, doc) is True


async def test_only_the_owners_awaiting_checkpoint_pins_the_resume(factory, make_user):
    owner, other = await make_user(), await make_user()
    review_doc, pipeline_doc = await _add(factory, _tailored_doc(owner), _tailored_doc(owner))
    review = {"type": "browser_review", "pdf_document_id": str(review_doc.id)}
    pipeline = {"actions_pending": [{"type": "apply", "pdf_document_id": str(pipeline_doc.id)}]}

    await _checkpoint(factory, other, {**review, "resume_sha256": "abc"})
    await _checkpoint(factory, other, pipeline)
    await _checkpoint(factory, owner, {**review, "resume_sha256": "abc"}, status="expired")
    await _checkpoint(factory, owner, pipeline, status="failed")
    # A checkpoint naming the document without its sha has not pinned it.
    await _checkpoint(factory, owner, review)
    assert await _pinned(factory, review_doc) is False
    assert await _pinned(factory, pipeline_doc) is False

    await _checkpoint(factory, owner, {**review, "resume_sha256": "abc"})
    await _checkpoint(factory, owner, pipeline)
    assert await _pinned(factory, review_doc) is True
    assert await _pinned(factory, pipeline_doc) is True
