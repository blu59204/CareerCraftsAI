from app.services.outreach_service import classify_thread, followup_text, initial_state


def test_only_verified_addresses_skip_the_members_eyes():
    assert initial_state("invalid", True) is None
    assert initial_state("unknown", True) == "held"
    assert initial_state("risky", False) == "held"
    assert initial_state("valid", False) == "draft"
    assert initial_state("valid", True) == "approved"


def _thread(*senders):
    return [{"id": f"m{i}", "from": sender} for i, sender in enumerate(senders)]


def test_a_reply_from_anyone_else_is_a_reply():
    thread = _thread("Me <me@gmail.com>", "Jane Roe <jane@acme.com>")
    assert classify_thread(thread, "m0") == "replied"


def test_the_members_own_messages_are_not_replies():
    assert classify_thread(_thread("me@gmail.com", "Me <me@gmail.com>"), "m0") is None
    assert classify_thread([], None) is None


def test_mail_system_notices_are_bounces_not_replies():
    thread = _thread("me@gmail.com", "Mail Delivery Subsystem <mailer-daemon@googlemail.com>")
    assert classify_thread(thread, "m0") == "bounced"


def test_followup_wording_is_fixed_and_makes_no_claims():
    subject, body = followup_text("Acme", "Backend Engineer", "Jane Roe")
    assert subject == "Following up: Backend Engineer at Acme"
    assert body.startswith("Hi Jane,")
    assert "Backend Engineer role" in body


def _row(kind="initial", state="sent", replied=False, bounced=False, minute=0):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    return SimpleNamespace(
        kind=kind,
        state=state,
        to_email="jane@acme.com",
        replied_at=datetime.now(UTC) if replied else None,
        bounced_at=datetime.now(UTC) if bounced else None,
        created_at=datetime(2026, 10, 1, 9, minute, tzinfo=UTC),
    )


def test_application_email_status_summary():
    from app.services.outreach_service import summarize_outreach

    assert summarize_outreach([]) is None
    assert summarize_outreach([_row(state="held")])["status"] == "held"
    assert summarize_outreach([_row()])["status"] == "sent"
    assert summarize_outreach([_row(), _row("followup", minute=5)])["status"] == "followed up"
    assert (
        summarize_outreach([_row(replied=True), _row("followup", "draft")])["status"] == "replied"
    )
    assert summarize_outreach([_row(bounced=True)])["status"] == "bounced"
