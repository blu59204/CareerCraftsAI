import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

UTC = timezone.utc


@pytest.mark.asyncio
async def test_schedule_followups_starts_one_workflow_keyed_by_application():
    """Scheduling is a FollowupWorkflow per application (timing is covered
    by the time-skipping tests in test_temporal_workflows.py)."""
    from app.agents import followup_agent

    application_id = str(uuid.uuid4())
    applied_at = datetime.now(UTC) - timedelta(days=4)
    with patch("app.workflows.starters.start_followups", new=AsyncMock(return_value=True)) as start:
        await followup_agent.schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=applied_at,
        )

    start.assert_awaited_once_with("usr_test", application_id, applied_at)


@pytest.mark.asyncio
async def test_schedule_followups_is_a_no_op_when_already_scheduled():
    from app.agents import followup_agent

    with patch(
        "app.workflows.starters.start_followups", new=AsyncMock(return_value=False)
    ) as start:
        await followup_agent.schedule_followups(
            user_id="usr_test",
            application_id=str(uuid.uuid4()),
            applied_at=None,
        )

    # applied_at=None falls back to "now" rather than failing.
    assert start.await_args.args[2] is not None


@pytest.mark.asyncio
async def test_start_followups_reuses_the_running_workflow(monkeypatch):
    """A second schedule call for the same application must not create a
    second set of drafts: Temporal rejects the duplicate workflow id."""
    from temporalio.exceptions import WorkflowAlreadyStartedError

    from app.workflows import starters

    client = AsyncMock()
    client.start_workflow.side_effect = [
        None,
        WorkflowAlreadyStartedError("followup/x", "FollowupWorkflow"),
    ]
    monkeypatch.setattr(starters, "get_temporal_client", AsyncMock(return_value=client))

    application_id = str(uuid.uuid4())
    first = await starters.start_followups("usr_test", application_id, datetime.now(UTC))
    second = await starters.start_followups("usr_test", application_id, datetime.now(UTC))

    assert (first, second) == (True, False)
    ids = {call.kwargs["id"] for call in client.start_workflow.call_args_list}
    assert ids == {f"followup/{application_id}"}


def test_build_followup_draft_uses_db_settings_fallback():
    from app.agents.followup_agent import build_followup_draft

    model_settings = object()
    parsed = types.SimpleNamespace(subject="Checking in", body="Hello")
    with (
        patch("app.core.sync_db.fetch_model_settings", return_value=model_settings) as fetch,
        patch("app.core.model_router._build_llm", return_value=object()) as build_llm,
        patch("app.agents._llm_json.call_llm_json", return_value=parsed),
    ):
        result = build_followup_draft("user", "Acme", "Engineer", None, 5)

    assert result == {"subject": "Checking in", "body": "Hello"}
    fetch.assert_called_once_with("user")
    build_llm.assert_called_once_with(model_settings)


# ---------------------------------------------------------------------------
# run_followup (execution side) — backend/app/services/scheduled_jobs.py
# ---------------------------------------------------------------------------

import types  # noqa: E402


class _FakeSingleResult:
    def __init__(self, item):
        self._item = item

    def scalar_one_or_none(self):
        return self._item


class _FakeFollowupSession:
    """Minimal AsyncSession stand-in: every execute() returns the one
    application row; with_for_update()/where() chains are irrelevant here
    since the fake ignores the statement entirely."""

    def __init__(self, application):
        self.application = application
        self.added = []
        self.commits = 0

    async def execute(self, stmt):
        return _FakeSingleResult(self.application)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeFollowupSessionLocal:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


def _make_application(applied_at=None, status="applied"):
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        company="Acme",
        role="Engineer",
        status=status,
        applied_at=applied_at or datetime.now(UTC),
        followup_day5=datetime.now(UTC) + timedelta(days=1),
        followup_day12=datetime.now(UTC) + timedelta(days=8),
    )


@pytest.mark.asyncio
async def test_run_followup_due_with_no_reply_creates_draft_checkpoint_not_send():
    """A due follow-up with no recruiter reply must produce a draft awaiting
    approval — never send anything itself."""
    from app.services.scheduled_jobs import FollowupTrigger, run_followup

    application = _make_application()
    session = _FakeFollowupSession(application)

    with (
        patch("app.core.database.AsyncSessionLocal", _FakeFollowupSessionLocal(session)),
        patch("app.services.scheduled_jobs._has_recruiter_replied", AsyncMock(return_value=False)),
        patch(
            "app.services.email_finder_service.find_recruiter_email",
            AsyncMock(return_value={"email": "hr@acme.com"}),
        ),
        patch(
            "app.agents.followup_agent.build_followup_draft",
            return_value={"subject": "Checking in", "body": "Hi there"},
        ),
        patch("app.services.scheduled_jobs.emit") as mock_emit,
    ):
        result = await run_followup(
            FollowupTrigger(
                user_id=str(application.user_id),
                application_id=str(application.id),
                day=5,
            )
        )

    assert result["status"] == "awaiting_approval"
    assert session.commits == 1
    assert len(session.added) == 1
    run = session.added[0]
    assert run.status == "awaiting_approval"
    assert run.output["type"] == "send_email"
    assert run.output["recipient"] == "hr@acme.com"
    assert run.output["subject"] == "Checking in"
    assert run.output["body"] == "Hi there"
    mock_emit.assert_called_once()
    emitted_event = mock_emit.call_args.args[1]
    assert emitted_event == "checkpoint"


@pytest.mark.asyncio
async def test_run_followup_cancels_instead_of_drafting_when_recruiter_replied():
    """A due follow-up where the recruiter already replied must cancel the
    remaining schedule and must never produce a draft."""
    from app.services.scheduled_jobs import FollowupTrigger, run_followup

    application = _make_application()
    session = _FakeFollowupSession(application)

    with (
        patch("app.core.database.AsyncSessionLocal", _FakeFollowupSessionLocal(session)),
        patch("app.services.scheduled_jobs._has_recruiter_replied", AsyncMock(return_value=True)),
    ):
        result = await run_followup(
            FollowupTrigger(
                user_id=str(application.user_id),
                application_id=str(application.id),
                day=5,
            )
        )

    assert result["status"] == "cancelled"
    assert result["reason"] == "recruiter_replied"
    assert application.followup_day5 is None
    assert application.followup_day12 is None
    assert session.added == []  # no draft/AgentRun created
    assert session.commits == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["interview", "offer", "rejected"])
async def test_run_followup_stops_once_the_application_moved_on(status):
    """No "just checking in" email after an interview, offer or rejection."""
    from app.services.scheduled_jobs import FollowupTrigger, run_followup

    application = _make_application(status=status)
    session = _FakeFollowupSession(application)

    with (
        patch("app.core.database.AsyncSessionLocal", _FakeFollowupSessionLocal(session)),
        patch("app.services.scheduled_jobs._has_recruiter_replied", AsyncMock()) as replied,
    ):
        result = await run_followup(
            FollowupTrigger(
                user_id=str(application.user_id),
                application_id=str(application.id),
                day=5,
            )
        )

    assert result == {
        "status": "cancelled",
        "reason": f"application_{status}",
        "application_id": str(application.id),
    }
    replied.assert_not_called()
    assert session.added == []


@pytest.mark.asyncio
async def test_run_followup_not_found_application():
    from app.services.scheduled_jobs import FollowupTrigger, run_followup

    session = _FakeFollowupSession(None)

    with patch("app.core.database.AsyncSessionLocal", _FakeFollowupSessionLocal(session)):
        result = await run_followup(
            FollowupTrigger(user_id=str(uuid.uuid4()), application_id=str(uuid.uuid4()), day=5)
        )

    assert result["status"] == "not_found"


@pytest.mark.asyncio
async def test_followup_approval_routes_through_send_approved_email():
    """The draft's pending_action must be recognized by the shared approval
    machinery and routed through workflow_service.send_approved_email — the
    one atomic claim-before-send path — not a second, ad-hoc Gmail call."""
    from app.models.db import AgentRun
    from app.services.workflow_service import continue_action

    run = AgentRun(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        agent_type="followup",
        status="queued",
    )
    pending = {
        "type": "send_email",
        "recipient": "hr@acme.com",
        "subject": "Checking in",
        "body": "Hi there",
        "application_id": str(uuid.uuid4()),
        "day": 5,
    }

    with patch(
        "app.services.workflow_service.send_approved_email",
        AsyncMock(return_value={"sent": True, "provider_message_id": "msg-1"}),
    ) as mock_send:
        result = await continue_action(run, pending)

    mock_send.assert_called_once_with(run.user_id, run.id, "hr@acme.com", "Checking in", "Hi there")
    assert result["status"] == "completed"
    assert result["result"]["sent"] is True
