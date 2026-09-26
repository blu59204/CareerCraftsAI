from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import UUID

import pytest

from app.api.v1.users import get_dashboard_stats


@pytest.mark.asyncio
async def test_dashboard_stats_uses_two_db_round_trips(mock_db, mock_user):
    stats_result = MagicMock()
    stats_result.one.return_value = (42, 7, Decimal("83.5"), 3)

    run = SimpleNamespace(
        id=UUID("00000000-0000-0000-0000-000000000123"),
        agent_type="resume",
        status="completed",
        started_at=datetime.fromisoformat("2026-05-30T00:00:00+00:00"),
    )
    runs_result = MagicMock()
    runs_result.scalars.return_value.all.return_value = [run]
    mock_db.execute.side_effect = [stats_result, runs_result]

    response = await get_dashboard_stats(db=mock_db, current_user=mock_user)

    assert mock_db.execute.await_count == 2
    assert response.applications_count == 42
    assert response.interviews_count == 7
    assert response.avg_match_score == 83.5
    assert response.followups_due == 3
    assert response.recent_agent_runs == [
        {
            "id": "00000000-0000-0000-0000-000000000123",
            "agent_type": "resume",
            "status": "completed",
            "created_at": "2026-05-30T00:00:00+00:00",
        }
    ]


@pytest.mark.asyncio
async def test_record_policy_consent_stamps_time_and_version(mock_db, mock_user):
    from app.api.v1.users import POLICY_VERSION, record_policy_consent

    mock_user.policy_accepted_at = None
    mock_user.policy_version = None

    response = await record_policy_consent(db=mock_db, current_user=mock_user)

    assert mock_user.policy_accepted_at is not None
    assert mock_user.policy_version == POLICY_VERSION
    assert response is mock_user
    mock_db.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_record_policy_consent_is_idempotent_and_refreshes_timestamp(mock_db, mock_user):
    """Calling it again (e.g. after a version bump) overwrites with the latest
    moment and version rather than refusing a second acceptance."""
    from datetime import UTC, datetime

    from app.api.v1.users import POLICY_VERSION, record_policy_consent

    stale = datetime(2020, 1, 1, tzinfo=UTC)
    mock_user.policy_accepted_at = stale
    mock_user.policy_version = "2020-01-01"

    await record_policy_consent(db=mock_db, current_user=mock_user)

    assert mock_user.policy_accepted_at > stale
    assert mock_user.policy_version == POLICY_VERSION


@pytest.mark.asyncio
async def test_request_account_deletion_stamps_grace_period(mock_db, mock_user):
    from datetime import UTC, datetime, timedelta

    from app.api.v1.users import DELETION_GRACE_DAYS, request_account_deletion

    mock_user.deletion_cooldown_until = None
    mock_user.deletion_requested_at = None
    mock_user.deletion_scheduled_for = None

    response = await request_account_deletion(db=mock_db, current_user=mock_user)

    assert mock_user.deletion_requested_at is not None
    expected = mock_user.deletion_requested_at + timedelta(days=DELETION_GRACE_DAYS)
    assert mock_user.deletion_scheduled_for == expected
    assert response is mock_user
    mock_db.flush.assert_awaited_once()
    # Sanity: the grace period really is ~15 days from now, not some other span.
    assert mock_user.deletion_scheduled_for > datetime.now(UTC) + timedelta(days=14)


@pytest.mark.asyncio
async def test_request_account_deletion_blocked_during_cooldown(mock_db, mock_user):
    from datetime import UTC, datetime, timedelta

    from fastapi import HTTPException

    from app.api.v1.users import request_account_deletion

    mock_user.deletion_cooldown_until = datetime.now(UTC) + timedelta(days=10)

    with pytest.raises(HTTPException) as exc_info:
        await request_account_deletion(db=mock_db, current_user=mock_user)

    assert exc_info.value.status_code == 429
    assert exc_info.value.detail["error"] == "deletion_cooldown_active"


@pytest.mark.asyncio
async def test_request_account_deletion_allowed_after_cooldown_expires(mock_db, mock_user):
    from datetime import UTC, datetime, timedelta

    from app.api.v1.users import request_account_deletion

    mock_user.deletion_cooldown_until = datetime.now(UTC) - timedelta(days=1)

    response = await request_account_deletion(db=mock_db, current_user=mock_user)

    assert mock_user.deletion_requested_at is not None
    assert response is mock_user


@pytest.mark.asyncio
async def test_cancel_account_deletion_clears_request_and_sets_cooldown(mock_db, mock_user):
    from datetime import UTC, datetime, timedelta

    from app.api.v1.users import DELETION_COOLDOWN_DAYS, cancel_account_deletion

    mock_user.deletion_requested_at = datetime.now(UTC)
    mock_user.deletion_scheduled_for = datetime.now(UTC) + timedelta(days=15)

    response = await cancel_account_deletion(db=mock_db, current_user=mock_user)

    assert mock_user.deletion_requested_at is None
    assert mock_user.deletion_scheduled_for is None
    assert mock_user.deletion_cooldown_until is not None
    expected = datetime.now(UTC) + timedelta(days=DELETION_COOLDOWN_DAYS)
    assert abs((mock_user.deletion_cooldown_until - expected).total_seconds()) < 5
    assert response is mock_user


@pytest.mark.asyncio
async def test_cancel_account_deletion_rejects_when_nothing_pending(mock_db, mock_user):
    from fastapi import HTTPException

    from app.api.v1.users import cancel_account_deletion

    mock_user.deletion_requested_at = None

    with pytest.raises(HTTPException) as exc_info:
        await cancel_account_deletion(db=mock_db, current_user=mock_user)

    assert exc_info.value.status_code == 400
