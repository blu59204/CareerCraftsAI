"""/health's Temporal block reports pollers for the main and notification queues."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from temporalio.api.enums.v1 import TaskQueueType

from app.core import temporal_client
from app.core.config import settings

WORKFLOW = TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW
ACTIVITY = TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY


def _client(pollers: dict[tuple[str, int], int]) -> SimpleNamespace:
    async def describe(request):
        key = (request.task_queue.name, request.task_queue_type)
        if key not in pollers:
            raise RuntimeError("boom")
        return SimpleNamespace(pollers=[object()] * pollers[key])

    return SimpleNamespace(
        service_client=SimpleNamespace(check_health=AsyncMock()),
        workflow_service=SimpleNamespace(describe_task_queue=describe),
    )


async def test_health_reports_every_queue(monkeypatch):
    client = _client(
        {
            (settings.TEMPORAL_TASK_QUEUE, WORKFLOW): 2,
            (settings.TEMPORAL_NOTIFICATION_TASK_QUEUE, WORKFLOW): 1,
            (settings.TEMPORAL_NOTIFICATION_EMAIL_TASK_QUEUE, ACTIVITY): 3,
        }
    )
    monkeypatch.setattr(temporal_client, "get_temporal_client", AsyncMock(return_value=client))

    assert await temporal_client.check_temporal_health() == {
        "connected": True,
        "workers": 2,
        "task_queue": settings.TEMPORAL_TASK_QUEUE,
        "notification_workers": 1,
        "notification_email_workers": 3,
    }


async def test_unknown_queue_is_none_not_an_error(monkeypatch):
    # Only the main queue answers; the notification queues' describe raises.
    client = _client({(settings.TEMPORAL_TASK_QUEUE, WORKFLOW): 1})
    monkeypatch.setattr(temporal_client, "get_temporal_client", AsyncMock(return_value=client))

    health = await temporal_client.check_temporal_health()

    assert health["workers"] == 1
    assert health["notification_workers"] is None
    assert health["notification_email_workers"] is None
