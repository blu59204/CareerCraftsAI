import uuid
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState


def make_state(jd_text: str = "Python engineer at Stripe") -> AgentState:
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="resume_optimize",
        messages=[HumanMessage(content=jd_text)],
        context={"jd_text": jd_text},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_resume_agent_pauses_for_approval(mock_llm):
    from app.agents.resume_agent import resume_agent_node

    mock_chunks = [MagicMock(page_content="5 years Python experience")]

    _settings_patch = "app.agents.resume_agent._get_model_settings"
    with patch("app.agents.resume_agent.retrieve", return_value=mock_chunks), \
         patch("app.agents.resume_agent.generate_resume_pdf", return_value=b"%PDF-fake"), \
         patch(_settings_patch, return_value=MagicMock(provider="openai")), \
         patch("app.agents.resume_agent._build_llm", return_value=mock_llm):
        result = resume_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"] is not None
    assert result["pending_action"]["type"] == "resume_ready"
    assert "resume_text" in result["pending_action"]


def test_resume_agent_sets_error_on_exception():
    from app.agents.resume_agent import resume_agent_node

    with patch("app.agents.resume_agent._get_model_settings", return_value=MagicMock()), \
         patch("app.agents.resume_agent.retrieve", side_effect=Exception("pgvector down")):
        result = resume_agent_node(make_state())

    assert result["status"] == "failed"
    assert "pgvector down" in result["error"]
