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
