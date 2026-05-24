import uuid
import pytest
from unittest.mock import MagicMock, patch, call
from langchain_core.messages import HumanMessage
from app.agents.state import AgentState

MOCK_SNAPSHOT = {
    "jobs": [
        {
            "title": "Senior Python Engineer",
            "company": "Stripe",
            "url": "https://stripe.com/jobs/1",
            "description": "FastAPI, PostgreSQL, 5+ years",
        },
        {
            "title": "Backend Engineer",
            "company": "Acme",
            "url": "https://acme.com/jobs/2",
            "description": "Django, Redis, 3+ years",
        },
    ]
}


def make_state(query: str = "Python engineer remote") -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="job_search",
        messages=[HumanMessage(content=query)],
        context={"search_query": query, "location": "Remote", "max_results": 10},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_job_search_agent_returns_scored_matches(mock_llm):
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["85", "62"]
    mock_session = MagicMock()
    mock_session.navigate.return_value = {"ok": True}
    mock_session.snapshot.return_value = MOCK_SNAPSHOT

    with patch("app.agents.job_search.new_session", return_value=mock_session), \
         patch("app.agents.job_search._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search._get_user_profile", return_value="Python engineer 5 years FastAPI"):
        result = job_search_agent_node(make_state())

    assert result["status"] == "completed"
    assert result["result"] is not None
    assert "matches" in result["result"]
    assert len(result["result"]["matches"]) == 2
    # Should be sorted by score descending
    scores = [m["match_score"] for m in result["result"]["matches"]]
    assert scores == sorted(scores, reverse=True)
    mock_session.close.assert_called_once()


def test_job_search_agent_closes_session_on_error():
    from app.agents.job_search import job_search_agent_node

    mock_session = MagicMock()
    mock_session.navigate.side_effect = Exception("PinchTab connection refused")

    with patch("app.agents.job_search.new_session", return_value=mock_session), \
         patch("app.agents.job_search._get_model_settings", return_value=MagicMock()):
        result = job_search_agent_node(make_state())

    assert result["status"] == "failed"
    assert "PinchTab connection refused" in result["error"]
    mock_session.close.assert_called_once()


def test_job_search_agent_respects_max_results_cap():
    from app.agents.job_search import job_search_agent_node

    many_jobs = [{"title": f"Job {i}", "company": f"Co{i}", "url": f"https://co{i}.com", "description": "Python"} for i in range(30)]
    mock_session = MagicMock()
    mock_session.navigate.return_value = {"ok": True}
    mock_session.snapshot.return_value = {"jobs": many_jobs}

    with patch("app.agents.job_search.new_session", return_value=mock_session), \
         patch("app.agents.job_search._get_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.job_search._build_llm") as mock_build:
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="50")
        mock_build.return_value = llm
        with patch("app.agents.job_search._get_user_profile", return_value="test"):
            # max_results capped at 25 per spec
            state = make_state()
            state["context"]["max_results"] = 50
            result = job_search_agent_node(state)

    assert len(result["result"]["matches"]) <= 25
    mock_session.close.assert_called_once()
