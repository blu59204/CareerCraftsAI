"""The interview history lists only the caller's sessions, newest first.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_interview_history.py.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1",
    reason="Disposable workflow infrastructure required",
)

ASYNC_URL = "postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"


@pytest.fixture
async def factory():
    from app.core.database import Base

    engine = create_async_engine(ASYNC_URL)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


async def test_history_is_scoped_to_the_member_and_newest_first(factory):
    from app.api.v1 import interview
    from app.models.db import InterviewSession, User

    now = datetime.now(UTC)
    mine = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.test")
    theirs = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@x.test")
    async with factory() as db:
        db.add_all([mine, theirs])
        await db.flush()
        db.add_all(
            [
                InterviewSession(
                    user_id=mine.id,
                    role="Older",
                    questions=[1, 2],
                    answers=[1],
                    started_at=now - timedelta(days=2),
                ),
                InterviewSession(
                    user_id=mine.id,
                    role="Newer",
                    questions=[1, 2, 3],
                    answers=[1, 2, 3],
                    scores=[80, 90, 70],
                    overall_score=80,
                    status="completed",
                    started_at=now - timedelta(days=1),
                    completed_at=now,
                ),
                InterviewSession(user_id=theirs.id, role="Not mine", started_at=now),
            ]
        )
        await db.commit()

    async with factory() as db:
        items = await interview.list_sessions(limit=30, db=db, current_user=mine)

    assert [item.role for item in items] == ["Newer", "Older"]
    assert (items[0].question_count, items[0].answered_count, items[0].overall_score) == (3, 3, 80)
    assert items[1].answered_count == 1 and items[1].overall_score is None
