import json
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

from langchain_core.messages import HumanMessage

from app.agents.state import AgentState

REPO_ROOT = Path(__file__).resolve().parents[3]
INTERVIEW_PREP_PAGE = (
    REPO_ROOT / "frontend" / "src" / "app" / "(app)" / "interview-prep" / "page.tsx"
)


def test_interview_prep_page_has_no_mock_interview_questions():
    """Mock interview practice must use the generated plan's questions."""
    source = INTERVIEW_PREP_PAGE.read_text(encoding="utf-8")

    assert "MOCK_INTERVIEW_QUESTIONS" not in source


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
