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
