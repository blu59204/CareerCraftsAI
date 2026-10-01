"""Regression tests for the second code review."""

from types import SimpleNamespace

import pytest

from app.applications.question_normalizer import normalize_question
from app.core.rate_limit import _get_user_or_ip
from app.services.llm_proxy_service import redact_keys
from app.services.scheduled_jobs import _automated_sender


@pytest.mark.parametrize(
    "label,key",
    [
        ("Are you authorized to work in the US?", "authorization.work_authorized"),
        ("Right to work in UK", "authorization.work_authorized"),
        ("Expected compensation", "compensation.expected_salary"),
        ("Expected CTC (LPA)", "compensation.expected_salary"),
        ("Pay expectations", "compensation.expected_salary"),
        ("Current CTC", "compensation.current_salary"),
        ("When can you start?", "availability.start_date"),
        ("City", "location.city"),
    ],
)
def test_sensitive_questions_are_recognised(label, key):
    assert normalize_question(label) == key


@pytest.mark.parametrize("label", ["Ethnicity", "Capacity to travel"])
def test_city_needs_a_whole_word(label):
    assert normalize_question(label) != "location.city"


def test_only_resume_fields_get_the_resume():
    from app.applications.models import ApplicationField
    from app.services.extension_service import RESUME_TOKEN, _file_answer

    def field(label):
        return ApplicationField(field_id="f", label=label, input_type="file", required=False)

    assert _file_answer(field("Resume/CV")) == RESUME_TOKEN
    assert _file_answer(field("Upload your passport")) is None
    assert _file_answer(field("Upload photo ID")) is None
    assert _file_answer(field("Cover letter")) is None
    assert _file_answer(field("Upload")) is None


def test_redaction_leaves_ordinary_words_and_hashes_alone():
    assert redact_keys("risk-based-testing-approach and task-oriented-workflow-engine") == (
        "risk-based-testing-approach and task-oriented-workflow-engine"
    )
    sha = "a" * 40
    assert redact_keys(f"commit {sha}") == f"commit {sha}"
    assert "[REDACTED]" in redact_keys("key sk-abcdefghijklmnopqrstuvwxyz123456")


def test_rate_limit_ignores_an_unverified_token_subject():
    import jwt

    forged = jwt.encode({"sub": "random-1"}, "x", algorithm="HS256")

    def request(user=None):
        return SimpleNamespace(
            headers={"authorization": f"Bearer {forged}"},
            state=SimpleNamespace(user=user),
            client=SimpleNamespace(host="203.0.113.9"),
            scope={"type": "http"},
        )

    assert _get_user_or_ip(request()) == "203.0.113.9"
    assert _get_user_or_ip(request({"sub": "user_1"})) == "user_1"


def test_ats_confirmations_are_not_a_recruiter_reply():
    assert _automated_sender("careers <no-reply@greenhouse-mail.io>")
    assert _automated_sender("acme <jobs@myworkday.com>")
    assert not _automated_sender("jane roe <jane@acme.com>")


def test_job_that_could_not_be_scored_is_not_eligible(monkeypatch):
    from app.agents import auto_apply_pipeline as pipeline

    def boom(*args, **kwargs):
        raise RuntimeError("model down")

    monkeypatch.setattr("app.agents.thinking.think_about_job_match", boom)
    assert (
        pipeline._score_job_quick(
            object(), SimpleNamespace(title="t", company="c", description="d"), "p"
        )
        == 0
    )


def test_funding_bonus_cannot_lift_a_job_over_the_threshold(monkeypatch):
    from app.core.config import settings
    from app.services.funding_signals import with_bonus

    monkeypatch.setattr(settings, "AUTO_APPLY_MIN_SCORE", 70)
    assert with_bonus(68) == 69
    assert with_bonus(40) == 45
    assert with_bonus(72) == 77
    assert with_bonus(98) == 100
