import uuid
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from langgraph.graph import END, START, StateGraph
from pydantic import ValidationError

from app.agents.state import AgentState
from app.api.v1.agents import RunRequest
from app.services.sandbox_service import OpenSandboxProvider, validate_browser_url
from app.services.workflow_service import validate_approval


@pytest.mark.parametrize("context", [
    {"linkedin_credentials": {"password": "secret"}},
    {"nested": [{"api_key": "secret"}]}, {"_durable": True},
])
def test_run_context_rejects_secrets_and_reserved_fields(context):
    with pytest.raises(ValidationError):
        RunRequest(task_type="auto_apply", context=context)


def test_approval_keeps_target_and_invalidates_edited_pdf():
    original = {"type": "resume_ready", "pdf_document_id": "old", "resume_markdown": "before"}
    result = validate_approval(original, {"body": "after"})
    assert result["pdf_document_id"] is None
    assert original["pdf_document_id"] == "old"
    with pytest.raises(ValueError):
        validate_approval({"type": "send_email", "to": "a@example.com"}, {"to": "b@example.com"})
    with pytest.raises(ValueError):
        validate_approval({"type": "browser_review"}, {"body": "changed"})


@pytest.mark.asyncio
async def test_real_async_graph_runner_preserves_approval():
    from app.agents.orchestrator import _auto_apply_wrapper, _make_node_runner
    graph = StateGraph(AgentState)
    graph.add_node("apply", _make_node_runner("apply", _auto_apply_wrapper))
    graph.add_edge(START, "apply")
    graph.add_edge("apply", END)
    pending = {"requires_approval": True, "type": "auto_apply_approval", "actions_pending": []}
    with patch("app.agents.orchestrator.run_auto_apply_pipeline", AsyncMock(return_value=pending)), patch("app.agents.orchestrator.emit"):
        result = await graph.compile().ainvoke({
            "user_id": str(uuid.uuid4()), "run_id": str(uuid.uuid4()), "task_type": "auto_apply",
            "status": "running", "context": {"_durable": True},
        })
    assert result["status"] == "awaiting_approval"
    assert result["pending_action"] == pending


@pytest.mark.parametrize("url", ["http://jobs.example.com", "https://127.0.0.1", "https://jobs.example.com.evil.test", "https://u:p@jobs.example.com", "https://jobs.example.com:8443"])
def test_destination_validation_rejects_unsafe_urls(monkeypatch, url):
    from app.core.config import settings
    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com,*.example.org")
    with pytest.raises(ValueError):
        validate_browser_url(url)
    assert validate_browser_url("https://jobs.example.com/apply")
    assert validate_browser_url("https://login.example.org")


@pytest.mark.asyncio
async def test_provider_uses_private_auth_and_resource_policy(monkeypatch):
    from app.core.config import settings
    from app.models.db import BrowserSession
    monkeypatch.setattr(settings, "OPEN_SANDBOX_URL", "http://sandbox.test")
    monkeypatch.setattr(settings, "OPEN_SANDBOX_API_KEY", "private-key")
    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    requests = []

    def handler(request):
        requests.append(request)
        return httpx.Response(202, json={"id": "sandbox-1"})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenSandboxProvider(client)
        result = await provider.create(BrowserSession(id=uuid.uuid4()))
    import json
    body = json.loads(requests[0].content)
    assert result == "sandbox-1"
    assert requests[0].headers["OPEN-SANDBOX-API-KEY"] == "private-key"
    assert body["networkPolicy"]["defaultAction"] == "deny"
    assert body["timeout"] > 0
    assert body["resourceLimits"]["memory"]


@pytest.mark.asyncio
@pytest.mark.parametrize("output,status", [
    ("REQUIRES_ACCOUNT_CREATION", "requires_account_creation"),
    ("Unable to proceed", "failed"), ("", "failed"),
    ("REQUIRES_MANUAL", "requires_manual"), ("READY_FOR_REVIEW", "ready_for_review"),
])
async def test_form_filler_never_labels_unknown_outcome_success(output, status):
    from app.services.form_filler_service import UserFormProfile, fill_and_submit_form
    with patch("app.services.form_filler_service.build_user_form_profile", return_value=UserFormProfile()), patch("app.services.form_filler_service.run_browser_task", AsyncMock(return_value=output)):
        result = await fill_and_submit_form(None, "user", "https://jobs.example.com")
    assert result["status"] == status


# --- Regression tests for the durable-workflow hardening pass. ---


def _fake_session_cm(yielded):
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _cm():
        yield yielded

    return _cm()


class _ScalarResult:
    def scalar_one(self):
        return 0

    def scalars(self):
        return self

    def all(self):
        return []


class _WorkflowFakeDB:
    """Minimal AsyncSession stand-in for workflow_service.execute_task."""

    def __init__(self, task=None, run=None):
        self.task = task
        self.run = run
        self.commits = 0

    async def get(self, model, key, with_for_update=False):
        from app.models.db import AgentRun, WorkflowTask

        if model is WorkflowTask:
            return self.task
        if model is AgentRun:
            return self.run
        return None

    async def execute(self, *args, **kwargs):
        return _ScalarResult()

    async def commit(self):
        self.commits += 1

    def add(self, obj):
        pass


def _make_queued_pair(kind="execute"):
    from app.models.db import AgentRun, WorkflowTask

    user_id = uuid.uuid4()
    run = AgentRun(id=uuid.uuid4(), user_id=user_id, agent_type="auto_apply", status="queued", input={})
    task = WorkflowTask(id=uuid.uuid4(), run_id=run.id, user_id=user_id, kind=kind, payload={}, status="pending")
    return task, run


@pytest.mark.asyncio
async def test_execute_task_ignores_malformed_id(monkeypatch):
    import app.services.workflow_service as workflow_service

    async def _no_session():
        raise AssertionError("malformed task id must not touch the database")

    execute = AsyncMock()
    continued = AsyncMock()
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", _no_session)
    monkeypatch.setattr(workflow_service, "execute_agent", execute)
    monkeypatch.setattr(workflow_service, "continue_action", continued)
    await workflow_service.execute_task("not-a-task-id")
    execute.assert_not_awaited()
    continued.assert_not_awaited()


@pytest.mark.asyncio
async def test_capacity_retry_does_not_resurrect_cancelled_run(monkeypatch):
    import app.services.workflow_service as workflow_service
    from app.services.workflow_service import CapacityUnavailable

    task, run = _make_queued_pair("execute")
    fake = _WorkflowFakeDB(task, run)
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))
    monkeypatch.setattr(workflow_service, "publish", lambda *args: None)

    async def _claim_then_cancel(*args, **kwargs):
        # The user cancels while the worker is busy downstream.
        run.status = "failed"
        raise CapacityUnavailable("Browser capacity is occupied")

    monkeypatch.setattr(workflow_service, "execute_agent", _claim_then_cancel)
    await workflow_service.execute_task(str(task.id))
    assert run.status == "failed"
    assert task.status == "running"  # left for lease recovery to fail closed
    assert fake.commits == 1  # only the initial claim committed


@pytest.mark.asyncio
async def test_browser_provisioning_session_is_not_usable():
    from datetime import datetime, timedelta, timezone

    from fastapi import HTTPException

    from app.api.v1.browser import owned_session
    from app.models.db import AgentRun, BrowserSession, User

    user = User(id=uuid.uuid4(), email="owner@example.test")
    run = AgentRun(id=uuid.uuid4(), user_id=user.id, agent_type="auto_apply",
                   status="awaiting_approval", input={}, output={"type": "browser_input"})
    session = BrowserSession(id=uuid.uuid4(), run_id=run.id, user_id=user.id, sandbox_id=None,
                             status="provisioning",
                             expires_at=datetime.now(timezone.utc) + timedelta(minutes=5))

    calls = {"n": 0}

    class _One:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _SeqDB:
        async def execute(self, *args, **kwargs):
            calls["n"] += 1
            return _One(run if calls["n"] == 1 else session)

    with pytest.raises(HTTPException) as exc:
        await owned_session(_SeqDB(), user, run.id)
    assert exc.value.status_code == 409


@pytest.mark.asyncio
async def test_reaper_isolates_single_destroy_failure(monkeypatch):
    from datetime import datetime, timedelta, timezone

    import app.services.sandbox_service as sandbox_service
    from app.models.db import BrowserSession

    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    user_id = uuid.uuid4()
    failing = BrowserSession(id=uuid.uuid4(), run_id=uuid.uuid4(), user_id=user_id,
                             sandbox_id="dead", status="closing", expires_at=future)
    rescued = BrowserSession(id=uuid.uuid4(), run_id=uuid.uuid4(), user_id=user_id,
                             sandbox_id="live", status="closing", expires_at=future)

    class _Rows:
        def scalars(self):
            return self

        def all(self):
            return [failing, rescued]

    class _ReapDB:
        def __init__(self):
            self.commits = 0

        async def execute(self, *args, **kwargs):
            return _Rows()

        async def commit(self):
            self.commits += 1

    fake = _ReapDB()
    monkeypatch.setattr(sandbox_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))
    monkeypatch.setattr(sandbox_service.settings, "OPEN_SANDBOX_URL", "http://sandbox.test")
    destroy = AsyncMock(side_effect=[RuntimeError("provider boom"), {}])
    monkeypatch.setattr(sandbox_service.OpenSandboxProvider, "destroy", destroy)
    await sandbox_service.reap_sessions()
    assert failing.status == "closing"
    assert rescued.status == "closed"
    assert fake.commits == 1


class _FormLocator:
    async def evaluate_all(self, script):
        return [{"action": "", "method": "get"}]


class _EmptyLocator:
    async def evaluate_all(self, script):
        return []

    async def count(self):
        return 0

    async def inner_text(self):
        return ""


class _FakeSubmitButton:
    def __init__(self, count=1, enabled=True, click_exc=None):
        self._count = count
        self._enabled = enabled
        self._click_exc = click_exc

    async def all_text_contents(self):
        return ["Submit application"]

    async def count(self):
        return self._count

    async def is_visible(self):
        return True

    async def is_enabled(self):
        return self._enabled

    async def click(self, **kwargs):
        if self._click_exc is not None:
            raise self._click_exc


class _FakeConfirmText:
    def __init__(self, count=0):
        self._count = count

    async def count(self):
        return self._count

    @property
    def first(self):
        return self

    async def wait_for(self, **kwargs):
        return None


class _FakeSubmitPage:
    def __init__(self, url, fields, button, pre_confirm=0):
        self.url = url
        self._fields = fields
        self._button = button
        self._pre_confirm = pre_confirm

    async def evaluate(self, script, *args):
        return [dict(field) for field in self._fields]

    def locator(self, selector):
        return _FormLocator() if selector == "form" else _EmptyLocator()

    def get_by_role(self, role, name=None):
        return self._button

    def get_by_text(self, pattern):
        return _FakeConfirmText(self._pre_confirm)


def _review_pending(snapshot, digest):
    return {"type": "browser_review", "job_url": "https://jobs.example.com/apply",
            "pdf_document_id": str(uuid.uuid4()), "resume_sha256": digest, "form": snapshot}


@pytest.mark.asyncio
async def test_submit_control_change_keeps_fresh_fingerprint(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from app.core.config import settings
    from app.models.db import AgentRun
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [{"name": "email", "id": "email", "type": "email", "label": "Email",
               "value": "me@example.test", "checked": False, "required": True}]
    page = _FakeSubmitPage("https://jobs.example.com/apply", fields,
                           _FakeSubmitButton(count=0, enabled=False))
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(app_workflow, "acquire_session",
                        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page)))
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))

    run = AgentRun(id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={})
    result = await app_workflow.run_application_stage(run, _review_pending(snapshot, digest))
    assert result["pending_action"]["type"] == "browser_input"
    assert result["pending_action"]["form"]["fingerprint"] == snapshot["fingerprint"]


@pytest.mark.asyncio
async def test_submit_click_timeout_is_unknown_outcome(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from app.core.config import settings
    from app.models.db import AgentRun
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [{"name": "email", "id": "email", "type": "email", "label": "Email",
               "value": "me@example.test", "checked": False, "required": True}]
    page = _FakeSubmitPage("https://jobs.example.com/apply", fields,
                           _FakeSubmitButton(count=1, enabled=True,
                                             click_exc=Exception("click timed out")))
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(app_workflow, "acquire_session",
                        AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4())))
    monkeypatch.setattr(app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page)))
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))

    run = AgentRun(id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={})
    result = await app_workflow.run_application_stage(run, _review_pending(snapshot, digest))
    assert result["status"] == "failed"
    assert result["result"]["outcome"] == "unknown"
    assert result["result"]["job_url"] == "https://jobs.example.com/apply"


@pytest.mark.asyncio
async def test_continue_action_rejects_malformed_search_confirmation():
    from unittest.mock import MagicMock

    from app.services.workflow_service import continue_action

    run = MagicMock()
    run.user_id = uuid.uuid4()
    run.id = uuid.uuid4()
    with pytest.raises(ValueError, match="interpretation"):
        await continue_action(run, {"type": "search_confirmation"})


@pytest.mark.asyncio
async def test_auto_apply_approval_missing_parent_fails_closed(monkeypatch):
    from unittest.mock import MagicMock

    import app.services.workflow_service as workflow_service

    run = MagicMock()
    run.id = uuid.uuid4()
    run.user_id = uuid.uuid4()

    class _MissingParentDB:
        async def get(self, *args, **kwargs):
            return None

        async def commit(self):
            return None

    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(_MissingParentDB()))
    with pytest.raises(ValueError, match="Parent run"):
        await workflow_service.continue_action(run, {"type": "auto_apply_approval", "actions_pending": []})


@pytest.mark.asyncio
async def test_sandbox_endpoint_rejects_invalid_provider_payload(monkeypatch):
    from app.core.config import settings
    from app.services.sandbox_service import OpenSandboxProvider

    monkeypatch.setattr(settings, "OPEN_SANDBOX_URL", "http://sandbox.test")
    monkeypatch.setattr(settings, "OPEN_SANDBOX_API_KEY", "private-key")

    def handler(request):
        return httpx.Response(200, json={"endpoint": ""})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        provider = OpenSandboxProvider(client)
        with pytest.raises(RuntimeError, match="invalid endpoint"):
            await provider.endpoint("sandbox-1")
