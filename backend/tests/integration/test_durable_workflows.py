"""Real PostgreSQL/Redis and Chromium checks on disposable test services only.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_durable_workflows.py.
Never reads deployment credentials or uses the application's production database.
"""
import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(os.getenv("RUN_WORKFLOW_INTEGRATION") != "1", reason="Disposable workflow infrastructure required")


@pytest.fixture
async def database(monkeypatch):
    from app.core.database import Base
    from app.services import workflow_service, sandbox_service, application_workflow
    engine = create_async_engine("postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test")
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
        await connection.execute(text("CREATE UNIQUE INDEX IF NOT EXISTS workflow_tasks_one_active_stage ON workflow_tasks (run_id) WHERE status IN ('pending', 'dispatched', 'running')"))
    for module in (workflow_service, sandbox_service, application_workflow):
        monkeypatch.setattr(module, "AsyncSessionLocal", factory)
    monkeypatch.setattr(workflow_service, "publish", lambda *args: None)
    yield factory
    await engine.dispose()


async def new_run(factory, status="queued"):
    from app.models.db import User, AgentRun
    async with factory() as db:
        user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
        db.add(user)
        await db.flush()
        run = AgentRun(id=uuid.uuid4(), user_id=user.id, agent_type="resume_optimize", status=status, input={"context": {}})
        db.add(run)
        await db.commit()
        return user, run


@pytest.mark.asyncio
async def test_restart_duplicate_delivery_and_approval(database):
    from app.models.db import AgentRun, WorkflowTask
    from app.services.workflow_service import add_task, execute_task
    user, run = await new_run(database)
    async with database() as db:
        task = add_task(db, run, "execute", {})
        await db.commit()
        task_id = str(task.id)
    # This uses a fresh DB session, like a worker starting after the API exits.
    execute = AsyncMock(return_value={"status": "awaiting_approval", "pending_action": {"type": "resume_ready", "resume_markdown": "review me"}})
    with patch("app.services.workflow_service.execute_agent", execute):
        await asyncio.gather(execute_task(task_id), execute_task(task_id))
    assert execute.await_count == 1
    async with database() as db:
        saved = await db.get(AgentRun, run.id)
        assert saved.status == "awaiting_approval"
        assert saved.completed_at is None
        saved.status = "queued"
        resume = add_task(db, saved, "continue", saved.output)
        await db.commit()
    await execute_task(str(resume.id))
    async with database() as db:
        saved = await db.get(AgentRun, run.id)
        assert saved.status == "completed"
        assert saved.output["reviewed"] is True


@pytest.mark.asyncio
async def test_worker_loss_is_not_a_duplicate_submission(database):
    from app.models.db import AgentRun, WorkflowTask
    from app.services.workflow_service import add_task, execute_task, recover_expired_tasks
    _, run = await new_run(database, "running")
    async with database() as db:
        task = add_task(db, run, "continue", {"type": "send_email"})
        task.status = "running"
        task.lease_until = datetime.now(timezone.utc) - timedelta(seconds=1)
        await db.commit()
    await recover_expired_tasks()
    with patch("app.services.workflow_service.continue_action", AsyncMock()) as action:
        await execute_task(str(task.id))
        action.assert_not_awaited()
    async with database() as db:
        saved = await db.get(AgentRun, run.id)
        assert saved.status == "failed"
        assert saved.output["outcome"] == "unknown"


@pytest.mark.asyncio
async def test_lease_recovery_covers_missing_lease(database):
    from app.models.db import AgentRun
    from app.services.workflow_service import add_task, execute_task, recover_expired_tasks
    _, run = await new_run(database, "running")
    async with database() as db:
        task = add_task(db, run, "continue", {"type": "send_email"})
        task.status = "running"
        task.lease_until = None
        await db.commit()
        task_id = str(task.id)
    await recover_expired_tasks()
    with patch("app.services.workflow_service.continue_action", AsyncMock()) as action:
        await execute_task(task_id)
        action.assert_not_awaited()
    async with database() as db:
        saved = await db.get(AgentRun, run.id)
        assert saved.status == "failed"
        assert saved.output["outcome"] == "unknown"


@pytest.mark.asyncio
async def test_bullmq_outbox_delivery(database):
    from bullmq import Queue, Worker
    from app.services.workflow_service import add_task, dispatch_pending, execute_task
    from app.models.db import AgentRun
    _, run = await new_run(database)
    async with database() as db:
        task = add_task(db, run, "continue", {"type": "resume_ready", "resume_markdown": "approved"})
        await db.commit()
    name = f"test-{uuid.uuid4()}"
    options = {"connection": {"host": "127.0.0.1", "port": 56379}}
    queue = Queue(name, options)
    done = asyncio.Event()

    async def process(job, token):
        await execute_task(job.data["task_id"])
        if job.data["task_id"] == str(task.id):
            done.set()

    worker = Worker(name, process, options)
    try:
        await dispatch_pending(queue)
        await asyncio.wait_for(done.wait(), timeout=20)
        async with database() as db:
            assert (await db.get(AgentRun, run.id)).status == "completed"
    finally:
        await worker.close()
        await queue.close()


@pytest.mark.asyncio
async def test_live_browser_form_snapshot_and_single_submit(database, monkeypatch):
    from playwright.async_api import async_playwright
    from app.models.db import BrowserSession, UserDocument
    from app.services import application_workflow as workflow
    from app.services.sandbox_service import OpenSandboxProvider
    from app.core.config import settings
    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.test")
    monkeypatch.setattr(OpenSandboxProvider, "endpoint", AsyncMock(return_value=("http://127.0.0.1:59222", {})))
    _, run = await new_run(database)
    session = BrowserSession(id=uuid.uuid4(), run_id=run.id, user_id=run.user_id, sandbox_id="test-browser", status="ready", expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))
    document_id = uuid.uuid4()
    async with database() as db:
        db.add(session)
        db.add(UserDocument(id=document_id, user_id=run.user_id, doc_type="resume", filename="resume.pdf", storage_path=f"{run.user_id}/resume.pdf"))
        await db.commit()
    monkeypatch.setattr(workflow, "acquire_session", AsyncMock(return_value=session))
    monkeypatch.setattr(workflow, "fill_known_fields", AsyncMock())
    monkeypatch.setattr(workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", "hash")))
    monkeypatch.setattr(workflow, "save_account_state", AsyncMock())
    async with async_playwright() as p:
        ws, headers = await OpenSandboxProvider().cdp("test-browser")
        browser = await p.chromium.connect_over_cdp(ws)
        page = browser.contexts[0].pages[-1]
        html = '''<label>Email<input name=email required value="me@example.test"></label>
        <input type=file required><button onclick="window.submits=(window.submits||0)+1;document.body.innerHTML='Thank you for applying'">Submit application</button>'''
        await page.route("https://jobs.example.test/**", lambda route: route.fulfill(body=html, content_type="text/html"))
        pending = {"type": "browser_prepare", "job_url": "https://jobs.example.test/apply", "pdf_document_id": str(document_id)}
        prepared = await workflow.run_application_stage(run, pending)
        assert prepared["pending_action"]["type"] == "browser_review"
        assert await page.evaluate("window.submits || 0") == 0
        # A changed form invalidates approval, and must not click submit.
        await page.locator("input[name=email]").fill("changed@example.test")
        changed = await workflow.run_application_stage(run, prepared["pending_action"])
        assert changed["pending_action"]["type"] == "browser_input"
        assert await page.evaluate("window.submits || 0") == 0
        reviewed = await workflow.run_application_stage(run, changed["pending_action"])
        submitted = await workflow.run_application_stage(run, reviewed["pending_action"])
        assert submitted["result"]["outcome"] == "submitted"
        assert await page.evaluate("window.submits") == 1


@pytest.mark.asyncio
async def test_browser_ownership_is_enforced(database):
    from app.api.v1.browser import owned_session
    from fastapi import HTTPException
    user, run = await new_run(database, "awaiting_approval")
    stranger, _ = await new_run(database)
    async with database() as db:
        with pytest.raises(HTTPException) as exc:
            await owned_session(db, stranger, run.id)
        assert exc.value.status_code == 404
