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
    import psycopg
    from psycopg import sql

    import app.core.database as core_database
    from app.core.config import settings
    from app.core.database import Base

    # Keep erasure tests independent of older fixtures and vector-table schemas.
    # This named database belongs only to this test; never drop workflow_test.
    database_name = "account_erasure_test_" + uuid.uuid4().hex
    admin_url = "postgresql://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"
    with psycopg.connect(admin_url, autocommit=True) as admin:
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name)))
    engine = create_async_engine(ASYNC_URL.rsplit("/", 1)[0] + "/" + database_name)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            for statement in _UNLINKED_DDL:
                await connection.execute(text(statement))
        monkeypatch.setattr(core_database, "AsyncSessionLocal", factory)
        monkeypatch.setattr(settings, "DOCUMENT_STORAGE_DIR", str(tmp_path))
        yield factory
    finally:
        await engine.dispose()
        with psycopg.connect(admin_url, autocommit=True) as admin:
            admin.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(database_name))
            )


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
        db.add(
            AgentRun(
                id=uuid.uuid5(user_id, "run"), user_id=user_id, agent_type="email", status="running"
            )
        )
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

    # Prove this owner was swept and the non-expired owner was untouched.
    from app.workflows.agent_run import agent_run_workflow_id

    assert removed == 1
    assert agent_run_workflow_id(str(uuid.uuid5(user_id, "run"))) in terminated
    assert agent_run_workflow_id(str(uuid.uuid5(other, "run"))) not in terminated
    clerk.assert_any_await(f"user_{user_id.hex[:8]}", strict=True)
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


async def test_database_cascade_erases_loaded_preferences_and_application_relationships(
    database, monkeypatch
):
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload

    from app.models.db import JobApplication, User, UserDocument, UserPreferences
    from app.services import account_deletion_service as service

    owner = uuid.uuid4()
    async with database() as db:
        db.add(
            User(
                id=owner,
                email=f"{owner}@example.test",
                deletion_scheduled_for=datetime.now(UTC) - timedelta(days=1),
            )
        )
        await db.flush()
        db.add(UserPreferences(user_id=owner))
        db.add(JobApplication(user_id=owner, company="Synthetic", role="Engineer"))
        db.add(
            UserDocument(
                user_id=owner,
                doc_type="resume",
                filename="resume.pdf",
                storage_path=f"{owner}/resume.pdf",
            )
        )
        await db.commit()
    # External effects are mocked; real Postgres owns every child cascade.
    monkeypatch.setattr(service, "erase_external_data", AsyncMock())
    async with database() as db:
        account = (
            await db.execute(
                select(User)
                .where(User.id == owner)
                .options(
                    selectinload(User.preferences),
                    selectinload(User.applications),
                    selectinload(User.documents),
                )
            )
        ).scalar_one()
        assert account.preferences is not None and len(account.applications) == 1
        assert await service.reap_expired_account_deletions(db) == 1
        await db.commit()
    async with database() as db:
        assert await db.get(User, owner) is None
        for model in (UserPreferences, JobApplication, UserDocument):
            assert (await db.execute(select(model).where(model.user_id == owner))).first() is None
