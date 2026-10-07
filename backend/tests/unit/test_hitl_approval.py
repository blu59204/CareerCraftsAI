"""Exercise production persistence rather than a copied branch."""
import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("status", ["awaiting_approval", "completed", "failed"])
async def test_record_run_result_preserves_payload_and_publishes_after_commit(monkeypatch, status):
    from app.workflows.agent_activities import record_run_result

    pending, result = {"type": "send_email", "body": "Review"}, {"jobs_found": 5}
    run = SimpleNamespace(status="running", output=None, completed_at=None)
    db = SimpleNamespace(get=AsyncMock(return_value=run), commit=AsyncMock())

    class Session:
        async def __aenter__(self):
            return db
        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr("app.core.database.AsyncSessionLocal", Session)
    published = []
    def publish(run_id, event, output):
        assert db.commit.await_count == 1
        published.append((event, output))
    monkeypatch.setattr("app.core.event_bus.publish", publish)
    outcome = await record_run_result(str(uuid.uuid4()), {
        "status": status, "pending_action": pending, "result": result,
    })
    expected = pending if status == "awaiting_approval" else result
    assert run.output == expected and run.status == status
    assert (run.completed_at is None) == (status == "awaiting_approval")
    assert published == [({"awaiting_approval": "checkpoint", "completed": "complete", "failed": "error"}[status], expected)]
    assert outcome["status"] == status


@pytest.mark.asyncio
async def test_result_never_overwrites_cancellation(monkeypatch):
    from app.workflows.agent_activities import record_run_result

    run = SimpleNamespace(status="failed", output={"error": "Action cancelled by user"})
    db = SimpleNamespace(get=AsyncMock(return_value=run), commit=AsyncMock())
    class Session:
        async def __aenter__(self):
            return db
        async def __aexit__(self, *args):
            return False
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", Session)
    published = []
    monkeypatch.setattr("app.core.event_bus.publish", lambda *args: published.append(args))
    await record_run_result(str(uuid.uuid4()), {"status": "completed", "result": {}})
    assert run.output == {"error": "Action cancelled by user"}
    assert published == []
    db.commit.assert_not_awaited()
