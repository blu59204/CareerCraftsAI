"""Applications list contract against a real migrated Postgres: soft delete,
restore, dedupe seeing deleted rows, filters/pagination, and the B8 job
description fallback to the shared catalog.

    APPLICATIONS_DB_URL=postgresql+asyncpg://careercraft:<pw>@127.0.0.1:18132/careercraft
"""

import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

DB_URL = os.getenv("APPLICATIONS_DB_URL")
pytestmark = pytest.mark.skipif(not DB_URL, reason="APPLICATIONS_DB_URL not set")


@pytest.fixture
async def ctx():
    from app.models.db import User

    engine = create_async_engine(DB_URL)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
    async with maker() as db:
        db.add(user)
        await db.commit()
    yield maker, user
    async with maker() as db:
        await db.execute(text("DELETE FROM job_catalog WHERE url LIKE 'https://jobs.test/%'"))
        await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": user.id})
        await db.commit()
    await engine.dispose()


async def _list(db, user, response=None, **kw):
    """Call the endpoint directly with plain defaults (not FastAPI Query objects)."""
    from app.api.v1.jobs import list_applications

    params = {
        "status": None, "location": None, "source": None, "posted_within_days": None,
        "min_match": None, "found_after": None, "found_before": None, "sort": None,
        "offset": 0, "limit": None,
    }
    params.update(kw)
    return await list_applications(response or Response(), db=db, current_user=user, **params)


async def _app(maker, user, **kw):
    from app.models.db import JobApplication

    row = JobApplication(
        user_id=user.id,
        company=kw.pop("company", "Acme"),
        role=kw.pop("role", "Engineer"),
        job_url=kw.pop("job_url", f"https://jobs.test/{uuid.uuid4()}"),
        **kw,
    )
    async with maker() as db:
        db.add(row)
        await db.commit()
    return row


async def test_soft_delete_hides_rows_everywhere_but_dedupe_and_restore(ctx):
    from app.api.v1.jobs import ApplicationIdsBody, delete_applications, restore_applications
    from app.models.db import ActionLog, JobApplication

    maker, user = ctx
    keep = await _app(maker, user, match_score=90)
    gone = await _app(maker, user, match_score=40)

    async with maker() as db:
        await delete_applications(ApplicationIdsBody(ids=[gone.id]), db, user)

    async with maker() as db:
        resp = Response()
        rows = await _list(db, user, resp)
        assert [r.id for r in rows] == [keep.id]
        assert resp.headers["X-Total-Count"] == "1"
        # Aggregates (dashboard stats) see the same rows.
        count = await db.scalar(
            select(func.count())
            .select_from(JobApplication)
            .where(JobApplication.user_id == user.id)
        )
        assert count == 1
        # Dedupe checks opt in, so a deleted job isn't re-saved by the next search.
        seen = await db.scalar(
            select(JobApplication.id)
            .where(JobApplication.job_url == gone.job_url)
            .execution_options(include_deleted=True)
        )
        assert seen == gone.id
        logged = await db.scalar(
            select(func.count()).select_from(ActionLog).where(ActionLog.user_id == user.id)
        )
        assert logged == 1

    async with maker() as db:
        await restore_applications(ApplicationIdsBody(ids=[gone.id]), db, user)
    async with maker() as db:
        rows = await _list(db, user)
        assert {r.id for r in rows} == {keep.id, gone.id}


async def test_filters_sort_and_pagination(ctx):
    maker, user = ctx
    now = datetime.now(UTC)
    old = await _app(maker, user, match_score=85, found_at=now - timedelta(days=20))
    new = await _app(maker, user, match_score=75, found_at=now - timedelta(hours=1))
    await _app(maker, user, match_score=30, found_at=now)

    async with maker() as db:
        resp = Response()
        rows = await _list(db, user, resp, min_match=70, sort="found_desc", limit=1)
        assert [r.id for r in rows] == [new.id]
        assert resp.headers["X-Total-Count"] == "2"
        rows = await _list(db, user, min_match=70, found_after=now - timedelta(days=7))
        assert [r.id for r in rows] == [new.id]
        rows = await _list(db, user, sort="match_desc", offset=1, limit=5)
        assert [r.match_score for r in rows] == [75, 30]
        assert old.id not in [r.id for r in rows]


async def test_job_description_falls_back_to_catalog(ctx):
    """B8: 'Customize resume' must get a JD even when the saved row has none
    or only the 4000-char truncated copy."""
    from app.api.v1.jobs import get_application_jd

    maker, user = ctx
    url = f"https://jobs.test/{uuid.uuid4()}"
    full = "Build distributed systems. " * 400  # > 4000 chars
    async with maker() as db:
        await db.execute(
            text(
                "INSERT INTO job_catalog(job_id, url, title, company, data) "
                "VALUES (:id, :url, 'Engineer', 'Acme', CAST(:data AS jsonb))"
            ),
            {"id": uuid.uuid4().hex, "url": url, "data": json.dumps({"description": full})},
        )
        await db.commit()

    truncated = await _app(maker, user, job_url=url, jd_text=full[:4000])
    empty = await _app(maker, user, job_url=url, jd_text=None)
    own = await _app(maker, user, jd_text="Our own JD")
    missing = await _app(maker, user, jd_text="")

    async with maker() as db:
        for row in (truncated, empty):
            jd = await get_application_jd(row.id, db, user)
            assert jd.jd_text == full.strip() and jd.source == "catalog"
        jd = await get_application_jd(own.id, db, user)
        assert jd.jd_text == "Our own JD" and jd.source == "application"
        with pytest.raises(HTTPException) as err:
            await get_application_jd(missing.id, db, user)
        assert err.value.status_code == 404
        # Another member can't read it.
        from app.models.db import User

        with pytest.raises(HTTPException):
            await get_application_jd(own.id, db, User(id=uuid.uuid4(), email="x@example.test"))


async def test_activate_resume_keeps_exactly_one_primary(ctx, monkeypatch):
    """E1/E3: switching the active resume is atomic (unique index) and
    re-scores the new one so every page reads the same ats_score."""
    import app.core.background as background
    from app.api.v1.rag import activate_resume
    from app.models.db import UserDocument

    maker, user = ctx
    rescored = []
    monkeypatch.setattr(background, "spawn_background", lambda coro: rescored.append(coro.close()))
    a = UserDocument(user_id=user.id, doc_type="resume", filename="a.pdf", storage_path="a",
                     raw_text="A", is_primary=True)
    b = UserDocument(user_id=user.id, doc_type="resume", filename="b.pdf", storage_path="b",
                     raw_text="B", is_primary=False)
    async with maker() as db:
        db.add_all([a, b])
        await db.commit()
    async with maker() as db:
        out = await activate_resume(b.id, db, user)
        assert out.is_primary
    async with maker() as db:
        primaries = (
            await db.execute(
                select(UserDocument.id).where(
                    UserDocument.user_id == user.id, UserDocument.is_primary.is_(True)
                )
            )
        ).scalars().all()
        assert primaries == [b.id]
    assert len(rescored) == 1


async def test_live_write_through_is_shared_and_keeps_fuller_description(ctx, monkeypatch):
    """A2/A3: a job one member's live search found lands in the shared catalog
    for everyone; a later thinner sighting never erases the full description."""
    import app.services.job_catalog as catalog

    maker, _ = ctx
    monkeypatch.setattr(catalog, "AsyncSessionLocal", maker)
    url = f"https://jobs.test/{uuid.uuid4()}"
    full = "Own the payments platform end to end. " * 50
    base = {"url": url, "title": "Backend Engineer", "company": "Acme", "location": "Remote"}

    assert await catalog.write_through([{**base, "description": full}], "jobspy") == 1
    assert await catalog.write_through([{**base, "description": "Short snippet"}], "jobspy") == 1
    async with maker() as db:
        stored = await db.scalar(
            text("SELECT data->>'description' FROM job_catalog WHERE url = :u"), {"u": url}
        )
        sources = (
            await db.execute(
                text(
                    "SELECT o.source_id FROM job_source_occurrences o "
                    "JOIN job_catalog c USING (job_id) WHERE c.url = :u"
                ),
                {"u": url},
            )
        ).scalars().all()
    assert stored.strip() == full.strip()
    assert sources == ["live:jobspy"]
