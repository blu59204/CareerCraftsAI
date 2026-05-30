import uuid
from datetime import datetime, timezone
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
        mock_r.exists.return_value = False  # not yet scheduled

        await followup_agent.schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(UTC),
        )

    # Day-5 and day-12 follow-ups enqueued via BullMQ
    assert mock_enqueue.call_count == 2
    # Idempotency key set with TTL
    mock_r.setex.assert_called_once()


@pytest.mark.asyncio
async def test_schedule_followups_idempotent():
    from app.agents import followup_agent

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn, \
         patch("app.agents.followup_agent._enqueue_followup", new=AsyncMock(return_value="job-id")) as mock_enqueue:
        mock_r = AsyncMock()
        mock_redis_fn.return_value = mock_r
        mock_r.exists.return_value = True  # already scheduled

        await followup_agent.schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(UTC),
        )

    # Already scheduled — no new jobs enqueued
    mock_enqueue.assert_not_called()
