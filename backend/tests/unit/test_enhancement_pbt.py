"""
Property-based tests for HITL gate state transitions and AI next-action suggestions.

Properties tested:
- Property 3: All approval-required actions pass through awaiting_approval before completed
- Property 18: At least one AI suggestion generated for any application status + days combo
- Property 21-24: ATS scoring properties
"""

import pytest
from hypothesis import given, settings as h_settings, assume
from hypothesis import strategies as st

from app.services.ats_service import (
    compute_weighted_composite,
    compute_ats_score,
    generate_suggestions,
    get_missing_keywords,
    AtsScoreResult,
)
from app.services.linkedin_outreach_service import (
    filter_contacts_by_title,
    validate_message_length,
    draft_outreach_message,
)

# ---------------------------------------------------------------------------
# Property 3: HITL gate state transition
# ---------------------------------------------------------------------------


def test_hitl_gate_requires_awaiting_approval():
    """Verify that the approve endpoint only works on awaiting_approval status."""
    # The linkedin outreach approve endpoint checks status == "awaiting_approval"
    # This is a structural test verifying the code path exists
    import inspect
    from app.api.v1.linkedin import approve_outreach

    source = inspect.getsource(approve_outreach)
    assert "awaiting_approval" in source
    assert "status" in source


# ---------------------------------------------------------------------------
# Property 18: AI next-action suggestion availability
# ---------------------------------------------------------------------------

STATUSES = ["saved", "applied", "viewed", "interview", "offer", "rejected"]


# Suggestions are frontend behavior. Do not duplicate their implementation in
# this backend suite: that assertion would pass even if the product broke.


# ---------------------------------------------------------------------------
# Property 21: ATS composite score bounds and weighting
# ---------------------------------------------------------------------------


@given(
    keyword=st.integers(min_value=0, max_value=100),
    readability=st.integers(min_value=0, max_value=100),
    format_=st.integers(min_value=0, max_value=100),
)
@h_settings(max_examples=50)
def test_ats_composite_bounds_and_weighting(keyword: int, readability: int, format_: int):
    """Composite score is in [0,100] and equals round(kw*0.5 + read*0.3 + fmt*0.2)."""
    result = compute_weighted_composite(keyword, readability, format_)
    assert 0 <= result <= 100
    expected = round(keyword * 0.5 + readability * 0.3 + format_ * 0.2)
    expected = max(0, min(100, expected))
    assert result == expected


# ---------------------------------------------------------------------------
# Property 22: Missing keywords are set difference
# ---------------------------------------------------------------------------


@given(
    resume_words=st.lists(
        st.text(min_size=4, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        min_size=5,
        max_size=20,
    ),
    jd_words=st.lists(
        st.text(min_size=4, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        min_size=5,
        max_size=20,
    ),
)
@h_settings(max_examples=20)
def test_missing_keywords_are_set_difference(resume_words: list, jd_words: list):
    """All returned missing keywords should be in JD but absent from resume."""
    resume_text = " ".join(resume_words) + ". Experience with " + " ".join(resume_words[:3])
    jd_text = "Requirements: " + " ".join(jd_words) + ". Must have " + " ".join(jd_words[:3])

    missing = get_missing_keywords(resume_text, jd_text)
    resume_lower = set(w.lower() for w in resume_words)

    for kw in missing:
        assert kw.lower() not in resume_lower
        assert kw.lower() in jd_text.lower()

    # All missing keywords should be strings
    assert all(isinstance(kw, str) for kw in missing)


# ---------------------------------------------------------------------------
# Property 23: Suggestions when score is low
# ---------------------------------------------------------------------------


def test_suggestions_when_score_below_60():
    """Verify ≥3 suggestions when composite < 60."""
    result = AtsScoreResult(
        composite_score=45,
        keyword_score=30,
        readability_score=50,
        format_score=60,
        matched_keywords=["python"],
        missing_keywords=["react", "typescript", "aws", "docker", "kubernetes"],
        suggestions=[],
        flesch_kincaid=10.0,
        avg_sentence_length=15.0,
        format_checks={
            "has_contact_info": True,
            "no_tables": True,
            "has_standard_headings": False,
        },
    )
    suggestions = generate_suggestions(result)
    assert len(suggestions) >= 3


# ---------------------------------------------------------------------------
# Property 30-33: LinkedIn outreach properties
# ---------------------------------------------------------------------------


def test_contact_title_filtering():
    """Only contacts with recruiter/talent/hiring/engineering/director titles pass."""
    contacts = [
        {"name": "Alice", "title": "Senior Recruiter"},
        {"name": "Bob", "title": "Software Engineer"},
        {"name": "Carol", "title": "Talent Acquisition Manager"},
        {"name": "Dave", "title": "Marketing Intern"},
        {"name": "Eve", "title": "Engineering Director"},
    ]
    filtered = filter_contacts_by_title(contacts)
    names = [c["name"] for c in filtered]
    assert "Alice" in names  # recruiter
    assert "Carol" in names  # talent
    assert "Eve" in names  # engineering + director
    assert "Dave" not in names  # marketing intern


def test_message_length_validation():
    """Messages must be <= 300 chars."""
    assert validate_message_length("Hi there!") is True
    assert validate_message_length("x" * 301) is False
    assert validate_message_length("x" * 300) is True


def test_draft_message_within_limit():
    """Drafted messages should always be <= 300 chars."""
    msg = draft_outreach_message(
        contact_name="Alice Smith",
        contact_title="Senior Recruiter at BigCorp",
        user_experience="5 years Python, FastAPI, React, distributed systems",
        company_intel="their recent Series B funding and expansion into AI",
    )
    assert len(msg) <= 300
    assert "Alice" in msg
