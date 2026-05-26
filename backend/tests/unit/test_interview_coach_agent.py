"""Unit tests for Interview Coach Agent pure functions."""

import pytest

from app.agents.interview_coach_agent import (
    QUESTION_TYPES,
    RATING_LABELS,
    compute_rating_label,
    compute_session_summary,
)


class TestComputeRatingLabel:
    """Tests for compute_rating_label pure function."""

    def test_poor_range(self):
        assert compute_rating_label(0) == "poor"
        assert compute_rating_label(12) == "poor"
        assert compute_rating_label(25) == "poor"

    def test_fair_range(self):
        assert compute_rating_label(26) == "fair"
        assert compute_rating_label(38) == "fair"
        assert compute_rating_label(50) == "fair"

    def test_good_range(self):
        assert compute_rating_label(51) == "good"
        assert compute_rating_label(63) == "good"
        assert compute_rating_label(75) == "good"

    def test_excellent_range(self):
        assert compute_rating_label(76) == "excellent"
        assert compute_rating_label(88) == "excellent"
        assert compute_rating_label(100) == "excellent"

    def test_boundary_values(self):
        """Verify exact boundaries between ranges."""
        assert compute_rating_label(25) == "poor"
        assert compute_rating_label(26) == "fair"
        assert compute_rating_label(50) == "fair"
        assert compute_rating_label(51) == "good"
        assert compute_rating_label(75) == "good"
        assert compute_rating_label(76) == "excellent"

    def test_clamps_negative(self):
        assert compute_rating_label(-5) == "poor"

    def test_clamps_above_100(self):
        assert compute_rating_label(150) == "excellent"


class TestComputeSessionSummary:
    """Tests for compute_session_summary pure function."""

    def test_empty_scores(self):
        result = compute_session_summary([])
        assert result == {"overall_score": 0, "count": 0, "rating": "poor"}

    def test_single_score(self):
        result = compute_session_summary([80])
        assert result["overall_score"] == 80
        assert result["count"] == 1
        assert result["rating"] == "excellent"

    def test_multiple_scores_mean(self):
        result = compute_session_summary([60, 70, 80])
        # mean = 210/3 = 70
        assert result["overall_score"] == 70
        assert result["count"] == 3
        assert result["rating"] == "good"

    def test_rounding(self):
        # mean = (50 + 60 + 61) / 3 = 171/3 = 57.0
        result = compute_session_summary([50, 60, 61])
        assert result["overall_score"] == 57
        assert result["rating"] == "good"

    def test_rounding_half(self):
        # mean = (33 + 34) / 2 = 33.5 -> rounds to 34
        result = compute_session_summary([33, 34])
        assert result["overall_score"] == 34
        assert result["rating"] == "fair"

    def test_all_zero_scores(self):
        result = compute_session_summary([0, 0, 0])
        assert result["overall_score"] == 0
        assert result["rating"] == "poor"

    def test_all_perfect_scores(self):
        result = compute_session_summary([100, 100, 100])
        assert result["overall_score"] == 100
        assert result["rating"] == "excellent"


class TestConstants:
    """Verify constants are correctly defined."""

    def test_question_types(self):
        assert QUESTION_TYPES == {"behavioral", "technical", "situational"}

    def test_rating_labels_cover_full_range(self):
        """Ensure RATING_LABELS cover 0-100 without gaps."""
        covered = set()
        for label, (low, high) in RATING_LABELS.items():
            for i in range(low, high + 1):
                covered.add(i)
        assert covered == set(range(0, 101))
