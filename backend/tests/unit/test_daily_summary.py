from app.services.daily_summary import format_summary

QUIET = {
    "applied": 0,
    "status_changes": 0,
    "emails_sent": 0,
    "replies": 0,
    "bounces": 0,
    "needs_approval": 0,
}


def test_a_quiet_day_sends_nothing():
    assert format_summary(QUIET) is None


def test_summary_lists_only_what_happened_and_what_waits_for_the_member():
    title, body = format_summary({**QUIET, "applied": 4, "replies": 1, "needs_approval": 2})
    assert title == "Your CareerCraft day in review"
    assert body.splitlines() == [
        "Applications submitted: 4",
        "Recruiters who replied: 1",
        "Waiting for you: 2 recruiter email(s) waiting for your approval",
    ]


def test_waiting_work_alone_is_enough_to_send():
    assert format_summary({**QUIET, "needs_approval": 1}) is not None
