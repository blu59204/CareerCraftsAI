import asyncio
from unittest.mock import AsyncMock, patch

from app.workflows.job_activities import inbox_status_activity

USER = "11111111-1111-1111-1111-111111111111"


def _run(changes, notify):
    outcome = {"status": "completed", "result": {"changes": changes}}
    with (
        patch(
            "app.services.application_status_service.scan_inbox_for_member", return_value=outcome
        ),
        patch("app.workflows.starters.start_notification", notify),
    ):
        return asyncio.run(inbox_status_activity({"user_id": USER}))


def test_one_move_names_the_company_and_status():
    notify = AsyncMock()
    change = {"company": "Stripe", "role": "Engineer", "to_status": "interview"}
    assert _run([change], notify) == {"changes": 1}
    kwargs = notify.call_args.kwargs
    assert kwargs["type"] == "application_update"
    assert kwargs["title"] == "Stripe: application moved to interview"
    assert kwargs["link"] == "/applications"


def test_no_changes_sends_nothing():
    notify = AsyncMock()
    assert _run([], notify) == {"changes": 0}
    notify.assert_not_called()


def test_notification_failure_does_not_fail_the_scan():
    notify = AsyncMock(side_effect=RuntimeError("temporal down"))
    change = {"company": "A", "role": "r", "to_status": "viewed"}
    assert _run([change, change], notify) == {"changes": 2}
