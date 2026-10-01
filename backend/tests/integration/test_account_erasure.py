"""The deletion sweep erases what the users cascade cannot reach.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_account_erasure.py.
"""

import os
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1",
    reason="Disposable workflow infrastructure required",
)

ASYNC_URL = "postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"

_UNLINKED_DDL = [
    "CREATE TABLE IF NOT EXISTS agent_memory_episodes (id serial PRIMARY KEY, user_id text)",
    "CREATE TABLE IF NOT EXISTS agent_memory_learnings (id serial PRIMARY KEY, user_id text)",
    "CREATE TABLE IF NOT EXISTS agent_memory_preferences (id serial PRIMARY KEY, user_id text)",
    "CREATE TABLE IF NOT EXISTS agent_memory_procedures (id serial PRIMARY KEY, user_id text)",
    "CREATE TABLE IF NOT EXISTS langchain_pg_collection (uuid uuid PRIMARY KEY, name text)",
    "CREATE TABLE IF NOT EXISTS langchain_pg_embedding"
    " (id text PRIMARY KEY, collection_id uuid REFERENCES langchain_pg_collection(uuid))",
]


@pytest.fixture
async def database(monkeypatch, tmp_path):
    import app.core.database as core_database
    from app.core.config import settings
    from app.core.database import Base

    engine = create_async_engine(ASYNC_URL)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        for statement in _UNLINKED_DDL:
            await connection.execute(text(statement))
    monkeypatch.setattr(core_database, "AsyncSessionLocal", factory)
    monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path))
    yield factory
    await engine.dispose()


async def _seed(factory, tmp_path):
    from app.models.db import AgentRun, User

    user_id = uuid.uuid4()
    async with factory() as db:
        db.add(
            User(
                id=user_id,
                email=f"{user_id}@example.test",
                clerk_user_id=f"user_{user_id.hex[:8]}",
                deletion_requested_at=datetime.now(UTC) - timedelta(days=16),
                deletion_scheduled_for=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await db.flush()
        db.add(AgentRun(id=uuid.uuid4(), user_id=user_id, agent_type="email", status="running"))
        collection = uuid.uuid4()
        await db.execute(
            text("INSERT INTO langchain_pg_collection VALUES (:id, :name)"),
            {"id": collection, "name": f"{user_id}_resume_openai_1536d"},
        )
        await db.execute(
            text("INSERT INTO langchain_pg_embedding VALUES (:id, :collection)"),
            {"id": str(uuid.uuid4()), "collection": collection},
        )
        await db.execute(
            text("INSERT INTO agent_memory_episodes (user_id) VALUES (:uid)"), {"uid": str(user_id)}
        )
        await db.commit()
    folder = tmp_path / str(user_id)
    folder.mkdir()
    (folder / "resume.pdf").write_bytes(b"%PDF")
    return user_id


async def _remaining(factory, user_id):
    async with factory() as db:
        return {
            "user": await db.scalar(
                text("SELECT count(*) FROM users WHERE id = :id"), {"id": user_id}
            ),
            "runs": await db.scalar(
                text("SELECT count(*) FROM agent_runs WHERE user_id = :id"), {"id": user_id}
            ),
            "collections": await db.scalar(
                text("SELECT count(*) FROM langchain_pg_collection WHERE name LIKE :p"),
                {"p": f"{user_id}%"},
            ),
            "memory": await db.scalar(
                text("SELECT count(*) FROM agent_memory_episodes WHERE user_id = :id"),
                {"id": str(user_id)},
            ),
        }


async def test_sweep_erases_everything_then_the_account(database, monkeypatch, tmp_path):
    from app.services import account_deletion_service as service

    user_id = await _seed(database, tmp_path)
    other = await _seed(database, tmp_path)  # a second member must be untouched
    async with database() as db:
        await db.execute(
            text("UPDATE users SET deletion_scheduled_for = NULL WHERE id = :id"), {"id": other}
        )
        await db.commit()

    terminated = []

    class Handle:
        def __init__(self, workflow_id):
            self.workflow_id = workflow_id

        async def terminate(self, reason):
            terminated.append(self.workflow_id)

    client = type("Client", (), {"get_workflow_handle": lambda self, wid: Handle(wid)})()
    monkeypatch.setattr(
        "app.core.temporal_client.get_temporal_client", AsyncMock(return_value=client)
    )
    monkeypatch.setattr(service, "_revoke_integrations", AsyncMock())
    monkeypatch.setattr(service, "_delete_redis_keys", AsyncMock())
    clerk = AsyncMock()
    monkeypatch.setattr("app.core.clerk_auth.delete_clerk_user", clerk)

    async with database() as db:
        removed = await service.reap_expired_account_deletions(db)
        await db.commit()

    assert removed == 1
    assert len(terminated) == 1  # the running agent run
    clerk.assert_awaited_once_with(f"user_{user_id.hex[:8]}", strict=True)
    assert await _remaining(database, user_id) == {
        "user": 0,
        "runs": 0,
        "collections": 0,
        "memory": 0,
    }
    assert not (tmp_path / str(user_id)).exists()
    assert await _remaining(database, other) == {
        "user": 1,
        "runs": 1,
        "collections": 1,
        "memory": 1,
    }
    assert (tmp_path / str(other)).exists()
