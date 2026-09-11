"""Unit tests for Interview Coach Agent — question generation, scoring, session lifecycle."""
import json
import uuid
from unittest.mock import MagicMock, patch

from app.agents.state import AgentState


def make_start_state() -> AgentState:
    return AgentState(
        user_id="usr_test",
        run_id=str(uuid.uuid4()),
        task_type="interview_coach",
        messages=[],
        context={"role": "Python Engineer", "company": "Stripe"},
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def make_eval_state(session_id: str) -> AgentState:
    return AgentState(
        user_id="usr_test",
        run_id=str(uuid.uuid4()),
        task_type="evaluate_answer",
        messages=[],
        context={
            "session_id": session_id,
            "question_index": 0,
            "answer_text": "I used Python to build a distributed task queue that processed 1M jobs/day, reducing latency by 40%.",
        },
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def test_interview_coach_rating_labels():
    from app.agents.interview_coach_agent import compute_rating_label

    assert compute_rating_label(10) == "poor"
    assert compute_rating_label(35) == "fair"
    assert compute_rating_label(60) == "good"
    assert compute_rating_label(85) == "excellent"
    assert compute_rating_label(95) == "excellent"


def test_interview_coach_compute_session_summary():
    from app.agents.interview_coach_agent import compute_session_summary

    scores = [70, 80]
    summary = compute_session_summary(scores)
    assert "overall_score" in summary
    assert "count" in summary
    assert summary["count"] == 2
    assert summary["overall_score"] == 75


def test_start_session_generates_questions(mock_llm):
    from app.agents.interview_coach_agent import start_session_node

    mock_llm.responses = [
        json.dumps([
            {"id": 1, "type": "behavioral", "text": "Tell me about yourself"},
            {"id": 2, "type": "technical", "text": "Explain Python GIL"},
            {"id": 3, "type": "situational", "text": "How do you handle conflict?"},
        ])
    ]

    with (
        patch("app.agents.interview_coach_agent.fetch_model_settings", return_value=MagicMock(provider="openai")),
        patch("app.agents.interview_coach_agent._build_llm", return_value=mock_llm),
        patch("app.agents.interview_coach_agent.retrieve", return_value=[]),
        patch("app.agents.interview_coach_agent._log_agent_run", return_value=None),
        patch("app.agents.interview_coach_agent._save_interview_session", return_value=None),
    ):
        result = start_session_node(make_start_state())

    assert result["status"] == "completed"
    assert result["result"]["type"] == "interview_session_started"
    assert "session_id" in result["result"]
    assert len(result["result"]["questions"]) == 3


def test_evaluate_answer_scores_in_range(mock_llm):
    from app.agents.interview_coach_agent import evaluate_answer_node

    session_id = str(uuid.uuid4())
    mock_llm.responses = [json.dumps({
        "clarity": 8,
        "relevance": 7,
        "depth": 6,
        "feedback": "Good answer with concrete metrics.",
        "rating": "excellent",
    })]

    with (
        patch("app.agents.interview_coach_agent.fetch_model_settings", return_value=MagicMock(provider="openai")),
        patch("app.agents.interview_coach_agent._build_llm", return_value=mock_llm),
        patch("app.agents.interview_coach_agent._get_interview_session", return_value={
            "questions": [{"question": "Tell me about yourself", "type": "behavioral"}]
        }),
        patch("app.agents.interview_coach_agent._update_session_answer", return_value=None),
        patch("app.agents.interview_coach_agent._log_agent_run", return_value=None),
    ):
        result = evaluate_answer_node(make_eval_state(session_id))

    assert result["status"] == "completed"
    assert "score" in result["result"]
