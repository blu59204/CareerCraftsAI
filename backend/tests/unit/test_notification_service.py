"""Unit tests for notification_service — DB session mocked throughout
(no live database), per this repo's convention for service-layer tests."""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services import notification_service


def make_prefs(**overrides) -> SimpleNamespace:
    defaults = {
        "notify_email": True,
        "notify_agent_alerts": True,
        "notify_followup_reminders": True,
        "notify_weekly_digest": False,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


@pytest.mark.asyncio
async def test_create_notification_skipped_when_gate_preference_off():
    db = AsyncMock()
    db.add = MagicMock()
    user_id = uuid.uuid4()

    with (
        patch.object(
            notification_service,
            "_get_preferences",
            AsyncMock(return_value=make_prefs(notify_agent_alerts=False)),
        ),
        patch.object(
            notification_service,
            "spawn_background",
            MagicMock(side_effect=lambda coro: coro.close()),
        ) as mock_spawn,
    ):
        result = await notification_service.create_notification(
            db, user_id, type="job_matches", title="Found 3 jobs"
        )

    assert result is None
    db.add.assert_not_called()
    mock_spawn.assert_not_called()


@pytest.mark.asyncio
async def test_create_notification_creates_when_gate_preference_on():
    db = AsyncMock()
    db.add = MagicMock()
    user_id = uuid.uuid4()

    with (
        patch.object(
            notification_service, "_get_preferences", AsyncMock(return_value=make_prefs())
        ),
        patch.object(
            notification_service,
            "spawn_background",
            MagicMock(side_effect=lambda coro: coro.close()),
        ) as mock_spawn,
    ):
        result = await notification_service.create_notification(
            db, user_id, type="job_matches", title="Found 3 jobs", body="details", link="/jobs"
        )

    assert result is not None
    assert result.user_id == user_id
    assert result.type == "job_matches"
    assert result.title == "Found 3 jobs"
    assert result.body == "details"
    assert result.link == "/jobs"
    db.add.assert_called_once_with(result)
    mock_spawn.assert_called_once()


@pytest.mark.asyncio
async def test_create_notification_created_when_user_has_no_preferences_row():
    """A brand-new user with no UserPreferences row yet must still get
    notified — missing preferences default to the settings page's own
    on-by-default toggles, not to "notifications off"."""
    db = AsyncMock()
    db.add = MagicMock()
    user_id = uuid.uuid4()

    with (
        patch.object(notification_service, "_get_preferences", AsyncMock(return_value=None)),
        patch.object(
            notification_service,
            "spawn_background",
            MagicMock(side_effect=lambda coro: coro.close()),
        ) as mock_spawn,
    ):
        result = await notification_service.create_notification(
            db, user_id, type="followup_ready", title="Draft ready"
        )

    assert result is not None
    mock_spawn.assert_called_once()


@pytest.mark.asyncio
async def test_create_notification_skips_email_when_notify_email_off():
    db = AsyncMock()
    db.add = MagicMock()
    user_id = uuid.uuid4()

    with (
        patch.object(
            notification_service,
            "_get_preferences",
            AsyncMock(return_value=make_prefs(notify_email=False)),
        ),
        patch.object(
            notification_service,
            "spawn_background",
            MagicMock(side_effect=lambda coro: coro.close()),
        ) as mock_spawn,
    ):
        result = await notification_service.create_notification(
            db, user_id, type="job_matches", title="Found 3 jobs"
        )

    assert result is not None
    mock_spawn.assert_not_called()


@pytest.mark.asyncio
async def test_create_notification_ungated_type_always_created_even_if_all_prefs_off():
    db = AsyncMock()
    db.add = MagicMock()
    user_id = uuid.uuid4()

    with (
        patch.object(
            notification_service,
            "_get_preferences",
            AsyncMock(
                return_value=make_prefs(
                    notify_agent_alerts=False, notify_followup_reminders=False, notify_email=False
                )
            ),
        ),
        patch.object(
            notification_service,
            "spawn_background",
            MagicMock(side_effect=lambda coro: coro.close()),
        ),
    ):
        result = await notification_service.create_notification(
            db, user_id, type="account_security", title="New sign-in detected"
        )

    assert result is not None


@pytest.mark.asyncio
async def test_mark_read_sets_read_at_when_unread():
    db = AsyncMock()
    db.add = MagicMock()
    notification = SimpleNamespace(read_at=None)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = notification
    db.execute = AsyncMock(return_value=result_mock)

    ok = await notification_service.mark_read(db, uuid.uuid4(), uuid.uuid4())

    assert ok is True
    assert notification.read_at is not None


@pytest.mark.asyncio
async def test_mark_read_is_idempotent_on_already_read():
    db = AsyncMock()
    db.add = MagicMock()
    already_read_at = object()
    notification = SimpleNamespace(read_at=already_read_at)
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = notification
    db.execute = AsyncMock(return_value=result_mock)

    ok = await notification_service.mark_read(db, uuid.uuid4(), uuid.uuid4())

    assert ok is True
    assert notification.read_at is already_read_at


@pytest.mark.asyncio
async def test_mark_read_returns_false_when_not_found_or_not_owned():
    db = AsyncMock()
    db.add = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    ok = await notification_service.mark_read(db, uuid.uuid4(), uuid.uuid4())

    assert ok is False


@pytest.mark.asyncio
async def test_list_notifications_returns_rows_and_unread_count():
    db = AsyncMock()
    db.add = MagicMock()
    rows = [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())]

    list_result = MagicMock()
    list_result.scalars.return_value.all.return_value = rows
    count_result = MagicMock()
    count_result.scalar_one.return_value = 2
    db.execute = AsyncMock(side_effect=[list_result, count_result])

    notifications, unread_count = await notification_service.list_notifications(db, uuid.uuid4())

    assert notifications == rows
    assert unread_count == 2


@pytest.mark.asyncio
async def test_mark_all_read_issues_a_single_bulk_update():
    db = AsyncMock()
    db.add = MagicMock()
    await notification_service.mark_all_read(db, uuid.uuid4())
    db.execute.assert_awaited_once()
