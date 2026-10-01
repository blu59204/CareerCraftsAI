"""Saved models: re-saving replaces the old key, and one model stays active.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_model_settings_db.py.
"""

import os
import uuid

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
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


async def _user(factory):
    from app.models.db import User

    async with factory() as db:
        user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
        db.add(user)
        await db.commit()
        return user


async def _save(factory, user, provider, model_name, key):
    from app.api.v1 import users
    from app.models.schemas import ModelSettingsCreate

    payload = ModelSettingsCreate(provider=provider, api_key=key, model_name=model_name)
    async with factory() as db:
        row = await users.add_model_settings.__wrapped__(
            request=None, payload=payload, db=db, current_user=user
        )
        await db.commit()
        return row.id


async def _rows(factory, user):
    from app.models.db import UserModelSettings

    async with factory() as db:
        result = await db.execute(
            select(UserModelSettings).where(UserModelSettings.user_id == user.id)
        )
        return result.scalars().all()


async def test_resaving_a_model_replaces_its_key_and_keeps_one_active(factory):
    from app.api.v1 import users

    user = await _user(factory)
    first = await _save(factory, user, "openai", "gpt-4o", "sk-old-key-000000")
    other = await _save(factory, user, "anthropic", "claude", "sk-ant-key-00000")
    latest = await _save(factory, user, "openai", "gpt-4o", "sk-new-key-000000")

    rows = await _rows(factory, user)
    assert {row.id for row in rows} == {other, latest}  # the old gpt-4o key is gone
    assert [row.id for row in rows if row.is_active] == [latest]
    assert first not in {row.id for row in rows}

    async with factory() as db:
        await users.activate_model(model_id=str(other), db=db, current_user=user)
        await db.commit()
    assert [row.id for row in await _rows(factory, user) if row.is_active] == [other]


async def test_the_database_rejects_a_second_active_model(factory):
    user = await _user(factory)
    await _save(factory, user, "openai", "gpt-4o", "sk-key-0000000000")
    async with factory() as db:
        with pytest.raises(IntegrityError):
            await db.execute(
                text(
                    "INSERT INTO user_model_settings (id, user_id, provider, is_active)"
                    " VALUES (:id, :uid, 'google', true)"
                ),
                {"id": uuid.uuid4(), "uid": user.id},
            )
