"""Unit tests for ATS Service — scoring, keyword extraction, suggestions."""
import pytest
from app.services.ats_service import (
    compute_ats_score,
    get_missing_keywords,
    generate_suggestions,
    compute_weighted_composite,
    AtsScoreResult,
)


def test_ats_score_in_range():
    result = compute_ats_score(
        "Python Django REST API AWS Docker CI/CD PostgreSQL Redis Kubernetes",
        "Python AWS Docker Kubernetes Terraform CI/CD"
    )
    assert 0 <= result.composite_score <= 100
    assert 0 <= result.keyword_score <= 100
    assert 0 <= result.readability_score <= 100
    assert 0 <= result.format_score <= 100


def test_ats_suggestions_when_score_below_80():
    result = compute_ats_score(
        "I code in python sometimes",
        "Python AWS Docker Kubernetes Terraform CI/CD TypeScript React"
    )
    if result.composite_score < 80:
        assert len(result.suggestions) > 0
        assert len(result.missing_keywords) > 0


def test_missing_keywords_finds_gaps():
    missing = get_missing_keywords(
        "Python Django REST API",
        "Python AWS Docker Kubernetes Terraform CI/CD TypeScript React"
    )
    assert "python" not in [k.lower() for k in missing]  # present in resume
    assert len(missing) > 0


def test_weighted_composite_bounds():
    assert compute_weighted_composite(100, 100, 100) == 100
    assert compute_weighted_composite(0, 0, 0) == 0
    assert 0 <= compute_weighted_composite(80, 70, 60) <= 100


def test_generate_suggestions_non_empty():
    result = AtsScoreResult(
        composite_score=45,
        keyword_score=30,
        readability_score=50,
        format_score=55,
        matched_keywords=["Python"],
        missing_keywords=["AWS", "Docker", "Kubernetes"],
        suggestions=[],
        flesch_kincaid=12.0,
        avg_sentence_length=20.0,
        format_checks={},
    )
    suggestions = generate_suggestions(result)
    assert len(suggestions) > 0


def test_ats_score_matches_all_keywords():
    result = compute_ats_score(
        "Python AWS Docker Kubernetes Terraform CI/CD React TypeScript Node.js",
        "Python AWS Docker Kubernetes Terraform CI/CD React TypeScript Node.js"
    )
    assert result.composite_score >= 70
    assert len(result.missing_keywords) == 0


def test_ats_score_empty_resume():
    import pytest
    with pytest.raises(ValueError, match="resume_text cannot be empty"):
        compute_ats_score("", "Python AWS Docker")
