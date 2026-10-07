"""Unit tests for Interview Coach Agent — question generation, scoring, session lifecycle."""

import json
import uuid
from unittest.mock import MagicMock, patch

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
            "answer_text": (
                "I used Python to build a distributed task queue that processed "
                "1M jobs/day, reducing latency by 40%."
            ),
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
        json.dumps(
            [
                {"id": 1, "type": "behavioral", "text": "Tell me about yourself"},
                {"id": 2, "type": "technical", "text": "Explain Python GIL"},
                {"id": 3, "type": "situational", "text": "How do you handle conflict?"},
            ]
        )
    ]

    with (
        patch(
            "app.agents.interview_coach_agent.fetch_model_settings",
            return_value=MagicMock(provider="openai"),
        ),
        patch("app.agents.interview_coach_agent.build_agent_llm", return_value=mock_llm),
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
    mock_llm.responses = [
        json.dumps(
            {
                "clarity": 8,
                "relevance": 7,
                "depth": 6,
                "feedback": "Good answer with concrete metrics.",
                "rating": "excellent",
            }
        )
    ]

    with (
        patch(
            "app.agents.interview_coach_agent.fetch_model_settings",
            return_value=MagicMock(provider="openai"),
        ),
        patch("app.agents.interview_coach_agent.build_agent_llm", return_value=mock_llm),
        patch(
            "app.agents.interview_coach_agent._get_interview_session",
            return_value={
                "user_id": "usr_test",
                "questions": [{"question": "Tell me about yourself", "type": "behavioral"}]
            },
        ),
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


class _OwnershipResult:
    def __init__(self, value):
        self.value = value

    def scalar_one_or_none(self):
        return self.value


class _FakeInterviewDB:
    """Async-session double: execute() answers the IDOR ownership check."""

    def __init__(self, owned_id):
        self.owned_id = owned_id

    async def execute(self, *a, **k):
        return _OwnershipResult(self.owned_id)


@pytest.mark.asyncio
async def test_start_session_queues_a_durable_run(monkeypatch):
    from app.api.v1 import interview

    queued = {}

    async def fake_queue(db, user, task_type, context):
        queued.update(task_type=task_type, context=context)
        return "run-1"

    monkeypatch.setattr(interview, "queue_agent_run", fake_queue)
    user = MagicMock(id=uuid.uuid4())

    result = await interview.start_session(
        interview.StartSessionRequest(role="Python Engineer", company="Stripe"),
        db=MagicMock(),
        current_user=user,
    )

    assert result == {"run_id": "run-1", "status": "queued"}
    assert queued["task_type"] == "interview_coach"
    assert queued["context"] == {"role": "Python Engineer", "company": "Stripe"}


@pytest.mark.asyncio
async def test_submit_answer_queues_evaluation_for_owned_session(monkeypatch):
    from app.api.v1 import interview

    queued = {}

    async def fake_queue(db, user, task_type, context):
        queued.update(task_type=task_type, context=context)
        return "run-2"

    monkeypatch.setattr(interview, "queue_agent_run", fake_queue)
    session_id = uuid.uuid4()
    answer = "I led the migration of our billing service to a queue based design."

    result = await interview.submit_answer(
        session_id,
        interview.AnswerRequest(answer_text=answer, question_index=1),
        db=_FakeInterviewDB(owned_id=session_id),
        current_user=MagicMock(id=uuid.uuid4()),
    )

    assert result == {"run_id": "run-2", "status": "queued", "question_index": 1}
    assert queued["task_type"] == "evaluate_answer"
    assert queued["context"] == {
        "session_id": str(session_id),
        "question_index": 1,
        "answer_text": answer,
    }


@pytest.mark.asyncio
async def test_submit_answer_rejects_another_users_session(monkeypatch):
    from fastapi import HTTPException

    from app.api.v1 import interview

    async def fake_queue(*_a, **_k):
        raise AssertionError("must not queue a run for a session the user does not own")

    monkeypatch.setattr(interview, "queue_agent_run", fake_queue)
    answer = "I led the migration of our billing service to a queue based design."

    with pytest.raises(HTTPException) as exc:
        await interview.submit_answer(
            uuid.uuid4(),
            interview.AnswerRequest(answer_text=answer, question_index=0),
            db=_FakeInterviewDB(owned_id=None),
            current_user=MagicMock(id=uuid.uuid4()),
        )
    assert exc.value.status_code == 404


def test_merge_answer_replaces_a_resubmitted_answer():
    from app.agents.interview_coach_agent import merge_answer

    answers, scores = merge_answer([], [], 0, "first try", 40)
    answers, scores = merge_answer(answers, scores, 0, "second try", 70)

    assert scores == [70]
    assert answers == [{"question_index": 0, "answer_text": "second try"}]


def test_merge_answer_appends_new_questions_in_order():
    from app.agents.interview_coach_agent import merge_answer

    answers, scores = merge_answer(None, None, 0, "a", 50)
    answers, scores = merge_answer(answers, scores, 1, "b", 80)
    answers, scores = merge_answer(answers, scores, 0, "a again", 60)

    assert scores == [60, 80]
    assert [a["question_index"] for a in answers] == [0, 1]


def test_answer_request_bounds():
    import pytest
    from pydantic import ValidationError

    from app.api.v1.interview import AnswerRequest

    with pytest.raises(ValidationError):
        AnswerRequest(answer_text="x", question_index=-1)
    with pytest.raises(ValidationError):
        AnswerRequest(answer_text="x" * 8001, question_index=0)
