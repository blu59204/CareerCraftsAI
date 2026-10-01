"""Rules for moving an application from an inbox reply."""

import pytest

from app.models.db import JobApplication
from app.services.application_status_service import (
    match_application,
    next_status,
    normalize_company,
)


def _app(company, status="applied"):
    return JobApplication(company=company, role="Engineer", status=status)


@pytest.mark.parametrize(
    "current,category,expected",
    [
        ("applied", "VIEWED", "viewed"),
        ("applied", "INTERVIEW", "interview"),
        ("viewed", "SHORTLISTED", None),  # same level, not forward
        ("interview", "VIEWED", None),  # never backwards
        ("interview", "REJECTED", "rejected"),
        ("applied", "REJECTED", "rejected"),
        ("offer", "REJECTED", None),  # an offer is never overwritten
        ("rejected", "INTERVIEW", None),  # nor a rejection
        ("saved", "INTERVIEW", None),  # never applied to
        ("applied", "RECRUITER_MESSAGE", None),  # recorded, no status change
    ],
)
def test_status_only_moves_forward(current, category, expected):
    assert next_status(current, category) == expected


def test_company_names_match_across_suffixes_and_case():
    assert normalize_company("Acme Technologies Pvt. Ltd.") == "acme"
    assert normalize_company("ACME, Inc.") == "acme"


def test_matches_the_single_application_the_email_is_about():
    acme, other = _app("Acme Technologies Pvt Ltd"), _app("Globex")
    update = {"company": "UNKNOWN", "sender": "Acme Careers <jobs@acme.com>", "subject": "Hi"}
    assert match_application([acme, other], update) is acme


def test_two_open_applications_at_one_company_are_ambiguous():
    update = {"company": "Acme", "sender": "", "subject": "Interview invitation"}
    assert match_application([_app("Acme"), _app("Acme Inc")], update) is None


def test_a_short_name_never_matches_inside_a_longer_word():
    update = {"company": "UNKNOWN", "sender": "Facebook Jobs", "subject": "Application update"}
    assert match_application([_app("Ace")], update) is None
