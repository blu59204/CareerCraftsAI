"""Real PostgreSQL/Redis and Chromium checks on disposable test services only.

Run docker compose -p careercraft-workflow-tests -f docker-compose.test.yml up -d
then RUN_WORKFLOW_INTEGRATION=1 pytest tests/integration/test_durable_workflows.py.
Never reads deployment credentials or uses the application's production database.
"""

import asyncio
import os
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_WORKFLOW_INTEGRATION") != "1",
    reason="Disposable workflow infrastructure required",
)


@pytest.fixture
async def database(monkeypatch):
    import app.core.database as core_database
    from app.core.database import Base
    from app.services import application_workflow, sandbox_service, workflow_service

    engine = create_async_engine(
        "postgresql+asyncpg://workflow_test:workflow_test@127.0.0.1:55439/workflow_test"
    )
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    for module in (workflow_service, sandbox_service, application_workflow, core_database):
        monkeypatch.setattr(module, "AsyncSessionLocal", factory)
    monkeypatch.setattr("app.core.event_bus.publish", lambda *args: None)
    yield factory
    await engine.dispose()


async def new_run(factory, status="queued"):
    from app.models.db import User, AgentRun

    async with factory() as db:
        user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
        db.add(user)
        await db.flush()
        run = AgentRun(
            id=uuid.uuid4(),
            user_id=user.id,
            agent_type="resume_optimize",
            status=status,
            input={"context": {}},
        )
        db.add(run)
        await db.commit()
        return user, run


async def _agent_worker(env):
    from temporalio.worker import Worker

    from app.workflows.agent_activities import (
        continue_agent_run_activity,
        execute_agent_run_activity,
        expire_agent_run_activity,
    )
    from app.workflows.agent_run import AgentRunWorkflow

    return Worker(
        env.client,
        task_queue="it-agent-runs",
        workflows=[AgentRunWorkflow],
        activities=[
            execute_agent_run_activity,
            continue_agent_run_activity,
            expire_agent_run_activity,
        ],
    )


@pytest.mark.asyncio
async def test_duplicate_start_runs_once_and_approval_continues(database):
    """Two starts for one run execute the agent once; the approval arrives
    by signal-with-start and the continuation completes the run."""
    from temporalio.exceptions import WorkflowAlreadyStartedError
    from temporalio.testing import WorkflowEnvironment

    from app.models.db import AgentRun
    from app.workflows.agent_run import (
        AgentRunInput,
        AgentRunWorkflow,
        ApprovalDecision,
        agent_run_workflow_id,
    )

    _, run = await new_run(database)
    execute = AsyncMock(
        return_value={
            "status": "awaiting_approval",
            "pending_action": {"type": "resume_ready", "resume_markdown": "review me"},
        }
    )
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with await _agent_worker(env):
            with patch("app.services.workflow_service.execute_agent", execute):
                workflow_id = agent_run_workflow_id(str(run.id))
                handle = await env.client.start_workflow(
                    AgentRunWorkflow.run,
                    AgentRunInput(run_id=str(run.id), user_id=str(run.user_id)),
                    id=workflow_id,
                    task_queue="it-agent-runs",
                )
                with pytest.raises(WorkflowAlreadyStartedError):
                    await env.client.start_workflow(
                        AgentRunWorkflow.run,
                        AgentRunInput(run_id=str(run.id), user_id=str(run.user_id)),
                        id=workflow_id,
                        task_queue="it-agent-runs",
                    )
                for _ in range(200):
                    if await handle.query(AgentRunWorkflow.status) == "awaiting_approval":
                        break
                    await asyncio.sleep(0.02)
                async with database() as db:
                    saved = await db.get(AgentRun, run.id)
                    assert saved.status == "awaiting_approval"
                    assert saved.completed_at is None
                    saved.status = "queued"  # what the approve endpoint does
                    continuation = saved.output
                    await db.commit()
                await env.client.start_workflow(
                    AgentRunWorkflow.run,
                    AgentRunInput(
                        run_id=str(run.id), user_id=str(run.user_id), start_at_checkpoint=True
                    ),
                    id=workflow_id,
                    task_queue="it-agent-runs",
                    start_signal="decide",
                    start_signal_args=[ApprovalDecision(approved=True, continuation=continuation)],
                )
                result = await handle.result()

    assert execute.await_count == 1
    assert result["status"] == "completed"
    async with database() as db:
        saved = await db.get(AgentRun, run.id)
        assert saved.status == "completed"
        assert saved.output["reviewed"] is True


@pytest.mark.asyncio
async def test_failed_continuation_is_never_replayed(database, monkeypatch):
    """A continuation that dies mid-send ends the workflow without a retry;
    maintenance then closes the run instead of leaving it "running"."""
    from temporalio.client import WorkflowFailureError
    from temporalio.testing import WorkflowEnvironment

    from app.models.db import AgentRun
    from app.workflows import job_activities
    from app.workflows.agent_run import AgentRunInput, AgentRunWorkflow, agent_run_workflow_id

    _, run = await new_run(database)
    action = AsyncMock(side_effect=RuntimeError("connection reset during send"))
    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with await _agent_worker(env):

            async def passthrough(coro):
                # Let the failure escape the activity, as a crash would.
                return await coro

            with (
                patch("app.services.workflow_service.continue_action", action),
                patch("app.workflows.agent_activities._run_with_timeout", new=passthrough),
            ):
                with pytest.raises(WorkflowFailureError):
                    await env.client.execute_workflow(
                        AgentRunWorkflow.run,
                        AgentRunInput(
                            run_id=str(run.id),
                            user_id=str(run.user_id),
                            initial_continuation={"type": "send_email"},
                        ),
                        id=agent_run_workflow_id(str(run.id)),
                        task_queue="it-agent-runs",
                    )
        assert action.await_count == 1

        async with database() as db:
            saved = await db.get(AgentRun, run.id)
            assert saved.status == "running"  # the claim, never overwritten
            saved.started_at = datetime.now(UTC) - timedelta(hours=1)
            await db.commit()
        monkeypatch.setattr(
            "app.core.temporal_client.get_temporal_client", AsyncMock(return_value=env.client)
        )
        assert (await job_activities.maintenance_activity({}))["reconciled"] >= 1

    async with database() as db:
        saved = await db.get(AgentRun, run.id)
        assert saved.status == "failed"


@pytest.mark.asyncio
async def test_extension_task_lifecycle_on_real_database(database):
    """Create/reuse the browser task, then record a submission on the task,
    attempt, application and run in one place."""
    from app.models.db import AgentRun, ApplicationAttempt, ExtensionTask, JobApplication
    from app.workflows.extension_activities import (
        create_extension_task_activity,
        finish_extension_task_activity,
    )

    user, run = await new_run(database, "running")
    workflow_id = f"auto-apply/{user.id}/{uuid.uuid4()}"
    async with database() as db:
        application = JobApplication(
            id=uuid.uuid4(),
            user_id=user.id,
            company="Acme",
            role="Backend Engineer",
            job_url="https://jobs.lever.co/acme/1",
            status="saved",
        )
        db.add(application)
        await db.flush()
        attempt = ApplicationAttempt(
            id=uuid.uuid4(),
            user_id=user.id,
            job_application_id=application.id,
            run_id=run.id,
            workflow_id=workflow_id,
            state="preparing",
        )
        db.add(attempt)
        await db.commit()

    params = {
        "user_id": str(user.id),
        "job_application_id": str(application.id),
        "run_id": str(run.id),
        "attempt_id": str(attempt.id),
        "workflow_id": workflow_id,
        "job_url": application.job_url,
        "company": "Acme",
        "role": "Backend Engineer",
        "pdf_document_id": None,
    }
    first = await create_extension_task_activity(params)
    retried = await create_extension_task_activity(params)  # at-least-once delivery
    assert first == retried

    async with database() as db:
        tasks = (
            (await db.execute(select(ExtensionTask).where(ExtensionTask.run_id == run.id)))
            .scalars()
            .all()
        )
        assert len(tasks) == 1 and tasks[0].status == "pending"
        assert tasks[0].payload["platform"] == "lever"
        assert (await db.get(AgentRun, run.id)).status == "queued"

    finished = await finish_extension_task_activity(
        {
            "task_id": first["task_id"],
            "run_id": str(run.id),
            "attempt_id": str(attempt.id),
            "user_id": str(user.id),
            "job_application_id": str(application.id),
            "outcome": "submitted",
            "details": {"confirmation_text": "Thank you for applying"},
        }
    )
    assert finished["applied_at"]

    async with database() as db:
        assert (await db.get(ExtensionTask, uuid.UUID(first["task_id"]))).status == "submitted"
        assert (await db.get(ApplicationAttempt, attempt.id)).state == "verified"
        saved_app = await db.get(JobApplication, application.id)
        assert saved_app.status == "applied" and saved_app.followup_day5 is not None
        saved_run = await db.get(AgentRun, run.id)
        assert saved_run.status == "completed"
        assert saved_run.output["outcome"] == "submitted"


@pytest.mark.asyncio
async def test_live_browser_form_snapshot_and_single_submit(database, monkeypatch):
    from playwright.async_api import async_playwright
    from app.models.db import BrowserSession, UserDocument
    from app.services import application_workflow as workflow
    from app.services.sandbox_service import OpenSandboxProvider
    from app.core.config import settings

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.test")
    monkeypatch.setattr(
        OpenSandboxProvider, "endpoint", AsyncMock(return_value=("http://127.0.0.1:59222", {}))
    )
    _, run = await new_run(database)
    session = BrowserSession(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=run.user_id,
        sandbox_id="test-browser",
        status="ready",
        expires_at=datetime.now(UTC) + timedelta(minutes=5),
    )
    document_id = uuid.uuid4()
    async with database() as db:
        db.add(session)
        db.add(
            UserDocument(
                id=document_id,
                user_id=run.user_id,
                doc_type="resume",
                filename="resume.pdf",
                storage_path=f"{run.user_id}/resume.pdf",
            )
        )
        await db.commit()
    monkeypatch.setattr(workflow, "acquire_session", AsyncMock(return_value=session))
    monkeypatch.setattr(workflow, "fill_known_fields", AsyncMock())
    monkeypatch.setattr(workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", "hash")))
    monkeypatch.setattr(workflow, "save_account_state", AsyncMock())
    async with async_playwright() as p:
        ws, headers = await OpenSandboxProvider().cdp("test-browser")
        browser = await p.chromium.connect_over_cdp(ws)
        page = browser.contexts[0].pages[-1]
        html = (
            '<label>Email<input name=email required value="me@example.test"></label>'
            '<input type=file required><button onclick="window.submits=(window.submits||0)+1;'
            "document.body.innerHTML='Thank you for applying'\">Submit application</button>"
        )
        await page.route(
            "https://jobs.example.test/**",
            lambda route: route.fulfill(body=html, content_type="text/html"),
        )
        pending = {
            "type": "browser_prepare",
            "job_url": "https://jobs.example.test/apply",
            "pdf_document_id": str(document_id),
        }
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


# --- Task 2: idempotent external actions (application submission + email) ---


async def new_application_attempt(factory, state="awaiting_approval"):
    from app.models.db import ApplicationAttempt, JobApplication, User

    async with factory() as db:
        user = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
        db.add(user)
        await db.flush()
        app_row = JobApplication(
            id=uuid.uuid4(),
            user_id=user.id,
            company="Acme",
            role="Backend Engineer",
            job_url="https://jobs.example.test/apply",
        )
        db.add(app_row)
        await db.flush()
        attempt = ApplicationAttempt(
            id=uuid.uuid4(), user_id=user.id, job_application_id=app_row.id, state=state
        )
        db.add(attempt)
        await db.commit()
        return user, app_row, attempt


@pytest.mark.asyncio
async def test_two_simultaneous_application_approvals_cause_one_submit(database, monkeypatch):
    """Required test #1: real Postgres row lock, not a mock — two concurrent
    claims for the same attempt must not both win the compare-and-swap."""
    from app.services import application_workflow

    monkeypatch.setattr(application_workflow, "AsyncSessionLocal", database)

    _, _, attempt = await new_application_attempt(database, state="awaiting_approval")
    results = await asyncio.gather(
        application_workflow.claim_attempt_for_submit(str(attempt.id), "hash-1"),
        application_workflow.claim_attempt_for_submit(str(attempt.id), "hash-1"),
    )
    winners = [r for r in results if r is not None]
    assert len(winners) == 1

    async with database() as db:
        from app.models.db import ApplicationAttempt

        saved = await db.get(ApplicationAttempt, attempt.id)
        assert saved.state == "submitting"


@pytest.mark.asyncio
async def test_two_simultaneous_email_approvals_cause_one_gmail_call(database, monkeypatch):
    """Required test #2: real Postgres row lock on outbound_messages."""
    from app.services import workflow_service

    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", database)

    user, run = await new_run(database)
    gmail_send = MagicMock(return_value={"id": "gmail-msg-1"})
    monkeypatch.setattr("app.services.gmail_service.GmailMCPClient.send_message", gmail_send)

    # Two concurrent approvals of the SAME run's pending email — the
    # idempotency_key ("agent_run:{run_id}") is what they collide on.
    await asyncio.gather(
        workflow_service.send_approved_email(
            user.id, run.id, "hr@acme.test", "Following up", "body"
        ),
        workflow_service.send_approved_email(
            user.id, run.id, "hr@acme.test", "Following up", "body"
        ),
    )
    assert gmail_send.call_count == 1


@pytest.mark.asyncio
async def test_same_user_cannot_start_second_attempt_for_same_job(database):
    """Required test #6: the unique constraint is the backstop even if
    application-level checks are ever bypassed."""
    from sqlalchemy.exc import IntegrityError
    from app.models.db import ApplicationAttempt

    _, app_row, _ = await new_application_attempt(database)
    async with database() as db:
        with pytest.raises(IntegrityError):
            db.add(
                ApplicationAttempt(
                    id=uuid.uuid4(),
                    user_id=app_row.user_id,
                    job_application_id=app_row.id,
                    state="preparing",
                )
            )
            await db.commit()


@pytest.mark.asyncio
async def test_different_users_can_apply_to_same_job_independently(database):
    """Required test #7."""
    from app.models.db import ApplicationAttempt, JobApplication, User

    async with database() as db:
        user_a = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
        user_b = User(id=uuid.uuid4(), email=f"{uuid.uuid4()}@example.test")
        db.add_all([user_a, user_b])
        await db.flush()
        app_a = JobApplication(
            id=uuid.uuid4(),
            user_id=user_a.id,
            company="Acme",
            role="Backend Engineer",
            job_url="https://jobs.example.test/apply",
        )
        app_b = JobApplication(
            id=uuid.uuid4(),
            user_id=user_b.id,
            company="Acme",
            role="Backend Engineer",
            job_url="https://jobs.example.test/apply",
        )
        db.add_all([app_a, app_b])
        await db.flush()
        db.add_all(
            [
                ApplicationAttempt(
                    id=uuid.uuid4(),
                    user_id=user_a.id,
                    job_application_id=app_a.id,
                    state="preparing",
                ),
                ApplicationAttempt(
                    id=uuid.uuid4(),
                    user_id=user_b.id,
                    job_application_id=app_b.id,
                    state="preparing",
                ),
            ]
        )
        await db.commit()  # no IntegrityError — different users, independent rows


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


# --- Task 3 slice 3b: the one controlled ATS adapter end-to-end test ---


@pytest.mark.asyncio
async def test_ashby_adapter_fills_and_submits_real_fixture_form(monkeypatch):
    """Required by the Task 3 spec: 'Greenhouse, Lever, and Ashby forms work
    through fixtures and one controlled end-to-end test.' Drives the real
    AshbyAdapter (not the generic inline path) against a served fixture over
    a real Chromium instance via CDP — no network, no real ashbyhq.com URL,
    no real submission. application_workflow.py does not yet dispatch to
    adapters (see adapters/__init__.py's registration and the parallel
    agent's report), so this calls the adapter's own methods directly, the
    same sequence dispatch would eventually use.
    """
    from pathlib import Path

    from playwright.async_api import async_playwright

    from app.applications.adapters.ashby import ashby_adapter
    from app.applications.models import ResolvedAnswer
    from app.core.config import settings
    from app.services.sandbox_service import OpenSandboxProvider

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.ashbyhq.com")
    monkeypatch.setattr(
        OpenSandboxProvider, "endpoint", AsyncMock(return_value=("http://127.0.0.1:59222", {}))
    )

    html = (Path(__file__).parent.parent / "fixtures" / "ats" / "ashby_apply.html").read_text()
    job_url = "https://jobs.ashbyhq.com/acme/apply"
    async with async_playwright() as p:
        ws, headers = await OpenSandboxProvider().cdp("test-browser")
        browser = await p.chromium.connect_over_cdp(ws)
        page = browser.contexts[0].pages[-1]
        await page.route(job_url, lambda route: route.fulfill(body=html, content_type="text/html"))

        assert await ashby_adapter.detect(job_url, page) is True

        await ashby_adapter.open_application(page, job_url)
        fields = await ashby_adapter.extract_fields(page)
        field_ids = {f.field_id for f in fields}
        assert {"full_name", "email", "source", "work_authorized"} <= field_ids

        answers = [
            ResolvedAnswer(
                field_id="full_name", value="Ada Lovelace", source="profile", confidence=0.99
            ),
            ResolvedAnswer(
                field_id="email", value="ada@example.test", source="profile", confidence=0.99
            ),
            ResolvedAnswer(field_id="source", value="LinkedIn", source="user", confidence=1.0),
            ResolvedAnswer(field_id="work_authorized", value="No", source="user", confidence=1.0),
        ]
        await ashby_adapter.fill_fields(page, fields, answers)
        await ashby_adapter.upload_documents(page, b"%PDF-test-resume")

        refreshed = await ashby_adapter.extract_fields(page)
        issues = await ashby_adapter.validate(page, refreshed)
        assert issues == []

        submit = await ashby_adapter.locate_submit(page)
        assert submit is not None
        assert await page.evaluate("window.submits || 0") == 0
        await submit.click()

        confirmed, text, _url = await ashby_adapter.verify_confirmation(page)
        assert confirmed is True
        assert "thank you" in text.lower()
        assert await page.evaluate("window.submits") == 1
