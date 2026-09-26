"""Unit tests for Company Research Agent — cache logic, source fallback, data structure."""

import uuid
from unittest.mock import MagicMock

import pytest

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


# ── Keyless sources, heuristics and synthesis ───────────────────────────


def test_tech_names_are_matched_as_names_not_words():
    from app.agents.company_research_agent import extract_tech_names

    text = (
        "We react quickly. Our services use Golang, Postgres and Kafka on k8s; the web "
        "app is React + TypeScript. Kafka streams feed Spark. C++ for the matching engine."
    )
    names = extract_tech_names(text)
    assert names[0] == "Kafka"  # most frequent first
    assert {"Go", "PostgreSQL", "Kubernetes", "React", "TypeScript", "Spark", "C++"} <= set(names)
    assert "react" not in names


def test_sentiment_prefers_ratings_over_keywords():
    from app.agents.company_research_agent import _sentiment_from_snippets

    assert _sentiment_from_snippets(["Employees rated Acme 4.2 out of 5 stars"]) == "positive"
    assert _sentiment_from_snippets(["Rated 2.6 ★ — terrible? great?"]) == "negative"
    assert _sentiment_from_snippets(["41% of employees would recommend it"]) == "negative"
    assert _sentiment_from_snippets(["People love it, excellent team"]) == "positive"


@pytest.mark.asyncio
async def test_sources_fall_back_to_keyless_lookups_without_api_keys(monkeypatch):
    from app.agents import company_research_agent as agent

    class NoKeyExa:
        async def search_news(self, company):
            return []

        async def search_tech_stack(self, company):
            return []

        async def _search(self, query, num_results=5):
            return []

    async def wiki(name):
        return {"content": "Acme Corp is a widget company.", "source": "wikipedia"}

    async def news(name, limit=5):
        return [
            {"title": "Acme raises $10M", "url": "https://n", "snippet": "Wire", "published": ""}
        ]

    async def ddg(query, limit=5):
        if "tech stack" in query:
            return [
                {"title": "Acme engineering", "url": "https://e", "snippet": "We run Python on AWS"}
            ]
        return []  # no review snippets anywhere

    monkeypatch.setattr(agent, "ExaService", NoKeyExa)
    monkeypatch.setattr(agent.settings, "FIRECRAWL_API_KEY", None)
    monkeypatch.setattr(agent.web_research, "wikipedia_summary", wiki)
    monkeypatch.setattr(agent.web_research, "google_news", news)
    monkeypatch.setattr(agent.web_research, "duckduckgo", ddg)

    results, failures = await agent.fetch_all_sources("Acme")
    intel = agent.compile_intel("Acme", results, failures)

    assert intel.overview.startswith("Acme Corp")
    assert intel.news_items[0]["title"] == "Acme raises $10M"
    assert intel.tech_stack == ["Python", "AWS"]
    assert failures == {"glassdoor": "Glassdoor research failed"}


@pytest.mark.asyncio
async def test_synthesis_keeps_only_technologies_the_sources_name(monkeypatch):
    from app.agents import company_research_agent as agent

    results = {
        "website": {"content": "Acme builds payment APIs."},
        "tech_stack": ["Acme engineers write Ruby and Java, with JSON APIs."],
        "glassdoor": {"snippets": ["Some call it toxic, but it is rated 4.0 out of 5"]},
    }
    intel = agent.compile_intel("Acme", results, {})

    def fake_synthesize(model_settings, company_name, sources):
        return agent._Brief(
            overview="Acme builds payment APIs for online businesses.",
            culture_summary="Reviewers praise mentorship.",
            tech_stack=["Ruby", "JSON", "Java", "Haskell"],  # Haskell is invented
            glassdoor_sentiment="negative",
        )

    monkeypatch.setattr(agent, "_synthesize", fake_synthesize)
    intel = await agent.synthesize_intel(intel, results, model_settings=object())

    assert intel.overview == "Acme builds payment APIs for online businesses."
    assert intel.tech_stack == ["Ruby", "Java"]
    assert intel.glassdoor_sentiment == "positive"  # the 4.0 rating wins


@pytest.mark.asyncio
async def test_synthesis_failure_keeps_the_heuristic_brief(monkeypatch):
    from app.agents import company_research_agent as agent

    results = {"website": {"content": "Acme builds payment APIs."}}
    intel = agent.compile_intel("Acme", results, {})

    def broken(*args):
        raise RuntimeError("model down")

    monkeypatch.setattr(agent, "_synthesize", broken)
    intel = await agent.synthesize_intel(intel, results, model_settings=object())
    assert intel.overview == "Acme builds payment APIs."


@pytest.mark.asyncio
async def test_no_sources_at_all_fails_the_run_with_a_useful_message(monkeypatch):
    from app.agents import company_research_agent as agent

    class _Session:
        async def __aenter__(self):
            return MagicMock()

        async def __aexit__(self, *exc):
            return False

    async def nothing(name):
        return {}, {"website": "x", "news": "x", "tech_stack": "x", "glassdoor": "x"}

    monkeypatch.setattr(agent, "AsyncSessionLocal", _Session)
    monkeypatch.setattr(agent, "fetch_all_sources", nothing)
    state = make_state("Qwzx Nonexistent")
    state["context"]["force_refresh"] = True

    with pytest.raises(ValueError, match="Couldn't find public information"):
        await agent.company_research_node(state)
