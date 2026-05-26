"""Unit tests for the salary agent module."""

import pytest

from app.agents.salary_agent import (
    OfferClassification,
    classify_offer,
    _extract_percentiles,
)


class TestClassifyOffer:
    """Tests for classify_offer pure function."""

    def test_below_market_when_offer_below_p25(self):
        result = classify_offer(offer=80_000, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.BELOW_MARKET

    def test_above_market_when_offer_above_p75(self):
        result = classify_offer(offer=150_000, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.ABOVE_MARKET

    def test_at_market_when_offer_equals_p25(self):
        result = classify_offer(offer=90_000, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.AT_MARKET

    def test_at_market_when_offer_equals_p75(self):
        result = classify_offer(offer=130_000, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.AT_MARKET

    def test_at_market_when_offer_between_p25_and_p75(self):
        result = classify_offer(offer=110_000, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.AT_MARKET

    def test_below_market_boundary(self):
        # One dollar below p25
        result = classify_offer(offer=89_999, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.BELOW_MARKET

    def test_above_market_boundary(self):
        # One dollar above p75
        result = classify_offer(offer=130_001, p25=90_000, p50=110_000, p75=130_000)
        assert result == OfferClassification.ABOVE_MARKET


class TestExtractPercentiles:
    """Tests for _extract_percentiles helper."""

    def test_returns_none_when_insufficient_data(self):
        results = [{"text": "No salary info here"}]
        assert _extract_percentiles(results) is None

    def test_returns_none_for_empty_results(self):
        assert _extract_percentiles([]) is None

    def test_extracts_from_salary_text(self):
        results = [
            {"text": "Salary range: $80,000 to $120,000 per year"},
            {"text": "Average compensation $100,000 annually"},
            {"text": "Top earners make $150,000 salary"},
        ]
        percentiles = _extract_percentiles(results)
        assert percentiles is not None
        assert percentiles["p25"] <= percentiles["p50"] <= percentiles["p75"]
        assert all(v > 0 for v in percentiles.values())

    def test_filters_unreasonable_values(self):
        results = [
            {"text": "The company has 5000 employees with salaries from $90,000 to $130,000"},
            {"text": "Revenue of $50,000,000 but average salary $110,000"},
            {"text": "Salary $100,000 per year"},
        ]
        percentiles = _extract_percentiles(results)
        assert percentiles is not None
        # Should only include reasonable salary values (20k-1M)
        assert all(20_000 <= v <= 1_000_000 for v in percentiles.values())
