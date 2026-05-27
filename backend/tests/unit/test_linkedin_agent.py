import uuid
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState


def make_state() -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="linkedin_optimize",
        messages=[HumanMessage(content="Optimize my LinkedIn profile")],
        context={"target_role": "Senior Python Engineer"},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_linkedin_agent_generates_sections_and_pauses():
    from langchain_core.messages import AIMessage

    from app.agents.linkedin_agent import linkedin_agent_node

    llm_responses = [
        AIMessage(content="Dynamic Python engineer | FastAPI | LangChain | 5+ years"),
        AIMessage(content="Passionate about building AI-powered systems..."),
        AIMessage(content="• Led migration to FastAPI microservices\n• Reduced latency 40%"),
    ]
    mock_llm = MagicMock()
    mock_llm.invoke.side_effect = llm_responses
    mock_chunks = [MagicMock(page_content="5 years Python, FastAPI, LangChain")]

    _settings_patch = "app.agents.linkedin_agent.fetch_model_settings"
    with patch("app.agents.linkedin_agent.retrieve", return_value=mock_chunks), \
         patch(_settings_patch, return_value=MagicMock(provider="openai")), \
         patch("app.agents.linkedin_agent._build_llm", return_value=mock_llm), \
         patch("app.agents.linkedin_agent.think_and_select", return_value="Focus on Python/FastAPI experience"):
        result = linkedin_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["type"] == "linkedin_edits"
    assert "headline" in result["pending_action"]
    assert "about" in result["pending_action"]
    assert "experience_bullets" in result["pending_action"]


def test_linkedin_agent_fails_gracefully():
    from app.agents.linkedin_agent import linkedin_agent_node

    with patch("app.agents.linkedin_agent.fetch_model_settings", return_value=MagicMock()), \
         patch("app.agents.linkedin_agent.retrieve", side_effect=Exception("DB error")):
        result = linkedin_agent_node(make_state())

    assert result["status"] == "failed"
    assert "DB error" in result["error"]

