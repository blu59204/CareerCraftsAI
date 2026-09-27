"""Unit tests for notification_activities — called directly (activity.defn
leaves the function itself callable), DB session and dependencies mocked,
matching this repo's existing activity-level test convention (see
job_activities.maintenance_activity / agent_activities in test_workflow_runtime.py)."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from temporalio.exceptions import ApplicationError

from app.workflows import notification_activities


def _session_cm(db):
    """AsyncSessionLocal() is used as `async with AsyncSessionLocal() as db`
    — wrap a mock db in a minimal async context manager returning it."""

    class _CM:
        async def __aenter__(self):
            return db

        async def __aexit__(self, *exc):
            return False

    return _CM()


@pytest.mark.asyncio
async def test_create_notification_activity_returns_ids_when_delivery_created():
    db = AsyncMock()
    notification_id = uuid.uuid4()
    delivery_id = uuid.uuid4()
    notification = SimpleNamespace(id=notification_id)
    delivery = SimpleNamespace(id=delivery_id)

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch(
            "app.services.notification_service.create_notification",
            AsyncMock(return_value=notification),
        ),
        patch(
            "app.services.notification_service.get_pending_email_delivery",
            AsyncMock(return_value=delivery),
        ),
    ):
        result = await notification_activities.create_notification_activity(
            {
                "user_id": str(uuid.uuid4()),
                "type": "job_matches",
                "title": "Found jobs",
                "body": None,
                "link": None,
            }
        )

    assert result == {
        "notification_id": str(notification_id),
        "email_delivery_id": str(delivery_id),
    }
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_create_notification_activity_returns_none_ids_when_gated_off():
    db = AsyncMock()

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch(
            "app.services.notification_service.create_notification", AsyncMock(return_value=None)
        ),
    ):
        result = await notification_activities.create_notification_activity(
            {"user_id": str(uuid.uuid4()), "type": "job_matches", "title": "Found jobs"}
        )

    assert result == {"notification_id": None, "email_delivery_id": None}


@pytest.mark.asyncio
async def test_send_notification_email_activity_marks_sent_on_success():
    db = AsyncMock()
    user = SimpleNamespace(email="a@b.com")
    db.get = AsyncMock(return_value=user)

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch("app.services.notification_service.mark_delivery_attempt", AsyncMock()) as mock_mark,
        patch("app.services.resend_service.send_transactional_email", return_value={"id": "x"}),
    ):
        result = await notification_activities.send_notification_email_activity(
            {
                "delivery_id": str(uuid.uuid4()),
                "user_id": str(uuid.uuid4()),
                "title": "Hi",
                "body": "body text",
            }
        )

    assert result == {"status": "sent"}
    mock_mark.assert_awaited_once()
    assert mock_mark.call_args.kwargs["status"] == "sent"


@pytest.mark.asyncio
async def test_send_notification_email_activity_skips_when_no_user_email():
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch("app.services.notification_service.mark_delivery_attempt", AsyncMock()) as mock_mark,
    ):
        result = await notification_activities.send_notification_email_activity(
            {"delivery_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()), "title": "Hi"}
        )

    assert result == {"status": "skipped"}
    assert mock_mark.call_args.kwargs["status"] == "dead"


@pytest.mark.asyncio
async def test_send_notification_email_activity_rate_limited_raises_application_error():
    from app.services.resend_service import EmailRateLimited

    db = AsyncMock()
    user = SimpleNamespace(email="a@b.com")
    db.get = AsyncMock(return_value=user)

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch("app.services.notification_service.mark_delivery_attempt", AsyncMock()) as mock_mark,
        patch(
            "app.services.resend_service.send_transactional_email",
            side_effect=EmailRateLimited(retry_after=12),
        ),
    ):
        with pytest.raises(ApplicationError) as exc_info:
            await notification_activities.send_notification_email_activity(
                {"delivery_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()), "title": "Hi"}
            )

    assert exc_info.value.next_retry_delay is not None
    assert mock_mark.call_args.kwargs["status"] == "pending"


@pytest.mark.asyncio
async def test_send_notification_email_activity_rejected_raises_non_retryable():
    from app.services.resend_service import EmailRejected

    db = AsyncMock()
    user = SimpleNamespace(email="a@b.com")
    db.get = AsyncMock(return_value=user)

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch("app.services.notification_service.mark_delivery_attempt", AsyncMock()) as mock_mark,
        patch(
            "app.services.resend_service.send_transactional_email",
            side_effect=EmailRejected("bad request"),
        ),
    ):
        with pytest.raises(ApplicationError) as exc_info:
            await notification_activities.send_notification_email_activity(
                {"delivery_id": str(uuid.uuid4()), "user_id": str(uuid.uuid4()), "title": "Hi"}
            )

    assert exc_info.value.non_retryable is True
    assert mock_mark.call_args.kwargs["status"] == "dead"


@pytest.mark.asyncio
async def test_mark_delivery_dead_activity_calls_service():
    db = AsyncMock()
    delivery_id = uuid.uuid4()

    with (
        patch("app.core.database.AsyncSessionLocal", return_value=_session_cm(db)),
        patch("app.services.notification_service.mark_delivery_dead", AsyncMock()) as mock_dead,
    ):
        await notification_activities.mark_delivery_dead_activity({"delivery_id": str(delivery_id)})

    mock_dead.assert_awaited_once_with(db, delivery_id)
