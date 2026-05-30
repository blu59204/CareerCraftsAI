import uuid
from unittest.mock import MagicMock, patch

import pytest

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
    """Tests the PinchTab fallback path (requires mocking internal imports)."""
    pytest.skip("Requires integration environment — JobSpy is primary path now")
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["85", "62"]
    mock_session = MagicMock()
    mock_session.navigate.return_value = {"ok": True}
    mock_session.snapshot.return_value = MOCK_SNAPSHOT

    with patch("app.agents.job_search.new_session", return_value=mock_session), \
         patch(
             "app.agents.job_search.fetch_model_settings",
             return_value=MagicMock(provider="openai"),
         ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch(
             "app.agents.job_search.fetch_user_profile_text",
             return_value="Python engineer 5 years FastAPI",
         ), \
         patch("app.services.job_platforms_service.scrape_jobs", side_effect=ImportError("no jobspy")):
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
    """Tests PinchTab error handling (requires integration environment)."""
    pytest.skip("Requires integration environment — JobSpy is primary path now")
    from app.agents.job_search import job_search_agent_node

    mock_session = MagicMock()
    mock_session.navigate.side_effect = Exception("PinchTab connection refused")

    with patch("app.agents.job_search.new_session", return_value=mock_session), \
         patch("app.agents.job_search.fetch_model_settings", return_value=MagicMock()):
        result = job_search_agent_node(make_state())

    assert result["status"] == "failed"
    assert result["error"] is not None  # Any error message is acceptable
    mock_session.close.assert_called_once()


def test_job_search_agent_returns_empty_matches_when_real_sources_unavailable(mock_llm):
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["50"]

    with patch("app.agents.job_search.new_session", side_effect=Exception("PinchTab offline")), \
         patch(
             "app.agents.job_search.fetch_model_settings",
             return_value=MagicMock(provider="openai"),
         ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search.fetch_user_profile_text", return_value="Python engineer"), \
         patch("app.agents.thinking.think_and_select", return_value="score relevant Python jobs"), \
         patch("app.services.job_platforms_service.scrape_jobs", side_effect=Exception("JobSpy offline")), \
         patch("app.services.indian_platforms_service.search_google_jobs", return_value=[]), \
         patch("app.agents.job_search._search_public_ats_jobs", side_effect=Exception("ATS offline")), \
         patch("app.agents.job_search._search_remoteok_jobs", side_effect=Exception("RemoteOK offline")):
        result = job_search_agent_node(make_state())

    assert result["status"] == "completed"
    assert result["result"] == {"matches": [], "total_found": 0}
    assert all(
        "example.com" not in (match.get("job_url") or "")
        for match in result["result"]["matches"]
    )


def test_job_search_agent_uses_google_jobs_when_jobspy_has_no_results(mock_llm):
    from app.agents.job_search import job_search_agent_node
    from app.services.job_platforms_service import JobListing

    mock_llm.responses = ["90"]
    google_jobs = [
        JobListing(
            title="Realtime Python Engineer",
            company="Stripe",
            location="Remote",
            description="Python APIs",
            job_url="https://stripe.com/jobs/realtime-python",
            platform="google_jobs",
        )
    ]

    with patch(
        "app.agents.job_search.fetch_model_settings",
        return_value=MagicMock(provider="openai"),
    ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search.fetch_user_profile_text", return_value="Python engineer"), \
         patch("app.agents.thinking.think_and_select", return_value="score Python jobs"), \
         patch("app.services.job_platforms_service.scrape_jobs", return_value=[]), \
         patch("app.services.indian_platforms_service.search_google_jobs", return_value=google_jobs) as google_search:
        result = job_search_agent_node(make_state())

    assert result["status"] == "completed"
    assert result["result"]["total_found"] == 1
    assert result["result"]["matches"][0]["platform"] == "google_jobs"
    assert result["result"]["matches"][0]["job_url"] == "https://stripe.com/jobs/realtime-python"
    google_search.assert_called_once()


def test_job_search_agent_passes_live_browser_to_google_jobs(mock_llm):
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["90"]
    state = make_state()
    state["context"]["live_browser"] = True

    with patch(
        "app.agents.job_search.fetch_model_settings",
        return_value=MagicMock(provider="openai"),
    ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search.fetch_user_profile_text", return_value="Python engineer"), \
         patch("app.agents.thinking.think_and_select", return_value="score Python jobs"), \
         patch("app.services.job_platforms_service.scrape_jobs", return_value=[]), \
         patch("app.services.indian_platforms_service.search_google_jobs", return_value=[]) as google_search, \
         patch("app.agents.job_search._search_public_ats_jobs", return_value=[]):
        job_search_agent_node(state)

    _, kwargs = google_search.call_args
    assert kwargs["live_browser"] is True
    assert kwargs["run_id"] == state["run_id"]


def test_live_browser_search_uses_visible_google_jobs_before_jobspy(mock_llm):
    from app.agents.job_search import job_search_agent_node
    from app.services.job_platforms_service import JobListing

    mock_llm.responses = ["91"]
    state = make_state()
    state["context"]["live_browser"] = True
    google_jobs = [
        JobListing(
            title="Visible Browser Python Engineer",
            company="Stripe",
            location="Remote",
            description="Python APIs",
            job_url="https://stripe.com/jobs/visible-python",
            platform="google_jobs",
        )
    ]

    with patch(
        "app.agents.job_search.fetch_model_settings",
        return_value=MagicMock(provider="openai"),
    ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search.fetch_user_profile_text", return_value="Python engineer"), \
         patch("app.agents.thinking.think_and_select", return_value="score Python jobs"), \
         patch("app.services.indian_platforms_service.search_google_jobs", return_value=google_jobs) as google_search, \
         patch("app.services.job_platforms_service.scrape_jobs") as jobspy_scrape:
        result = job_search_agent_node(state)

    assert result["status"] == "completed"
    assert result["result"]["total_found"] == 1
    assert result["result"]["matches"][0]["job_url"] == "https://stripe.com/jobs/visible-python"
    _, kwargs = google_search.call_args
    assert kwargs["live_browser"] is True
    jobspy_scrape.assert_not_called()


def test_job_search_agent_uses_public_ats_before_remoteok(mock_llm):
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["88"]
    ats_jobs = [
        {
            "title": "Hybrid Python Engineer",
            "company": "Stripe",
            "location": "Bangalore, India",
            "description": "Python APIs",
            "job_url": "https://boards.greenhouse.io/stripe/jobs/1",
            "platform": "greenhouse",
        }
    ]
    state = make_state("Python engineer")
    state["context"]["location"] = "Bangalore"
    state["context"]["work_mode"] = "hybrid"

    with patch(
        "app.agents.job_search.fetch_model_settings",
        return_value=MagicMock(provider="openai"),
    ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search.fetch_user_profile_text", return_value="Python engineer"), \
         patch("app.agents.thinking.think_and_select", return_value="score Python jobs"), \
         patch("app.services.job_platforms_service.scrape_jobs", return_value=[]), \
         patch("app.services.indian_platforms_service.search_google_jobs", return_value=[]), \
         patch("app.agents.job_search._search_public_ats_jobs", return_value=ats_jobs) as ats_search, \
         patch("app.agents.job_search._search_remoteok_jobs") as remoteok_search:
        result = job_search_agent_node(state)

    assert result["status"] == "completed"
    assert result["result"]["matches"][0]["platform"] == "greenhouse"
    ats_search.assert_called_once_with("Python engineer", "Bangalore", 10, "hybrid")
    remoteok_search.assert_not_called()


def test_non_remote_search_skips_remoteok_when_no_ats_jobs(mock_llm):
    from app.agents.job_search import job_search_agent_node

    mock_llm.responses = ["50"]
    state = make_state("Python engineer")
    state["context"]["location"] = "Bangalore"
    state["context"]["work_mode"] = "onsite"

    with patch("app.agents.job_search.new_session", side_effect=Exception("PinchTab offline")), \
         patch(
             "app.agents.job_search.fetch_model_settings",
             return_value=MagicMock(provider="openai"),
         ), \
         patch("app.agents.job_search._build_llm", return_value=mock_llm), \
         patch("app.agents.job_search.fetch_user_profile_text", return_value="Python engineer"), \
         patch("app.agents.thinking.think_and_select", return_value="score Python jobs"), \
         patch("app.services.job_platforms_service.scrape_jobs", return_value=[]), \
         patch("app.services.indian_platforms_service.search_google_jobs", return_value=[]), \
         patch("app.agents.job_search._search_public_ats_jobs", return_value=[]), \
         patch("app.agents.job_search._search_remoteok_jobs") as remoteok_search:
        result = job_search_agent_node(state)

    assert result["status"] == "completed"
    assert result["result"] == {"matches": [], "total_found": 0}
    remoteok_search.assert_not_called()


def test_example_job_urls_are_identified_for_filtering():
    from app.api.v1.jobs import is_example_job_url

    assert is_example_job_url("https://example.com/jobs/1")
    assert is_example_job_url("http://www.example.com/mock")
    assert not is_example_job_url("https://stripe.com/jobs/1")
    assert not is_example_job_url(None)


def test_browser_config_uses_headed_mode_for_live_browser():
    from app.services import browser_control_service as svc

    with patch.object(svc, "BrowserConfig") as browser_config:
        svc._get_browser_config("usr_test123", live_browser=True)

    _, kwargs = browser_config.call_args
    assert kwargs["headless"] is False


def test_job_search_agent_respects_max_results_cap():
    from app.agents.job_search import job_search_agent_node

    many_jobs = [
        {
            "title": f"Job {i}",
            "company": f"Co{i}",
            "url": f"https://co{i}.com",
            "description": "Python",
        }
        for i in range(30)
    ]
    mock_session = MagicMock()
    mock_session.navigate.return_value = {"ok": True}
    mock_session.snapshot.return_value = {"jobs": many_jobs}

    with patch("app.agents.job_search.new_session", return_value=mock_session), \
         patch(
             "app.agents.job_search.fetch_model_settings",
             return_value=MagicMock(provider="openai"),
         ), \
         patch("app.agents.job_search._build_llm") as mock_build:
        llm = MagicMock()
        llm.invoke.return_value = MagicMock(content="50")
        mock_build.return_value = llm
        with patch("app.agents.job_search.fetch_user_profile_text", return_value="test"), \
             patch("app.services.job_platforms_service.scrape_jobs", return_value=[]), \
             patch("app.services.indian_platforms_service.search_google_jobs", return_value=[]), \
             patch("app.agents.job_search._search_public_ats_jobs", return_value=[]), \
             patch("app.agents.job_search._search_remoteok_jobs", return_value=[]):
            # max_results capped at 25 per spec
            state = make_state()
            state["context"]["max_results"] = 50
            result = job_search_agent_node(state)

    assert len(result["result"]["matches"]) <= 25
    mock_session.close.assert_called_once()


