import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

UTC = timezone.utc


@pytest.mark.asyncio
async def test_schedule_followups_enqueues_two_jobs():
    from app.agents import followup_agent

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn, \
         patch("app.agents.followup_agent._enqueue_followup", new=AsyncMock(return_value="job-id")) as mock_enqueue:
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.set.return_value = True  # SET NX claim succeeds — not yet scheduled

        await followup_agent.schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(UTC),
        )

    # Day-5 and day-12 follow-ups enqueued via BullMQ
    assert mock_enqueue.call_count == 2
    # One atomic SET NX claim per day
    assert mock_r.set.call_count == 2
    mock_r.delete.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_followups_idempotent():
    from app.agents import followup_agent

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn, \
         patch("app.agents.followup_agent._enqueue_followup", new=AsyncMock(return_value="job-id")) as mock_enqueue:
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.set.return_value = None  # SET NX claim fails — already scheduled

        await followup_agent.schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(UTC),
        )

    # Already scheduled — no new jobs enqueued
    mock_enqueue.assert_not_called()


@pytest.mark.asyncio
async def test_schedule_followups_uses_distinct_key_per_day():
    """Re-running the scheduler for the same application must never
    double-schedule a single day — each day has its own stable identity."""
    from app.agents import followup_agent

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn, \
         patch("app.agents.followup_agent._enqueue_followup", new=AsyncMock(return_value="job-id")):
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.set.return_value = True

        await followup_agent.schedule_followups(
            user_id="usr_test", application_id=application_id, applied_at=datetime.now(UTC),
        )

    keys = [call.args[0] for call in mock_r.set.call_args_list]
    assert keys == [
        f"followup:scheduled:{application_id}:day5",
        f"followup:scheduled:{application_id}:day12",
    ]


@pytest.mark.asyncio
async def test_schedule_followups_delay_derived_from_applied_at_not_now():
    """Delays must drift with applied_at, not be fixed offsets from 'now' —
    scheduling a day-5 follow-up for an application applied 4 days ago
    should fire in about 1 day, not 5."""
    from app.agents import followup_agent

    application_id = str(uuid.uuid4())
    applied_at = datetime.now(UTC) - timedelta(days=4)
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn, \
         patch("app.agents.followup_agent._enqueue_followup", new=AsyncMock(return_value="job-id")) as mock_enqueue:
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.set.return_value = True

        await followup_agent.schedule_followups(
            user_id="usr_test", application_id=application_id, applied_at=applied_at,
        )

    day5_delay_ms = mock_enqueue.call_args_list[0].args[3]
    one_day_ms = 24 * 60 * 60 * 1000
    assert 0 <= day5_delay_ms <= one_day_ms + 5000


# ---------------------------------------------------------------------------
# run_followup (execution side) — backend/app/api/internal.py
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


def _make_application(applied_at=None):
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        company="Acme",
        role="Engineer",
        applied_at=applied_at or datetime.now(UTC),
        followup_day5=datetime.now(UTC) + timedelta(days=1),
        followup_day12=datetime.now(UTC) + timedelta(days=8),
    )


@pytest.mark.asyncio
async def test_run_followup_due_with_no_reply_creates_draft_checkpoint_not_send():
    """A due follow-up with no recruiter reply must produce a draft awaiting
    approval — never send anything itself."""
    from app.api.internal import FollowupTrigger, run_followup

    application = _make_application()
    session = _FakeFollowupSession(application)

    with patch("app.core.database.AsyncSessionLocal", _FakeFollowupSessionLocal(session)), \
         patch("app.api.internal._has_recruiter_replied", AsyncMock(return_value=False)), \
         patch(
             "app.services.email_finder_service.find_recruiter_email",
             AsyncMock(return_value={"email": "hr@acme.com"}),
         ), \
         patch(
             "app.agents.followup_agent.build_followup_draft",
             return_value={"subject": "Checking in", "body": "Hi there"},
         ), \
         patch("app.api.internal.emit") as mock_emit:
        result = await run_followup(FollowupTrigger(
            user_id=str(application.user_id), application_id=str(application.id), day=5,
        ))

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
    from app.api.internal import FollowupTrigger, run_followup

    application = _make_application()
    session = _FakeFollowupSession(application)

    with patch("app.core.database.AsyncSessionLocal", _FakeFollowupSessionLocal(session)), \
         patch("app.api.internal._has_recruiter_replied", AsyncMock(return_value=True)):
        result = await run_followup(FollowupTrigger(
            user_id=str(application.user_id), application_id=str(application.id), day=5,
        ))

    assert result["status"] == "cancelled"
    assert result["reason"] == "recruiter_replied"
    assert application.followup_day5 is None
    assert application.followup_day12 is None
    assert session.added == []  # no draft/AgentRun created
    assert session.commits == 1


@pytest.mark.asyncio
async def test_run_followup_not_found_application():
    from app.api.internal import FollowupTrigger, run_followup

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
        id=uuid.uuid4(), user_id=uuid.uuid4(), agent_type="followup", status="queued",
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
