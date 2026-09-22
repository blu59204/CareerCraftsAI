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
    return Request({
        "type": "http",
        "method": "POST",
        "path": "/api/v1/agents/run",
        "headers": [],
        "client": ("test", 1),
        "server": ("testserver", 80),
        "scheme": "http",
    })


@pytest.mark.asyncio
async def test_approval_runs_do_not_consume_admission_slots(monkeypatch):
    from app.api.v1 import agents

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
async def test_recovery_expires_approvals_and_times_out_runs(monkeypatch):
    from app.services import workflow_service

    now = datetime.now(timezone.utc)
    approval = SimpleNamespace(
        status="awaiting_approval",
        started_at=now - timedelta(hours=49),
        output=None,
        completed_at=None,
    )
    running = SimpleNamespace(
        status="running",
        agent_type="resume_optimize",
        started_at=now - timedelta(seconds=121),
        output=None,
        completed_at=None,
    )

    db = MagicMock()
    db.execute = AsyncMock(side_effect=[
        _result([]),
        _result([approval]),
        _result([running]),
    ])
    db.commit = AsyncMock()

    class Session:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(workflow_service, "AsyncSessionLocal", lambda: Session())
    await workflow_service.recover_expired_tasks()

    assert approval.status == "expired"
    assert approval.output == {"error": "Approval expired after 48 hours"}
    assert running.status == "failed"
    assert running.output == {"error": "Worker did not report completion (timeout)"}
    db.commit.assert_awaited_once()
