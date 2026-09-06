import json
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


def _valid_resume_json() -> str:
    return json.dumps({
        "resume_markdown": "Jane Doe\n\nSUMMARY\n5 years Python experience",
        "summary": "Backend engineer",
        "ats_score": 70,
        "keywords_matched": ["Python"],
        "keywords_missing": ["AWS"],
        "changes_made": ["Reordered sections"],
        "warnings": [],
    })


def test_resume_agent_pauses_for_approval(mock_llm):
    from app.agents.resume_agent import resume_agent_node

    mock_llm.responses = [_valid_resume_json()]
    mock_chunks = [MagicMock(page_content="5 years Python experience")]

    with patch("app.core.sync_db.fetch_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.resume_agent.retrieve", return_value=mock_chunks), \
         patch("app.agents.resume_agent.generate_resume_pdf", return_value=b"%PDF-fake"), \
         patch("app.agents.resume_agent._persist_resume_document", return_value="doc-123") as persist, \
         patch("app.core.sync_db.fetch_user_full_name", return_value="Test User"), \
         patch("app.core.model_router._build_llm", return_value=mock_llm), \
         patch("app.core.event_bus.emit"):
        result = resume_agent_node(make_state())

    persist.assert_called_once()
    assert result["status"] == "awaiting_approval"
    assert result["pending_action"] is not None
    assert result["pending_action"]["type"] == "resume_ready"
    assert "resume_markdown" in result["pending_action"]
    assert result["pending_action"]["pdf_document_id"] == "doc-123"
    assert "pdf_b64" not in result["pending_action"]
    assert result["pending_action"]["ats_score"] >= 0


def test_resume_agent_uses_fallback_on_exception():
    from app.agents.resume_agent import resume_agent_node

    with patch("app.core.sync_db.fetch_model_settings", return_value=MagicMock()), \
         patch("app.core.sync_db.fetch_user_full_name", return_value="Test"), \
         patch("app.agents.resume_agent.retrieve", side_effect=Exception("pgvector down")), \
         patch("app.agents.resume_agent.generate_resume_pdf", return_value=b"%PDF-fake"), \
         patch("app.agents.resume_agent._persist_resume_document", return_value="doc-456"), \
         patch("app.core.event_bus.emit"):
        result = resume_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["type"] == "resume_ready"
    assert result["pending_action"]["pdf_document_id"] == "doc-456"
    assert any("allback" in w or "ailed" in w for w in result["pending_action"]["warnings"])


def test_resume_agent_degrades_without_pdf_storage(mock_llm):
    from app.agents.resume_agent import resume_agent_node

    mock_llm.responses = [_valid_resume_json()]
    mock_chunks = [MagicMock(page_content="5 years Python experience")]

    with patch("app.core.sync_db.fetch_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.resume_agent.retrieve", return_value=mock_chunks), \
         patch("app.agents.resume_agent.generate_resume_pdf", return_value=b"%PDF-fake"), \
         patch("app.agents.resume_agent._persist_resume_document", side_effect=Exception("storage down")), \
         patch("app.core.sync_db.fetch_user_full_name", return_value="Test User"), \
         patch("app.core.model_router._build_llm", return_value=mock_llm), \
         patch("app.core.event_bus.emit"):
        result = resume_agent_node(make_state())

    assert result["status"] == "awaiting_approval"
    assert result["pending_action"]["pdf_document_id"] is None
    assert "resume_markdown" in result["pending_action"]


def test_call_llm_json_retries_once_on_invalid():
    from app.agents._llm_json import call_llm_json
    from app.agents.prompts.resume_prompt import OUTPUT_SCHEMA
    from langchain_core.messages import AIMessage

    calls = {"n": 0}

    class FakeLLM:
        def invoke(self, messages):
            calls["n"] += 1
            if calls["n"] == 1:
                return AIMessage(content="not json at all")
            return AIMessage(content=_valid_resume_json())

    parsed = call_llm_json(FakeLLM(), "sys", "human", OUTPUT_SCHEMA)
    assert parsed.ats_score == 70
    assert calls["n"] == 2
