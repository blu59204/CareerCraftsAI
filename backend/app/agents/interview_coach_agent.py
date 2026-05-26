"""
interview_coach_agent.py — Interview Coach Agent for mock interview sessions.

Provides two LangGraph nodes:
  - start_session_node: generates role-specific interview questions
  - evaluate_answer_node: scores user answers 0-100 with rating and tips

Pure functions (testable without LLM/DB):
  - compute_rating_label(score) -> str
  - compute_session_summary(scores) -> dict
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings, _get_sync_factory
from app.services.rag_service import retrieve

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────────────

QUESTION_TYPES = {"behavioral", "technical", "situational"}

RATING_LABELS = {
    "poor": (0, 25),
    "fair": (26, 50),
    "good": (51, 75),
    "excellent": (76, 100),
}

_GENERATE_QUESTIONS_PROMPT = """You are an expert interview coach. Generate interview questions for a mock interview session.

Target Role: {role}
Company: {company}
{company_intel_section}
{type_filter_section}

Generate questions as a JSON array. Each question object must have:
  - "type": one of "behavioral", "technical", "situational"
  - "question": the question text
  - "context": brief explanation of what the question assesses

{type_instructions}

Return ONLY valid JSON array, no markdown fences or extra text."""

_EVALUATE_ANSWER_PROMPT = """You are an expert interview coach evaluating a candidate's answer.

Question: {question}
Question Type: {question_type}
Candidate's Answer: {answer}

Evaluate the answer and return a JSON object with:
  - "score": integer 0-100 (0=terrible, 100=perfect)
  - "tips": array of specific improvement suggestions (at least 1)

Scoring guidelines:
  - 0-25 (poor): Missing key elements, vague, off-topic
  - 26-50 (fair): Partially addresses the question, lacks depth or structure
  - 51-75 (good): Solid answer with room for improvement
  - 76-100 (excellent): Well-structured, specific examples, compelling delivery

Return ONLY valid JSON, no markdown fences or extra text."""


# ──────────────────────────────────────────────────────────────────────────────
# Pure Functions
# ──────────────────────────────────────────────────────────────────────────────


def compute_rating_label(score: int) -> str:
    """Map a numeric score (0-100) to a qualitative rating label.

    Returns one of: 'poor', 'fair', 'good', 'excellent'.
    Scores outside 0-100 are clamped to the nearest boundary.
    """
    score = max(0, min(100, score))
    for label, (low, high) in RATING_LABELS.items():
        if low <= score <= high:
            return label
    return "poor"


def compute_session_summary(scores: list[int]) -> dict:
    """Compute session summary from a list of individual answer scores.

    Returns dict with:
      - overall_score: round(mean(scores)), or 0 if empty
      - count: number of answers scored
      - rating: qualitative label for overall_score
    """
    if not scores:
        return {"overall_score": 0, "count": 0, "rating": "poor"}

    overall_score = round(sum(scores) / len(scores))
    return {
        "overall_score": overall_score,
        "count": len(scores),
        "rating": compute_rating_label(overall_score),
    }


# ──────────────────────────────────────────────────────────────────────────────
# LangGraph Nodes
# ──────────────────────────────────────────────────────────────────────────────


def start_session_node(state: AgentState) -> AgentState:
    """Generate interview questions for a mock session.

    Expected context keys:
      - role: target role title (required)
      - company: target company name (optional)
      - question_type: filter to single type (optional)
      - job_application_id: linked application (optional)
    """
    start_ts = time.monotonic()
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        role = ctx.get("role", "software engineer")
        company = ctx.get("company", "")
        question_type_filter = ctx.get("question_type")
        job_application_id = ctx.get("job_application_id")

        # Validate question_type filter if provided
        if question_type_filter and question_type_filter not in QUESTION_TYPES:
            return {
                **state,
                "status": "failed",
                "error": (
                    f"Invalid question_type: '{question_type_filter}'. "
                    f"Must be one of: {', '.join(sorted(QUESTION_TYPES))}"
                ),
            }

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            return {
                **state,
                "status": "failed",
                "error": "No active model settings configured for user",
            }

        # Retrieve company intel if available
        company_intel_text = ""
        if company:
            try:
                intel_chunks = retrieve(user_id, "company", company, model_settings, k=3)
                if intel_chunks:
                    company_intel_text = "\n".join(
                        c.page_content for c in intel_chunks
                    )
            except Exception as exc:
                logger.warning(
                    "interview_coach: failed to retrieve company intel for %s: %s",
                    company, exc,
                )

        # Build prompt
        company_intel_section = ""
        if company_intel_text:
            company_intel_section = (
                f"Company Intelligence:\n{company_intel_text[:1500]}"
            )

        if question_type_filter:
            type_filter_section = f"Question Type Filter: {question_type_filter} ONLY"
            type_instructions = (
                f"Generate exactly 5 questions, ALL of type '{question_type_filter}'."
            )
        else:
            type_filter_section = "Question Types: behavioral, technical, situational (all three)"
            type_instructions = (
                "Generate at least 5 questions total, with at least one of each type "
                "(behavioral, technical, situational)."
            )

        prompt = _GENERATE_QUESTIONS_PROMPT.format(
            role=role,
            company=company or "a company",
            company_intel_section=company_intel_section,
            type_filter_section=type_filter_section,
            type_instructions=type_instructions,
        )

        llm = _build_llm(model_settings)
        response = llm.invoke([HumanMessage(content=prompt)])

        raw = response.content.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rstrip("`").strip()

        try:
            questions = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                **state,
                "status": "failed",
                "error": f"interview_coach: LLM returned non-JSON response: {exc}",
            }

        if not isinstance(questions, list) or len(questions) == 0:
            return {
                **state,
                "status": "failed",
                "error": "interview_coach: LLM returned empty or invalid question list",
            }

        # Create session in database
        session_id = str(uuid.uuid4())
        duration_ms = int((time.monotonic() - start_ts) * 1000)

        _log_agent_run(
            user_id=user_id,
            agent_type="interview_coach",
            status="completed",
            input_data={"role": role, "company": company, "question_type": question_type_filter},
            output_data={"session_id": session_id, "question_count": len(questions)},
            duration_ms=duration_ms,
        )

        _save_interview_session(
            session_id=session_id,
            user_id=user_id,
            role=role,
            company=company,
            job_application_id=job_application_id,
            questions=questions,
        )

        return {
            **state,
            "status": "completed",
            "result": {
                "type": "interview_session_started",
                "session_id": session_id,
                "role": role,
                "company": company,
                "questions": questions,
                "question_count": len(questions),
            },
            "messages": state["messages"] + [
                AIMessage(
                    content=f"Interview session started for {role}"
                    + (f" at {company}" if company else "")
                    + f" with {len(questions)} questions."
                )
            ],
        }
    except Exception as exc:
        logger.error("interview_coach start_session failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": str(exc)}


def evaluate_answer_node(state: AgentState) -> AgentState:
    """Evaluate a user's answer to an interview question.

    Expected context keys:
      - session_id: the interview session ID (required)
      - question_index: which question is being answered (required)
      - answer_text: the user's answer (required, min 10 words)
    """
    start_ts = time.monotonic()
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        session_id = ctx.get("session_id")
        question_index = ctx.get("question_index", 0)
        answer_text = ctx.get("answer_text", "")

        # Validate answer minimum 10 words
        word_count = len(answer_text.split())
        if word_count < 10:
            return {
                **state,
                "status": "failed",
                "error": (
                    f"Answer too short ({word_count} words). "
                    "Please provide a more complete response (minimum 10 words)."
                ),
            }

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            return {
                **state,
                "status": "failed",
                "error": "No active model settings configured for user",
            }

        # Retrieve session questions
        session_data = _get_interview_session(session_id)
        if not session_data:
            return {
                **state,
                "status": "failed",
                "error": f"Interview session not found: {session_id}",
            }

        questions = session_data.get("questions", [])
        if question_index >= len(questions):
            return {
                **state,
                "status": "failed",
                "error": (
                    f"Question index {question_index} out of range "
                    f"(session has {len(questions)} questions)"
                ),
            }

        question = questions[question_index]
        question_text = question.get("question", "")
        question_type = question.get("type", "behavioral")

        # Evaluate with LLM
        prompt = _EVALUATE_ANSWER_PROMPT.format(
            question=question_text,
            question_type=question_type,
            answer=answer_text,
        )

        llm = _build_llm(model_settings)
        response = llm.invoke([HumanMessage(content=prompt)])

        raw = response.content.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
            raw = raw.rstrip("`").strip()

        try:
            evaluation = json.loads(raw)
        except json.JSONDecodeError as exc:
            return {
                **state,
                "status": "failed",
                "error": f"interview_coach: LLM returned non-JSON evaluation: {exc}",
            }

        # Normalize score to 0-100 range
        score = max(0, min(100, int(evaluation.get("score", 0))))
        tips = evaluation.get("tips", [])
        if not tips:
            tips = ["Try to provide more specific examples in your response."]

        rating = compute_rating_label(score)

        # Update session with answer and score
        _update_session_answer(
            session_id=session_id,
            question_index=question_index,
            answer_text=answer_text,
            score=score,
        )

        duration_ms = int((time.monotonic() - start_ts) * 1000)

        _log_agent_run(
            user_id=user_id,
            agent_type="interview_coach",
            status="completed",
            input_data={
                "session_id": session_id,
                "question_index": question_index,
                "answer_word_count": word_count,
            },
            output_data={"score": score, "rating": rating},
            duration_ms=duration_ms,
        )

        return {
            **state,
            "status": "completed",
            "result": {
                "type": "answer_evaluation",
                "session_id": session_id,
                "question_index": question_index,
                "score": score,
                "rating": rating,
                "tips": tips,
            },
            "messages": state["messages"] + [
                AIMessage(
                    content=f"Answer evaluated: {score}/100 ({rating}). "
                    + (f"Tip: {tips[0]}" if tips else "")
                )
            ],
        }
    except Exception as exc:
        logger.error(
            "interview_coach evaluate_answer failed for user %s: %s",
            state.get("user_id"), exc,
        )
        return {**state, "status": "failed", "error": str(exc)}


# ──────────────────────────────────────────────────────────────────────────────
# Database Helpers (sync, for use in agent thread)
# ──────────────────────────────────────────────────────────────────────────────


def _log_agent_run(
    user_id: str,
    agent_type: str,
    status: str,
    input_data: dict[str, Any] | None = None,
    output_data: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    tokens_used: int | None = None,
) -> None:
    """Log an agent run to the agent_runs table."""
    from app.models.db import AgentRun

    factory = _get_sync_factory()
    try:
        with factory() as db:
            run = AgentRun(
                user_id=user_id,
                agent_type=agent_type,
                status=status,
                input=input_data,
                output=output_data,
                duration_ms=duration_ms,
                tokens_used=tokens_used,
                completed_at=(
                    datetime.now(timezone.utc) if status in ("completed", "failed") else None
                ),
            )
            db.add(run)
            db.commit()
    except Exception as exc:
        logger.warning("interview_coach: failed to log agent run: %s", exc)


def _save_interview_session(
    session_id: str,
    user_id: str,
    role: str,
    company: str | None,
    job_application_id: str | None,
    questions: list[dict],
) -> None:
    """Create a new interview session record."""
    from app.models.db import InterviewSession

    factory = _get_sync_factory()
    try:
        with factory() as db:
            session = InterviewSession(
                id=session_id,
                user_id=user_id,
                role=role,
                company=company or None,
                job_application_id=job_application_id,
                questions=questions,
                answers=[],
                scores=[],
                status="in_progress",
            )
            db.add(session)
            db.commit()
    except Exception as exc:
        logger.warning("interview_coach: failed to save session: %s", exc)


def _get_interview_session(session_id: str) -> dict | None:
    """Retrieve interview session data by ID."""
    from sqlalchemy import select
    from app.models.db import InterviewSession

    factory = _get_sync_factory()
    try:
        with factory() as db:
            result = db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session = result.scalars().first()
            if not session:
                return None
            return {
                "id": str(session.id),
                "user_id": str(session.user_id),
                "role": session.role,
                "company": session.company,
                "questions": session.questions or [],
                "answers": session.answers or [],
                "scores": session.scores or [],
                "status": session.status,
            }
    except Exception as exc:
        logger.warning("interview_coach: failed to get session: %s", exc)
        return None


def _update_session_answer(
    session_id: str,
    question_index: int,
    answer_text: str,
    score: int,
) -> None:
    """Append answer and score to the session record."""
    from sqlalchemy import select
    from app.models.db import InterviewSession

    factory = _get_sync_factory()
    try:
        with factory() as db:
            result = db.execute(
                select(InterviewSession).where(InterviewSession.id == session_id)
            )
            session = result.scalars().first()
            if not session:
                return

            answers = list(session.answers or [])
            scores = list(session.scores or [])

            answers.append({
                "question_index": question_index,
                "answer_text": answer_text,
            })
            scores.append(score)

            session.answers = answers
            session.scores = scores

            # Compute summary if all questions answered
            if len(scores) >= len(session.questions or []):
                summary = compute_session_summary(scores)
                session.summary = summary
                session.overall_score = summary["overall_score"]
                session.status = "completed"
                session.completed_at = datetime.now(timezone.utc)

            db.commit()
    except Exception as exc:
        logger.warning("interview_coach: failed to update session answer: %s", exc)
