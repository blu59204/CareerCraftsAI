import base64

from app.services.attention_notices import attention_text
from app.services.email_answers import (
    member_reply,
    message_text,
    parse_answers,
    question_lines,
    ref_for,
    reply_only,
)

QUESTIONS = [{"key": "a", "label": "Notice period"}, {"key": "b", "label": "Expected salary"}]


def _b64(text):
    return base64.urlsafe_b64encode(text.encode()).decode()


def test_numbered_lines_become_answers_and_quoted_mail_is_ignored():
    text = "1: 30 days\n2) 12 LPA\nnegotiable\n\nOn Mon, 5 Oct, CareerCraft wrote:\n> 3: ignore"
    assert parse_answers(text, 2) == {1: "30 days", 2: "12 LPA negotiable"}


def test_a_single_question_can_be_answered_in_plain_text():
    assert parse_answers("Yes, I can relocate\n\n> quoted", 1) == {1: "Yes, I can relocate"}
    assert parse_answers("random words", 2) == {}


def test_numbers_outside_the_list_are_ignored():
    assert parse_answers("5: nope\n1: ok", 2) == {1: "ok"}


def test_reply_only_stops_at_the_quote():
    assert reply_only("answer\n> old") == "answer"


def test_message_text_reads_nested_plain_part():
    message = {
        "payload": {
            "mimeType": "multipart/alternative",
            "parts": [
                {"mimeType": "text/plain", "body": {"data": _b64("1: hello")}},
                {"mimeType": "text/html", "body": {"data": _b64("<b>x</b>")}},
            ],
        }
    }
    assert message_text(message) == "1: hello"


def test_only_the_members_own_message_counts_as_an_answer():
    def msg(sender, when):
        return {
            "id": sender,
            "internalDate": str(when),
            "payload": {"headers": [{"name": "From", "value": sender}]},
        }

    thread = {
        "messages": [
            msg("CareerCraft <noreply@jobagent.ai>", 1),
            msg("Me <me@example.com>", 2),
            msg("someone@else.com", 3),
        ]
    }
    assert member_reply(thread, "ME@example.com")["id"] == "Me <me@example.com>"
    assert member_reply(thread, "other@example.com") is None


def test_the_email_lists_questions_and_a_reference_to_reply_to():
    ref = ref_for("12345678-aaaa-bbbb-cccc-dddddddddddd")
    assert ref == "CC-12345678"
    title, body = attention_text("needs_input", "Acme", "Eng", QUESTIONS, ref)
    assert question_lines(QUESTIONS) in body and ref in body and "Reply to this email" in body
    # no known questions: the old short text
    assert "Reply" not in attention_text("needs_input", "Acme", "Eng")[1]
    assert "Reply" not in attention_text("login_required", "Acme", "Eng", QUESTIONS, ref)[1]
