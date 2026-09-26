from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from starlette.requests import Request


def _result(rows):
    result = MagicMock()
    result.scalars.return_value.all.return_value = rows
    return result


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/v1/agents/run",
            "headers": [],
            "client": ("test", 1),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


@pytest.mark.asyncio
async def test_approval_runs_do_not_consume_admission_slots(monkeypatch):
    from app.api.v1 import agents
    from app.workflows import starters

    start = AsyncMock(return_value="agent-run/x")
    monkeypatch.setattr(starters, "start_agent_run", start)
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[MagicMock(), _result([])])
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.add = MagicMock()
    user = SimpleNamespace(id="user-1")
    request = _request()

    response = await agents.run_agent(
        request,
        agents.RunRequest(task_type="resume_optimize"),
        db,
        user,
    )

    assert response["status"] == "queued"
    db.add.assert_called()
    # The row is committed before the workflow that reads it is started.
    db.commit.assert_awaited()
    start.assert_awaited_once_with(response["run_id"], "user-1")


@pytest.mark.asyncio
async def test_run_fails_visibly_when_temporal_is_unreachable(monkeypatch):
    """A run must never sit in "queued" forever because no workflow was
    started — the original "workflows are not getting scheduled" bug."""
    from app.api.v1 import agents
    from app.workflows import starters

    monkeypatch.setattr(
        starters,
        "start_agent_run",
        AsyncMock(side_effect=starters.WorkflowUnavailable("down")),
    )
    db = MagicMock()
    db.execute = AsyncMock(side_effect=[MagicMock(), _result([])])
    db.commit = AsyncMock()
    added = []
    db.add = MagicMock(side_effect=added.append)

    with pytest.raises(HTTPException) as exc:
        await agents.run_agent(
            _request(),
            agents.RunRequest(task_type="resume_optimize"),
            db,
            SimpleNamespace(id="user-1"),
        )

    assert exc.value.status_code == 503
    assert added[0].status == "failed"
    assert added[0].completed_at is not None


@pytest.mark.asyncio
async def test_concurrency_error_includes_active_run_ids(monkeypatch):
    from app.api.v1 import agents

    db = MagicMock()
    active = MagicMock()
    active.scalars.return_value.all.return_value = ["run-1", "run-2"]
    db.execute = AsyncMock(side_effect=[MagicMock(), active])
    user = SimpleNamespace(id="user-1")
    request = _request()

    with pytest.raises(HTTPException) as exc:
        await agents.run_agent(
            request,
            agents.RunRequest(task_type="resume_optimize"),
            db,
            user,
        )

    assert exc.value.status_code == 429
    assert exc.value.detail["run_ids"] == ["run-1", "run-2"]


@pytest.mark.asyncio
async def test_maintenance_reconciles_runs_whose_workflow_is_gone(monkeypatch):
    """Runs whose workflow no longer runs are closed out; runs with a live
    workflow are left alone; old checkpoints with no workflow expire."""
    import uuid

    from temporalio.client import WorkflowExecutionStatus
    from temporalio.service import RPCError, RPCStatusCode

    from app.workflows import job_activities

    now = datetime.now(timezone.utc)
    orphan = SimpleNamespace(
        id=uuid.uuid4(),
        status="running",
        agent_type="resume_optimize",
        input={},
        started_at=now - timedelta(hours=1),
        output=None,
        completed_at=None,
    )
    live = SimpleNamespace(
        id=uuid.uuid4(),
        status="running",
        agent_type="resume_optimize",
        input={},
        started_at=now - timedelta(hours=1),
        output=None,
        completed_at=None,
    )
    stale_checkpoint = SimpleNamespace(
        id=uuid.uuid4(),
        status="awaiting_approval",
        agent_type="followup",
        input={},
        started_at=now - timedelta(days=3),
        output=None,
        completed_at=None,
    )
    rows = {r.id: r for r in (orphan, live, stale_checkpoint)}

    calls = []

    def execute(*_args, **_kwargs):
        # First query selects candidate runs; later ones their extension tasks.
        calls.append(1)
        return _result(list(rows.values()) if len(calls) == 1 else [])

    db = MagicMock()
    db.execute = AsyncMock(side_effect=execute)
    db.get = AsyncMock(side_effect=lambda _model, run_id, **_k: rows.get(run_id))
    db.commit = AsyncMock()

    class Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return False

    def describe_for(workflow_id):
        handle = MagicMock()
        if workflow_id.endswith(str(live.id)):
            handle.describe = AsyncMock(
                return_value=SimpleNamespace(status=WorkflowExecutionStatus.RUNNING)
            )
        else:
            handle.describe = AsyncMock(side_effect=RPCError("gone", RPCStatusCode.NOT_FOUND, b""))
        return handle

    client = MagicMock()
    client.get_workflow_handle = MagicMock(side_effect=describe_for)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: Session())
    monkeypatch.setattr(
        "app.core.temporal_client.get_temporal_client", AsyncMock(return_value=client)
    )
    monkeypatch.setattr("app.core.event_bus.publish", MagicMock())

    result = await job_activities.maintenance_activity({})

    assert result == {"reconciled": 2}
    assert orphan.status == "failed"
    assert live.status == "running"
    assert stale_checkpoint.status == "expired"
