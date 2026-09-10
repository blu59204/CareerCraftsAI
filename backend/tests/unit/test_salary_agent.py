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
        json.dumps({
            "p25": 160000,
            "p50": 190000,
            "p75": 220000,
            "p90": 250000,
        }),
        json.dumps({
            "opening": "Thank you for the offer...",
            "counter_offer": 220000,
            "justifications": ["Market data shows...", "My experience with..."],
        }),
    ]

    with (
        patch("app.agents.salary_agent.fetch_model_settings", return_value=MagicMock(provider="openai")),
        patch("app.agents.salary_agent._build_llm", return_value=mock_llm),
        patch("app.agents.salary_agent.ExaService") as mock_exa_cls,
        patch("app.agents.salary_agent._log_agent_run", return_value=None),
    ):
        mock_exa = MagicMock()
        mock_exa.search_salary = AsyncMock(return_value=[
            {"title": "Salary data", "text": "$160,000 per year"},
            {"title": "Salary data 2", "text": "$190,000 salary annually"},
            {"title": "Salary data 3", "text": "$220,000 per year"},
            {"title": "Salary data 4", "text": "$250,000 annually"},
        ])
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
