import json
import uuid
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState


def test_interview_prep_pauses_with_generated_payload_for_review(mock_llm):
    from app.agents.interview_prep_agent import interview_prep_agent_node

    mock_llm.responses = [json.dumps({
        "questions": [{"q": "Tell me about a shipped project.", "type": "behavioral", "intent": "ownership"}],
        "study_plan": [],
        "topics_ranked": ["Python"],
        "questions_to_ask": ["How is success measured?"],
        "video_search_queries": [],
    })]
    state = AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="interview_prep",
        messages=[HumanMessage(content="prepare me")],
        context={"role": "Senior Python Engineer", "company": "Example"},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )

    with patch("app.agents.interview_prep_agent.fetch_model_settings", return_value=MagicMock(provider="openai")), \
         patch("app.agents.interview_prep_agent.retrieve", return_value=[MagicMock(page_content="Python experience")]), \
         patch("app.agents.interview_prep_agent._build_llm", return_value=mock_llm), \
         patch("app.agents.thinking.think_and_select", return_value="Focus on Python ownership"), \
         patch("app.core.event_bus.emit"):
        result = interview_prep_agent_node(state)

    assert result["status"] == "awaiting_approval"
    assert result["result"] is None
    assert result["pending_action"]["type"] == "interview_prep"
    assert result["pending_action"]["questions"][0]["q"] == "Tell me about a shipped project."
