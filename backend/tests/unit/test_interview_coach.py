"""Unit tests for Interview Coach Agent — question generation, scoring, session lifecycle."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

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


# --- API contract: POST /interview/session/start and .../answer ---
#
# These exercise the FastAPI route layer (not the LangGraph nodes above),
# following the AsyncClient + ASGITransport + dependency_overrides pattern
# established in test_applications.py::test_candidate_profile_api_upsert_then_get.


class _FakeInterviewDB:
    """Async-session double for interview route tests.

    Call 1 to execute() is always the IDOR ownership check (a column-only
    select) in submit_answer; any later call re-fetches the full row to read
    the questions/scores the agent's (mocked) run would have updated.
    """

    def __init__(self, session_row=None, owns_session=True):
        self.session_row = session_row
        self.owns_session = owns_session
        self.added = []
        self.execute_calls = 0

    async def execute(self, *a, **k):
        self.execute_calls += 1

        class _Result:
            def __init__(self_inner, value):
                self_inner.value = value

            def scalar_one_or_none(self_inner):
                return self_inner.value

        if self.execute_calls == 1:
            owned_id = self.session_row.id if (self.owns_session and self.session_row) else None
            return _Result(owned_id)
        return _Result(self.session_row)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        return None


def _fake_session_row(session_id, user_id, questions, scores):
    row = MagicMock()
    row.id = session_id
    row.user_id = user_id
    row.questions = questions
    row.scores = scores
    return row


@pytest.mark.asyncio
async def test_interview_session_contract_start_then_answer_to_completion(monkeypatch):
    """Step 1 (TDD): the API layer must return the full session/question/
    feedback contract, not just {run_id, status} — and question_index must
    increment per turn instead of being hardcoded to 0 on every answer."""
    from httpx import ASGITransport, AsyncClient

    from app.api.v1.deps import get_current_user, get_db
    from app.main import app

    user_id = uuid.uuid4()
    session_id = uuid.uuid4()
    monkeypatch.setattr(
        "app.main.verify_token",
        lambda token: {"sub": str(user_id), "email": "a@b.com"},
    )
    questions = [
        {"type": "behavioral", "question": "Tell me about yourself", "context": "warm-up"},
        {"type": "technical", "question": "Explain the GIL", "context": "depth check"},
    ]

    async def _fake_user():
        return MagicMock(id=user_id, email="a@b.com")

    session_row = _fake_session_row(session_id, user_id, questions, scores=[])
    fake_db = _FakeInterviewDB(session_row=session_row)

    async def _fake_db():
        return fake_db

    start_result = {
        "status": "completed",
        "result": {
            "type": "interview_session_started",
            "session_id": str(session_id),
            "role": "Python Engineer",
            "company": "Stripe",
            "questions": questions,
            "question_count": 2,
        },
    }
    answer_results = [
        {
            "status": "completed",
            "result": {
                "type": "answer_evaluation",
                "session_id": str(session_id),
                "question_index": 0,
                "score": 82,
                "rating": "excellent",
                "tips": ["Add a metric next time."],
            },
        },
        {
            "status": "completed",
            "result": {
                "type": "answer_evaluation",
                "session_id": str(session_id),
                "question_index": 1,
                "score": 60,
                "rating": "good",
                "tips": ["Go deeper on internals."],
            },
        },
    ]

    fake_harness = MagicMock()
    fake_harness.run = AsyncMock(side_effect=[start_result, *answer_results])

    app.dependency_overrides[get_current_user] = _fake_user
    app.dependency_overrides[get_db] = _fake_db
    try:
        with patch("app.api.v1.interview.get_harness", AsyncMock(return_value=fake_harness)):
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
                headers = {"Authorization": "Bearer test-token"}

                start_response = await client.post(
                    "/api/v1/interview/session/start",
                    json={"role": "Python Engineer", "company": "Stripe"},
                    headers=headers,
                )
                assert start_response.status_code == 200, start_response.text
                start_body = start_response.json()
                assert start_body["session_id"]
                assert start_body["question"]["question"] == "Tell me about yourself"
                assert start_body["question_index"] == 0

                # Answer question 0 — expect the *second* question next, no summary yet.
                answer_response = await client.post(
                    f"/api/v1/interview/session/{session_id}/answer",
                    json={
                        "question_index": 0,
                        "answer_text": "I built a distributed task queue that processed a million jobs a day.",
                    },
                    headers=headers,
                )
                assert answer_response.status_code == 200, answer_response.text
                answer_body = answer_response.json()
                assert answer_body["feedback"]["score"] >= 0
                assert "next_question" in answer_body
                assert answer_body["next_question"]["question"] == "Explain the GIL"
                assert answer_body["summary"] is None

                # The harness must be told which question this answer is for
                # (bug: previously hardcoded to question_index=0 every turn).
                first_answer_call = fake_harness.run.call_args_list[1]
                assert first_answer_call.kwargs["context"]["question_index"] == 0
                assert first_answer_call.kwargs["context"]["answer_text"]

                # Answer question 1 (the last one) — expect no next question, summary present.
                session_row.scores = [82]  # simulate the agent's sync-DB update after turn 1
                final_answer_response = await client.post(
                    f"/api/v1/interview/session/{session_id}/answer",
                    json={
                        "question_index": 1,
                        "answer_text": "The GIL is a mutex that protects access to Python objects in CPython.",
                    },
                    headers=headers,
                )
                assert final_answer_response.status_code == 200, final_answer_response.text
                final_body = final_answer_response.json()
                assert final_body["next_question"] is None
                assert final_body["summary"] is not None
                assert final_body["summary"]["count"] == 1

                second_answer_call = fake_harness.run.call_args_list[2]
                assert second_answer_call.kwargs["context"]["question_index"] == 1
    finally:
        app.dependency_overrides.clear()
