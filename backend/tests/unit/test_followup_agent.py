import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch


def test_schedule_followups_enqueues_two_jobs():
    from app.agents.followup_agent import schedule_followups

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn:
        mock_r = MagicMock()
        mock_redis_fn.return_value = mock_r
        mock_r.sismember.return_value = False

        schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(timezone.utc),
        )

    assert mock_r.rpush.call_count == 2
    pushed_args = [call[0] for call in mock_r.rpush.call_args_list]
    assert all(a[0] == "bull:agent-queue:wait" for a in pushed_args)


def test_schedule_followups_idempotent():
    from app.agents.followup_agent import schedule_followups

    application_id = str(uuid.uuid4())
    with patch("app.agents.followup_agent._get_redis") as mock_redis_fn:
        mock_r = MagicMock()
        mock_redis_fn.return_value = mock_r
        mock_r.sismember.return_value = True  # already scheduled

        schedule_followups(
            user_id="usr_test",
            application_id=application_id,
            applied_at=datetime.now(timezone.utc),
        )

    mock_r.rpush.assert_not_called()
