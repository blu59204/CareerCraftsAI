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


@pytest.mark.parametrize(
    "context",
    [
        {"linkedin_credentials": {"password": "secret"}},
        {"nested": [{"api_key": "secret"}]},
        {"_durable": True},
    ],
)
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
    with (
        patch("app.agents.orchestrator.run_auto_apply_pipeline", AsyncMock(return_value=pending)),
        patch("app.agents.orchestrator.emit"),
    ):
        result = await graph.compile().ainvoke(
            {
                "user_id": str(uuid.uuid4()),
                "run_id": str(uuid.uuid4()),
                "task_type": "auto_apply",
                "status": "running",
                "context": {"_durable": True},
            }
        )
    assert result["status"] == "awaiting_approval"
    assert result["pending_action"] == pending


@pytest.mark.parametrize(
    "url",
    [
        "http://jobs.example.com",
        "https://127.0.0.1",
        "https://jobs.example.com.evil.test",
        "https://u:p@jobs.example.com",
        "https://jobs.example.com:8443",
    ],
)
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
@pytest.mark.parametrize(
    "output,status",
    [
        ("REQUIRES_ACCOUNT_CREATION", "requires_account_creation"),
        ("Unable to proceed", "failed"),
        ("", "failed"),
        ("REQUIRES_MANUAL", "requires_manual"),
        ("READY_FOR_REVIEW", "ready_for_review"),
    ],
)
async def test_form_filler_never_labels_unknown_outcome_success(output, status):
    from app.services.form_filler_service import UserFormProfile, fill_and_submit_form

    with (
        patch(
            "app.services.form_filler_service.build_user_form_profile",
            return_value=UserFormProfile(),
        ),
        patch("app.services.form_filler_service.run_browser_task", AsyncMock(return_value=output)),
    ):
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
    run = AgentRun(
        id=uuid.uuid4(), user_id=user_id, agent_type="auto_apply", status="queued", input={}
    )
    task = WorkflowTask(
        id=uuid.uuid4(), run_id=run.id, user_id=user_id, kind=kind, payload={}, status="pending"
    )
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
    run = AgentRun(
        id=uuid.uuid4(),
        user_id=user.id,
        agent_type="auto_apply",
        status="awaiting_approval",
        input={},
        output={"type": "browser_input"},
    )
    session = BrowserSession(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user.id,
        sandbox_id=None,
        status="provisioning",
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
    )

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
    failing = BrowserSession(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=user_id,
        sandbox_id="dead",
        status="closing",
        expires_at=future,
    )
    rescued = BrowserSession(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=user_id,
        sandbox_id="live",
        status="closing",
        expires_at=future,
    )

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
    return {
        "type": "browser_review",
        "job_url": "https://jobs.example.com/apply",
        "pdf_document_id": str(uuid.uuid4()),
        "resume_sha256": digest,
        "form": snapshot,
    }


@pytest.mark.asyncio
async def test_submit_control_change_keeps_fresh_fingerprint(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from app.core.config import settings
    from app.models.db import AgentRun
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [
        {
            "name": "email",
            "id": "email",
            "type": "email",
            "label": "Email",
            "value": "me@example.test",
            "checked": False,
            "required": True,
        }
    ]
    page = _FakeSubmitPage(
        "https://jobs.example.com/apply", fields, _FakeSubmitButton(count=0, enabled=False)
    )
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(
        app_workflow, "acquire_session", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    )
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))

    run = AgentRun(
        id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={}
    )
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
    fields = [
        {
            "name": "email",
            "id": "email",
            "type": "email",
            "label": "Email",
            "value": "me@example.test",
            "checked": False,
            "required": True,
        }
    ]
    page = _FakeSubmitPage(
        "https://jobs.example.com/apply",
        fields,
        _FakeSubmitButton(count=1, enabled=True, click_exc=Exception("click timed out")),
    )
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(
        app_workflow, "acquire_session", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    )
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))

    run = AgentRun(
        id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={}
    )
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

    monkeypatch.setattr(
        workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(_MissingParentDB())
    )
    with pytest.raises(ValueError, match="Parent run"):
        await workflow_service.continue_action(
            run, {"type": "auto_apply_approval", "actions_pending": []}
        )


class _AutoApplyBatchFakeDB:
    """Minimal AsyncSession stand-in for the batch auto_apply_approval branch.

    `attempt_lookup_results` is consumed in order, one per apply_browser item
    that reaches the ApplicationAttempt lookup (mirrors _AttemptFakeDB's
    style but needs `execute` for the SELECT rather than `get`).
    """

    def __init__(self, parent, attempt_lookup_results=()):
        from app.models.db import AgentRun

        self._agent_run_model = AgentRun
        self.parent = parent
        self._attempt_lookup_results = list(attempt_lookup_results)
        self.added = []

    async def get(self, model, key, with_for_update=False):
        if model is self._agent_run_model:
            return self.parent
        return None

    async def execute(self, *args, **kwargs):
        class _R:
            def __init__(self, value):
                self._value = value

            def scalar_one_or_none(self):
                return self._value

        return _R(self._attempt_lookup_results.pop(0))

    def add(self, obj):
        # Mirrors the real session's flush-assigned default id, like the
        # established fake-DB pattern in _EmailFakeDB above.
        obj.id = getattr(obj, "id", None) or uuid.uuid4()
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        pass


@pytest.mark.asyncio
async def test_auto_apply_approval_reserves_attempt_per_child(monkeypatch):
    import app.services.workflow_service as workflow_service
    from app.models.db import AgentRun, ApplicationAttempt, WorkflowTask
    from unittest.mock import MagicMock

    run = MagicMock()
    run.id = uuid.uuid4()
    run.user_id = uuid.uuid4()
    parent = AgentRun(
        id=run.id, user_id=run.user_id, agent_type="auto_apply", status="running", output={}
    )
    job_application_id = uuid.uuid4()

    fake = _AutoApplyBatchFakeDB(parent, attempt_lookup_results=[None])
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    pending = {
        "type": "auto_apply_approval",
        "actions_pending": [
            {
                "action": "apply_browser",
                "job_url": "https://jobs.example.test/apply",
                "job_application_id": str(job_application_id),
                "pdf_document_id": "doc-1",
                "resume_sha256": "abc123",
            }
        ],
    }
    result = await workflow_service.continue_action(run, pending)

    assert len(result["result"]["child_run_ids"]) == 1
    assert result["result"].get("skipped_actions") == []

    attempts = [o for o in fake.added if isinstance(o, ApplicationAttempt)]
    assert len(attempts) == 1
    attempt = attempts[0]
    assert attempt.state == "preparing"
    assert attempt.job_application_id == job_application_id
    assert attempt.user_id == run.user_id

    tasks = [o for o in fake.added if isinstance(o, WorkflowTask)]
    assert len(tasks) == 1
    assert tasks[0].payload["type"] == "browser_prepare"
    assert tasks[0].payload["attempt_id"] == str(attempt.id)


@pytest.mark.asyncio
async def test_auto_apply_approval_skips_child_with_active_attempt(monkeypatch):
    import app.services.workflow_service as workflow_service
    from app.models.db import AgentRun, ApplicationAttempt, WorkflowTask
    from unittest.mock import MagicMock

    run = MagicMock()
    run.id = uuid.uuid4()
    run.user_id = uuid.uuid4()
    parent = AgentRun(
        id=run.id, user_id=run.user_id, agent_type="auto_apply", status="running", output={}
    )
    job_application_id = uuid.uuid4()
    existing_attempt = ApplicationAttempt(
        id=uuid.uuid4(),
        user_id=run.user_id,
        job_application_id=job_application_id,
        state="submitting",
    )

    fake = _AutoApplyBatchFakeDB(parent, attempt_lookup_results=[existing_attempt])
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    pending = {
        "type": "auto_apply_approval",
        "actions_pending": [
            {
                "action": "apply_browser",
                "job_url": "https://jobs.example.test/apply",
                "job_application_id": str(job_application_id),
                "pdf_document_id": "doc-1",
                "resume_sha256": "abc123",
            }
        ],
    }
    result = await workflow_service.continue_action(run, pending)

    assert result["result"]["child_run_ids"] == []
    assert len(result["result"]["skipped_actions"]) == 1
    skipped = result["result"]["skipped_actions"][0]
    assert skipped["job_application_id"] == str(job_application_id)
    assert "submitting" in skipped["reason"]
    assert not [o for o in fake.added if isinstance(o, (AgentRun, WorkflowTask))]


@pytest.mark.asyncio
async def test_auto_apply_approval_skips_apply_browser_without_job_application_id(monkeypatch):
    import app.services.workflow_service as workflow_service
    from app.models.db import AgentRun
    from unittest.mock import MagicMock

    run = MagicMock()
    run.id = uuid.uuid4()
    run.user_id = uuid.uuid4()
    parent = AgentRun(
        id=run.id, user_id=run.user_id, agent_type="auto_apply", status="running", output={}
    )

    fake = _AutoApplyBatchFakeDB(parent, attempt_lookup_results=[])
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    pending = {
        "type": "auto_apply_approval",
        "actions_pending": [
            {"action": "apply_browser", "job_url": "https://jobs.example.test/apply"}
        ],
    }
    result = await workflow_service.continue_action(run, pending)

    assert result["result"]["child_run_ids"] == []
    assert len(result["result"]["skipped_actions"]) == 1
    assert "job_application_id" in result["result"]["skipped_actions"][0]["reason"]


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


# --- Task 2: idempotent application submission + email sends ---


class _AttemptFakeDB:
    """Minimal AsyncSession stand-in for ApplicationAttempt row-lock reads."""

    def __init__(self, attempt=None):
        self.attempt = attempt
        self.commits = 0

    async def get(self, model, key, with_for_update=False):
        from app.models.db import ApplicationAttempt

        if model is ApplicationAttempt:
            return self.attempt
        return None

    async def commit(self):
        self.commits += 1


def _make_attempt(state="awaiting_approval"):
    from app.models.db import ApplicationAttempt

    return ApplicationAttempt(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        job_application_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        state=state,
    )


def _review_pending_with_attempt(snapshot, digest, attempt_id):
    return {
        "type": "browser_review",
        "job_url": "https://jobs.example.com/apply",
        "pdf_document_id": str(uuid.uuid4()),
        "resume_sha256": digest,
        "form": snapshot,
        "attempt_id": str(attempt_id),
    }


@pytest.mark.asyncio
async def test_claim_attempt_for_submit_swaps_awaiting_approval_to_submitting(monkeypatch):
    from app.services import application_workflow as app_workflow

    attempt = _make_attempt(state="awaiting_approval")
    fake = _AttemptFakeDB(attempt)
    monkeypatch.setattr(app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    claimed = await app_workflow.claim_attempt_for_submit(str(attempt.id), "hash-123")
    assert claimed is attempt
    assert attempt.state == "submitting"
    assert attempt.submission_token is not None
    assert attempt.approved_snapshot_hash == "hash-123"
    assert fake.commits == 1


@pytest.mark.asyncio
async def test_claim_attempt_for_submit_rejects_already_claimed(monkeypatch):
    """Second concurrent caller: the attempt is already 'submitting' (or
    beyond) — must return None, never re-claim or double count as a second
    winner of the compare-and-swap."""
    from app.services import application_workflow as app_workflow

    attempt = _make_attempt(state="submitting")
    fake = _AttemptFakeDB(attempt)
    monkeypatch.setattr(app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    claimed = await app_workflow.claim_attempt_for_submit(str(attempt.id), "hash-123")
    assert claimed is None
    assert fake.commits == 0  # no-op: nothing was written


@pytest.mark.asyncio
async def test_two_simultaneous_submits_click_exactly_once(monkeypatch):
    """The domain-level guard required by Task 2 test #1: even if
    run_application_stage's browser_review branch is entered twice for the
    same attempt, the submit button is clicked at most once."""
    import hashlib
    from types import SimpleNamespace

    from app.core.config import settings
    from app.models.db import AgentRun
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [
        {
            "name": "email",
            "id": "email",
            "type": "email",
            "label": "Email",
            "value": "me@example.test",
            "checked": False,
            "required": True,
        }
    ]
    button = _FakeSubmitButton(count=1, enabled=True)
    page = _FakeSubmitPage("https://jobs.example.com/apply", fields, button)
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(
        app_workflow, "acquire_session", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    )
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))

    attempt = _make_attempt(state="awaiting_approval")

    click_count = {"n": 0}
    real_click = button.click

    async def _counting_click(**kwargs):
        click_count["n"] += 1
        return await real_click(**kwargs)

    button.click = _counting_click

    # First caller claims the attempt (flips it to submitting) so the second
    # concurrent caller's read of the SAME row sees it already claimed.
    fake_first = _AttemptFakeDB(attempt)
    monkeypatch.setattr(app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(fake_first))
    run = AgentRun(
        id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={}
    )
    pending = _review_pending_with_attempt(snapshot, digest, attempt.id)

    result_one = await app_workflow.run_application_stage(run, dict(pending))
    result_two = await app_workflow.run_application_stage(run, dict(pending))

    assert click_count["n"] == 1
    assert (
        result_one["result"]["outcome"] == "unknown"
    )  # confirmation never arrives from _FakeConfirmText(0)
    assert result_two["result"]["outcome"] == "duplicate_suppressed"


@pytest.mark.asyncio
async def test_submit_success_marks_attempt_verified(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from app.core.config import settings
    from app.models.db import AgentRun
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [
        {
            "name": "email",
            "id": "email",
            "type": "email",
            "label": "Email",
            "value": "me@example.test",
            "checked": False,
            "required": True,
        }
    ]
    button = _FakeSubmitButton(count=1, enabled=True)
    page = _FakeSubmitPage("https://jobs.example.com/apply", fields, button, pre_confirm=0)
    # Confirmation text only appears after the click — the pre-click
    # "existing confirmation" guard must see none, only the post-click wait.
    state = {"clicked": False}
    real_click = button.click

    async def _click_then_confirm(**kwargs):
        state["clicked"] = True
        return await real_click(**kwargs)

    button.click = _click_then_confirm
    page.get_by_text = lambda pattern: _FakeConfirmText(1 if state["clicked"] else 0)

    class _BodyLocator:
        async def inner_text(self):
            return "Thank you for applying! Your application has been submitted."

    real_locator = page.locator
    page.locator = lambda selector: _BodyLocator() if selector == "body" else real_locator(selector)
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(
        app_workflow, "acquire_session", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    )
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))
    monkeypatch.setattr(app_workflow, "save_account_state", AsyncMock(return_value=None))

    attempt = _make_attempt(state="awaiting_approval")
    fake = _AttemptFakeDB(attempt)
    monkeypatch.setattr(app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    class _JobAppDB:
        async def execute(self, *a, **k):
            class _R:
                def scalars(self):
                    return self

                def first(self):
                    return None

            return _R()

        def add(self, obj):
            pass

        async def commit(self):
            pass

    # run_application_stage opens separate AsyncSessionLocal() calls for the
    # claim, the verified-state write, and finally the JobApplication
    # upsert — only that last one needs the JobApplication-shaped fake.
    calls = {"n": 0}

    def _session_factory():
        calls["n"] += 1
        return _fake_session_cm(fake if calls["n"] <= 2 else _JobAppDB())

    monkeypatch.setattr(app_workflow, "AsyncSessionLocal", _session_factory)

    run = AgentRun(
        id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={}
    )
    pending = _review_pending_with_attempt(snapshot, digest, attempt.id)
    result = await app_workflow.run_application_stage(run, pending)

    assert result["status"] == "completed"
    assert result["result"]["outcome"] == "submitted"
    assert attempt.state == "verified"
    assert attempt.confirmation_url == "https://jobs.example.com/apply"
    assert attempt.verified_at is not None


@pytest.mark.asyncio
async def test_submit_click_failure_marks_outcome_unknown_on_attempt(monkeypatch):
    import hashlib
    from types import SimpleNamespace

    from app.core.config import settings
    from app.models.db import AgentRun
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [
        {
            "name": "email",
            "id": "email",
            "type": "email",
            "label": "Email",
            "value": "me@example.test",
            "checked": False,
            "required": True,
        }
    ]
    page = _FakeSubmitPage(
        "https://jobs.example.com/apply",
        fields,
        _FakeSubmitButton(count=1, enabled=True, click_exc=Exception("timed out")),
    )
    snapshot = await app_workflow.review_snapshot(page)
    digest = hashlib.sha256(b"%PDF-test").hexdigest()

    monkeypatch.setattr(
        app_workflow, "acquire_session", AsyncMock(return_value=SimpleNamespace(id=uuid.uuid4()))
    )
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", digest)))

    attempt = _make_attempt(state="awaiting_approval")
    fake = _AttemptFakeDB(attempt)
    monkeypatch.setattr(app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(fake))

    run = AgentRun(
        id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="auto_apply", status="running", input={}
    )
    pending = _review_pending_with_attempt(snapshot, digest, attempt.id)
    result = await app_workflow.run_application_stage(run, pending)

    assert result["result"]["outcome"] == "unknown"
    assert attempt.state == "outcome_unknown"
    assert attempt.last_error


@pytest.mark.asyncio
async def test_recover_expired_tasks_flips_stuck_submitting_attempt(monkeypatch):
    import app.services.workflow_service as workflow_service
    from app.models.db import AgentRun, ApplicationAttempt, WorkflowTask

    user_id = uuid.uuid4()
    run = AgentRun(
        id=uuid.uuid4(), user_id=user_id, agent_type="apply_prepare", status="running", input={}
    )
    task = WorkflowTask(
        id=uuid.uuid4(),
        run_id=run.id,
        user_id=user_id,
        kind="continue",
        payload={},
        status="running",
        lease_until=None,
    )
    attempt = ApplicationAttempt(
        id=uuid.uuid4(),
        user_id=user_id,
        job_application_id=uuid.uuid4(),
        run_id=run.id,
        state="submitting",
    )

    class _ScalarsList:
        def __init__(self, items):
            self._items = items

        def scalars(self):
            return self

        def all(self):
            return self._items

        def first(self):
            return self._items[0] if self._items else None

    class _RecoverDB:
        def __init__(self):
            self.commits = 0

        async def execute(self, statement, *a, **k):
            # First query: expired WorkflowTasks. Second: the stuck attempt.
            compiled = str(statement)
            if "workflow_tasks" in compiled.lower():
                return _ScalarsList([task])
            return _ScalarsList([attempt])

        async def get(self, model, key, with_for_update=False):
            if model is AgentRun:
                return run
            return None

        async def commit(self):
            self.commits += 1

    fake = _RecoverDB()
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))
    await workflow_service.recover_expired_tasks()

    assert task.status == "failed"
    assert run.status == "failed"
    assert attempt.state == "outcome_unknown"
    assert attempt.last_error == task.error


@pytest.mark.asyncio
async def test_send_approved_email_suppresses_concurrent_duplicate(monkeypatch):
    import app.services.workflow_service as workflow_service
    from app.models.db import OutboundMessage

    already_sending = OutboundMessage(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        channel="email",
        recipient="hr@acme.test",
        subject="Following up",
        body_hash="x",
        state="sending",
        idempotency_key="agent_run:same-run",
    )

    class _OneRow:
        def __init__(self, value):
            self._value = value

        def scalar_one_or_none(self):
            return self._value

    class _EmailFakeDB:
        async def execute(self, *a, **k):
            return _OneRow(already_sending)

        async def commit(self):
            return None

    monkeypatch.setattr(
        workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(_EmailFakeDB())
    )
    gmail_send = AsyncMock()
    monkeypatch.setattr("app.services.gmail_service.GmailMCPClient.send_message", gmail_send)

    result = await workflow_service.send_approved_email(
        already_sending.user_id,
        already_sending.run_id,
        "hr@acme.test",
        "Following up",
        "body",
    )
    assert result["duplicate_suppressed"] is True
    gmail_send.assert_not_called()


@pytest.mark.asyncio
async def test_send_approved_email_success_marks_sent(monkeypatch):
    import app.services.workflow_service as workflow_service

    class _OneRow:
        def scalar_one_or_none(self):
            return None

    class _EmailFakeDB:
        def __init__(self):
            self.added = None

        async def execute(self, *a, **k):
            return _OneRow()

        def add(self, obj):
            obj.id = obj.id or uuid.uuid4()
            self.added = obj

        async def flush(self):
            pass

        async def get(self, model, key, with_for_update=False):
            return self.added

        async def commit(self):
            pass

    fake = _EmailFakeDB()
    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(fake))
    monkeypatch.setattr(
        "app.services.gmail_service.GmailMCPClient.send_message",
        lambda self, to, subject, body: {"id": "gmail-msg-1"},
    )

    result = await workflow_service.send_approved_email(
        uuid.uuid4(),
        uuid.uuid4(),
        "hr@acme.test",
        "Following up",
        "body text",
    )
    assert result["sent"] is True
    assert result["provider_message_id"] == "gmail-msg-1"
    assert fake.added.state == "sent"
    assert fake.added.provider_message_id == "gmail-msg-1"


# --- Task 3 slice 3a: answer-required checkpoint integration ---


class _NoAnswersDB:
    """No saved answers/profile for this user, but supports BrowserSession
    get/update — matches what the browser_prepare/browser_input branch of
    run_application_stage needs from AsyncSessionLocal()."""

    def __init__(self, browser_session):
        self.browser_session = browser_session

    async def execute(self, *a, **k):
        class _R:
            def scalar_one_or_none(self):
                return None

        return _R()

    async def get(self, model, key, with_for_update=False):
        from app.models.db import BrowserSession

        if model is BrowserSession:
            return self.browser_session
        return None

    async def commit(self):
        pass


def _prepare_pending(attempt_id=None):
    pending = {
        "type": "browser_input",
        "job_url": "https://jobs.example.com/apply",
        "pdf_document_id": str(uuid.uuid4()),
        "company": "Acme",
        "role": "Backend Engineer",
    }
    if attempt_id:
        pending["attempt_id"] = str(attempt_id)
    return pending


@pytest.mark.asyncio
async def test_unresolved_required_field_triggers_answers_required_checkpoint(monkeypatch):

    from app.core.config import settings
    from app.models.db import AgentRun, BrowserSession
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [
        {
            "name": "sponsor",
            "id": "",
            "type": "radio",
            "label": "Yes",
            "value": "yes",
            "group_label": "Will you require visa sponsorship?",
            "checked": False,
            "required": True,
            "options": [],
            "visible": True,
            "disabled": False,
        },
        {
            "name": "sponsor",
            "id": "",
            "type": "radio",
            "label": "No",
            "value": "no",
            "group_label": "Will you require visa sponsorship?",
            "checked": False,
            "required": True,
            "options": [],
            "visible": True,
            "disabled": False,
        },
    ]
    page = _FakeSubmitPage(
        "https://jobs.example.com/apply", fields, _FakeSubmitButton(count=0, enabled=False)
    )
    browser_session = BrowserSession(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="provisioning",
        expires_at=None,
    )

    monkeypatch.setattr(app_workflow, "acquire_session", AsyncMock(return_value=browser_session))
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "save_account_state", AsyncMock(return_value=None))
    monkeypatch.setattr(
        app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", "digest123"))
    )
    monkeypatch.setattr(app_workflow, "fill_known_fields", AsyncMock(return_value=None))
    monkeypatch.setattr(
        app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(_NoAnswersDB(browser_session))
    )

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_type="apply_prepare",
        status="running",
        input={},
    )
    result = await app_workflow.run_application_stage(run, _prepare_pending())

    assert result["pending_action"]["type"] == "application_answers_required"
    returned_fields = result["pending_action"]["fields"]
    assert len(returned_fields) == 1
    assert returned_fields[0]["question_key"] == "authorization.requires_sponsorship"


@pytest.mark.asyncio
async def test_already_filled_required_field_does_not_trigger_answers_required(monkeypatch):
    """Regression: a required field the DOM already has a value for must
    not be treated as 'missing' just because there is no saved answer for
    it — otherwise every field fill_known_fields already handled would
    wrongly block on a fresh human-input checkpoint."""

    from app.core.config import settings
    from app.models.db import AgentRun, BrowserSession
    from app.services import application_workflow as app_workflow

    monkeypatch.setattr(settings, "SANDBOX_ALLOWED_DOMAINS", "jobs.example.com")
    fields = [
        {
            "name": "email",
            "id": "email",
            "type": "email",
            "label": "Email",
            "value": "me@example.test",
            "checked": False,
            "required": True,
            "options": [],
            "visible": True,
            "disabled": False,
        }
    ]
    page = _FakeSubmitPage(
        "https://jobs.example.com/apply", fields, _FakeSubmitButton(count=0, enabled=False)
    )
    browser_session = BrowserSession(
        id=uuid.uuid4(),
        run_id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        status="provisioning",
        expires_at=None,
    )

    monkeypatch.setattr(app_workflow, "acquire_session", AsyncMock(return_value=browser_session))
    monkeypatch.setattr(
        app_workflow, "browser_page", lambda session: _fake_session_cm((object(), page))
    )
    monkeypatch.setattr(app_workflow, "save_account_state", AsyncMock(return_value=None))
    monkeypatch.setattr(
        app_workflow, "load_resume", AsyncMock(return_value=(b"%PDF-test", "digest123"))
    )
    monkeypatch.setattr(app_workflow, "fill_known_fields", AsyncMock(return_value=None))
    monkeypatch.setattr(
        app_workflow, "AsyncSessionLocal", lambda: _fake_session_cm(_NoAnswersDB(browser_session))
    )

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_type="apply_prepare",
        status="running",
        input={},
    )
    result = await app_workflow.run_application_stage(run, _prepare_pending())

    assert result["pending_action"]["type"] == "browser_input"


@pytest.mark.asyncio
async def test_continue_action_saves_answers_and_resumes_preparation(monkeypatch):
    import app.services.workflow_service as workflow_service
    from unittest.mock import MagicMock

    saved_calls = []

    async def _fake_save(db, user_id, question_key, label, value, **kwargs):
        saved_calls.append((question_key, value))
        return MagicMock()

    resumed_calls = []

    async def _fake_run_application_stage(run, pending):
        resumed_calls.append(pending)
        return {"status": "awaiting_approval", "pending_action": {"type": "browser_input"}}

    monkeypatch.setattr("app.applications.profile_service.save_approved_answer", _fake_save)
    monkeypatch.setattr(
        "app.services.application_workflow.run_application_stage",
        _fake_run_application_stage,
    )

    class _CommitDB:
        async def commit(self):
            pass

    monkeypatch.setattr(
        workflow_service, "AsyncSessionLocal", lambda: _fake_session_cm(_CommitDB())
    )

    run = MagicMock()
    run.user_id = uuid.uuid4()
    run.id = uuid.uuid4()
    pending = {
        "type": "application_answers_required",
        "job_url": "https://jobs.example.com/apply",
        "answers": {"sponsor": "No"},
        "fields": [
            {
                "field_id": "sponsor",
                "question_key": "authorization.requires_sponsorship",
                "label": "Will you require sponsorship?",
            }
        ],
    }
    result = await workflow_service.continue_action(run, pending)

    assert saved_calls == [("authorization.requires_sponsorship", "No")]
    assert len(resumed_calls) == 1
    assert resumed_calls[0]["type"] == "browser_input"
    assert "answers" not in resumed_calls[0]
    assert "fields" not in resumed_calls[0]
    assert result["pending_action"]["type"] == "browser_input"
