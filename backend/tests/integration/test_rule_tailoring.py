"""Rule tailoring uses the same durable admission/run ledger as API agents."""

import os
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1", reason="Disposable database required"
)


@pytest.mark.asyncio
async def test_rule_tailoring_starts_one_durable_run_and_reuses_its_checkpoint(
    monkeypatch,
):
    from app.core.database import Base
    from app.models.db import AgentRun, JobApplication, User
    from app.services import auto_apply_queue as queue

    engine = create_async_engine(
        "postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(queue, "AsyncSessionLocal", maker)
    owner = uuid.uuid4()
    draft = {
        "type": "resume_ready",
        "pdf_document_id": str(uuid.uuid4()),
        "grounding": {"unsupported": []},
    }
    async with maker() as db:
        db.add(
            User(
                id=owner,
                email=f"{owner}@example.test",
                policy_accepted_at=datetime.now(UTC),
            )
        )
        await db.flush()
        application = JobApplication(
            user_id=owner,
            company="Acme",
            role="Engineer",
            job_url="https://acme.test/jobs/1",
        )
        db.add(application)
        await db.commit()

    async def start(run_id, user_id):
        async with maker() as db:
            run = await db.get(AgentRun, uuid.UUID(run_id))
            assert run.status == "queued" and run.user_id == owner
            run.status, run.output = "awaiting_approval", draft
            run.tokens_used, run.duration_ms = 123, 456
            await db.commit()

    starter = AsyncMock(side_effect=start)
    monkeypatch.setattr("app.workflows.starters.start_agent_run", starter)
    rule = {
        "since": datetime.now(UTC),
        "template": "modern",
        "page_target": 1,
        "tone": "concise",
    }
    try:
        assert await queue._tailor(str(owner), application, rule) == draft
        assert await queue._tailor(str(owner), application, rule) == draft
        starter.assert_awaited_once()
        async with maker() as db:
            runs = (
                (await db.execute(select(AgentRun).where(AgentRun.user_id == owner)))
                .scalars()
                .all()
            )
            assert len(runs) == 1
            assert runs[0].input["context"]["rule_application_id"] == str(application.id)
            assert (runs[0].tokens_used, runs[0].duration_ms) == (123, 456)
    finally:
        async with maker() as db:
            await db.execute(text("DELETE FROM users WHERE id = :id"), {"id": owner})
            await db.commit()
        await engine.dispose()
