import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

UTC = timezone.utc


@pytest.mark.asyncio
async def test_schedule_followups_enqueues_two_jobs():
    from app.agents.followup_agent import schedule_followups

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn:
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.sismember.return_value = False

        await schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(UTC),
        )

    assert mock_r.rpush.call_count == 2


@pytest.mark.asyncio
async def test_schedule_followups_idempotent():
    from app.agents.followup_agent import schedule_followups

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn:
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.sismember.return_value = True  # already scheduled

        await schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(UTC),
        )

    mock_r.rpush.assert_not_called()
