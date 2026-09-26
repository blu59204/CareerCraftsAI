"""Unit tests for Salary Agent — percentiles, negotiation script, offer classification."""

import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.state import AgentState


def make_state(role: str = "Senior Python Engineer", location: str = "San Francisco") -> AgentState:
    return AgentState(
        user_id="usr_test",
        run_id=str(uuid.uuid4()),
        task_type="salary_intelligence",
        messages=[],
        context={
            "role": role,
            "location": location,
            "experience_years": 7,
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_offer_classification_enum():
    from app.agents.salary_agent import OfferClassification

    assert OfferClassification.ABOVE_MARKET.value == "above_market"
    assert OfferClassification.AT_MARKET.value == "at_market"
    assert OfferClassification.BELOW_MARKET.value == "below_market"


def test_salary_agent_pauses_for_approval(mock_llm):
    from app.agents.salary_agent import salary_report_node

    mock_llm.responses = [
        json.dumps(
            {
                "p25": 160000,
                "p50": 190000,
                "p75": 220000,
                "p90": 250000,
            }
        ),
        json.dumps(
            {
                "opening": "Thank you for the offer...",
                "counter_offer": 220000,
                "justifications": ["Market data shows...", "My experience with..."],
            }
        ),
    ]

    with (
        patch(
            "app.agents.salary_agent.fetch_model_settings",
            return_value=MagicMock(provider="openai"),
        ),
        patch("app.agents.salary_agent._build_llm", return_value=mock_llm),
        patch("app.agents.salary_agent.ExaService") as mock_exa_cls,
        patch("app.agents.salary_agent._log_agent_run", return_value=None),
    ):
        mock_exa = MagicMock()
        mock_exa.search_salary = AsyncMock(
            return_value=[
                {"title": "Salary data", "text": "$160,000 per year"},
                {"title": "Salary data 2", "text": "$190,000 salary annually"},
                {"title": "Salary data 3", "text": "$220,000 per year"},
                {"title": "Salary data 4", "text": "$250,000 annually"},
            ]
        )
        mock_exa_cls.return_value = mock_exa

        result = salary_report_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"] is not None
    assert result["pending_action"]["type"] == "salary_report_review"
    report = result["pending_action"]["report"]
    assert "p25" in report
    assert "p50" in report
    assert "p75" in report
    assert result["pending_action"]["script"] is not None


def test_salary_agent_handles_exa_failure(mock_llm):
    from app.agents.salary_agent import salary_report_node

    with (
        patch("app.agents.salary_agent.fetch_model_settings", return_value=MagicMock()),
        patch("app.agents.salary_agent.ExaService", side_effect=Exception("Exa unavailable")),
    ):
        result = salary_report_node(make_state())

    assert result["status"] == "failed"
    assert result["error"] is not None


def test_salary_figures_keep_the_sources_currency():
    from app.agents.salary_agent import _extract_percentiles, format_amount

    results = [
        {"url": "https://a", "text": "70% of salaries range between ₹ 28 lakhs to ₹ 73 lakhs."},
        {"url": "https://b", "text": "Senior Backend Developer at Razorpay. ₹22L - ₹28L CTC."},
        {"url": "https://c", "text": "The median total compensation is ₹3,864,698."},
        {"url": "https://d", "text": "Founded in 2014, 3,000+ employees, rated 4.1"},
    ]
    report = _extract_percentiles(results)

    assert report["currency"] == "INR"
    assert report["sample_size"] == 5
    assert (report["p25"], report["p50"], report["p75"]) == (2_800_000, 2_800_000, 3_864_698)
    assert report["sources"] == ["https://a", "https://b", "https://c"]
    assert format_amount(report["p75"], "INR") == "₹38.6 lakh"


def test_hourly_rates_and_stray_numbers_are_not_salaries():
    from app.agents.salary_agent import _salary_figures

    assert _salary_figures("$181,137 or an equivalent hourly rate of $87.09") == [("USD", 181137)]
    assert _salary_figures("$120K - $150K base") == [("USD", 120000), ("USD", 150000)]
    assert _salary_figures("₹85,000 per month") == [("INR", 1_020_000)]
    assert _salary_figures("as of September 01, 2026 with 5,098 submissions") == []


def test_salary_falls_back_to_keyless_search_without_exa(mock_llm):
    from app.agents import salary_agent

    mock_llm.responses = [
        json.dumps(
            {
                "opening": "Thank you for the offer.",
                "counter_offer": 1,
                "justifications": ["Market data", "Experience"],
            }
        )
    ]
    queries = []

    async def ddg(query, limit=5):
        queries.append(query)
        return [
            {"url": "https://x", "title": "Salary", "snippet": "range ₹ 28 lakhs to ₹ 73 lakhs"},
            {"url": "https://y", "title": "Salary", "snippet": "₹22L - ₹28L CTC"},
        ]

    with (
        patch.object(salary_agent, "fetch_model_settings", return_value=MagicMock()),
        patch.object(salary_agent, "_build_llm", return_value=mock_llm),
        patch.object(salary_agent, "ExaService") as exa_cls,
        patch.object(salary_agent, "_log_agent_run", return_value=None),
        patch.object(salary_agent.web_research, "duckduckgo", ddg),
    ):
        exa_cls.return_value.search_salary = AsyncMock(return_value=[])
        state = make_state()
        state["context"] = {"role": "Backend Engineer", "company": "Razorpay"}  # no location
        result = salary_agent.salary_report_node(state)

    assert result["status"] == "awaiting_approval"
    report = result["pending_action"]["report"]
    assert report["currency"] == "INR" and report["p75"] == 7_300_000
    assert queries[0] == "Backend Engineer salary Razorpay"
    assert result["pending_action"]["script"]["counter_offer"] == 7_300_000
