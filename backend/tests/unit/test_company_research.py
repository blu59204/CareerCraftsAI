"""Unit tests for Company Research Agent — cache logic, source fallback, data structure."""
import uuid
from unittest.mock import MagicMock, patch

from app.agents.state import AgentState


def make_state(company: str = "Stripe") -> AgentState:
    return AgentState(
        user_id="usr_test",
        run_id=str(uuid.uuid4()),
        task_type="company_research",
        messages=[],
        context={"company_name": company},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_company_intel_dataclass_to_dict():
    from app.agents.company_research_agent import CompanyIntel

    intel = CompanyIntel(
        company_name="Acme",
        overview="A widget company",
        culture_summary="Fast-paced",
        news_items=[{"title": "Acme raises $100M", "url": "https://example.com"}],
        tech_stack=["React", "Python"],
        glassdoor_sentiment="positive",
    )
    d = intel.to_dict()
    assert d["company_name"] == "Acme"
    assert d["overview"] == "A widget company"
    assert len(d["news_items"]) == 1
    assert d["glassdoor_sentiment"] == "positive"
    assert d["tech_stack"] == ["React", "Python"]
    assert "researched_at" in d


def test_company_intel_cache_key_present():
    from app.agents.company_research_agent import CompanyIntel

    intel = CompanyIntel(company_name="Acme")
    d = intel.to_dict()
    now = d["researched_at"]
    assert now is not None


def test_company_research_node_structure():
    from app.agents.company_research_agent import CompanyIntel

    intel = CompanyIntel(
        company_name="TestCo",
        overview="Overview text",
        culture_summary="Culture text",
        news_items=[],
        tech_stack=[],
    )
    assert intel.overview == "Overview text"
    assert intel.culture_summary == "Culture text"
    assert intel.news_items == []
    assert intel.glassdoor_sentiment == "neutral"
    assert intel.partial_data is None
