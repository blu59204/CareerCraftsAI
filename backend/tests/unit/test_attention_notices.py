import asyncio
from unittest.mock import AsyncMock, patch

from app.services.attention_notices import attention_text, notify_needs_attention
from app.workflows.notification_activities import _email_html

USER = "11111111-1111-1111-1111-111111111111"


def test_only_stages_that_need_the_member_have_text():
    title, body = attention_text("login_required", "Acme", "Engineer")
    assert title == "Your application to Engineer at Acme is waiting for you"
    assert "CAPTCHA" in body
    assert attention_text("filling", "Acme", "Engineer") is None
    assert attention_text("needs_input", None, None)[0].startswith("Your application to your")


def _notify(stage, previous, payload=None):
    start = AsyncMock()
    with patch("app.workflows.starters.start_notification", start):
        sent = asyncio.run(notify_needs_attention(USER, stage, previous, payload))
    return sent, start


def test_one_notice_when_a_task_newly_needs_the_member():
    sent, start = _notify("needs_input", "filling", {"company": "Acme", "role": "Eng"})
    assert sent and start.call_args.kwargs["type"] == "application_needs_you"
    # staying in the same stage does not email again
    assert _notify("needs_input", "needs_input")[0] is False
    assert _notify("filling", "claimed")[0] is False


def test_a_failed_notification_never_blocks_the_application():
    start = AsyncMock(side_effect=RuntimeError("temporal down"))
    with patch("app.workflows.starters.start_notification", start):
        assert asyncio.run(notify_needs_attention(USER, "needs_input", "filling", {})) is False


def test_scraped_names_cannot_inject_html_into_the_email():
    html = _email_html("t", "<script>alert(1)</script> Evil & Co", "/applications")
    assert "<script>" not in html and "&amp;" in html
    assert 'href="http' in html
    assert "javascript:" not in _email_html("t", "b", "javascript:alert(1)")
