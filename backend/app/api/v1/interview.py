import asyncio
import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.agents.interview_coach_agent import compute_session_summary
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import CLIENT_SAFE_AGENT_ERROR, apply_harness_result
from app.models.db import AgentRun, InterviewSession, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])

HARNESS_TIMEOUT_SECONDS = 120


class StartSessionRequest(BaseModel):
    role: str
    company: str | None = None
    question_type: str | None = None  # behavioral | technical | situational


class AnswerRequest(BaseModel):
    answer_text: str
    question_index: int


@router.post("/session/start")
async def start_session(
    body: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="interview_coach",
        status="running",
        input=body.model_dump(exclude_none=True),
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    try:
        harness_result = await asyncio.wait_for(
            harness.run(
                user_id=str(current_user.id),
                task_type="interview_coach",
                context=body.model_dump(exclude_none=True),
                user_settings={},
                run_id=run_id,
            ),
            timeout=HARNESS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        agent_run.status = "failed"
        agent_run.output = {"error": f"Timed out after {HARNESS_TIMEOUT_SECONDS}s"}
        await db.flush()
        raise HTTPException(status_code=504, detail="Interview session start timed out") from None
    output = apply_harness_result(agent_run, harness_result) or {}
    await db.flush()
    if agent_run.status == "failed":
        logger.warning("Interview session start failed for run %s: %s", run_id, harness_result.get("error"))
        raise HTTPException(status_code=502, detail=CLIENT_SAFE_AGENT_ERROR)
    questions = output.get("questions") or []
    question = questions[0] if questions else None
    return {
        "run_id": run_id,
        "status": agent_run.status,
        "session_id": output.get("session_id"),
        "question": question,
        "question_index": 0,
    }


@router.post("/session/{session_id}/answer")
async def submit_answer(
    session_id: uuid.UUID,
    body: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(body.answer_text.split()) < 10:
        raise HTTPException(status_code=422, detail="Answer must be at least 10 words")

    # Verify the session belongs to this user (prevents IDOR into another user's session)
    session_result = await db.execute(
        select(InterviewSession.id).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    if session_result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session not found")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="interview_coach",
        status="running",
        input={
            "session_id": str(session_id),
            "question_index": body.question_index,
            "answer_text": body.answer_text,
        },
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    try:
        harness_result = await asyncio.wait_for(
            harness.run(
                user_id=str(current_user.id),
                task_type="evaluate_answer",
                context={
                    "session_id": str(session_id),
                    "question_index": body.question_index,
                    "answer_text": body.answer_text,
                },
                user_settings={},
                run_id=run_id,
            ),
            timeout=HARNESS_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        agent_run.status = "failed"
        agent_run.output = {"error": f"Timed out after {HARNESS_TIMEOUT_SECONDS}s"}
        await db.flush()
        raise HTTPException(status_code=504, detail="Answer evaluation timed out") from None

    output = apply_harness_result(agent_run, harness_result) or {}
    await db.flush()
    if agent_run.status == "failed":
        logger.warning("Answer evaluation failed for run %s: %s", run_id, harness_result.get("error"))
        raise HTTPException(status_code=502, detail=CLIENT_SAFE_AGENT_ERROR)

    # Re-fetch the session (already own it, per the IDOR check above) to read
    # the questions/scores the agent's sync-DB helper just updated, so we can
    # derive the next question and, once the last one is answered, the summary.
    session_after = await db.execute(
        select(InterviewSession).where(InterviewSession.id == session_id)
    )
    session_row = session_after.scalar_one_or_none()
    questions = (session_row.questions if session_row else None) or []
    scores = (session_row.scores if session_row else None) or []

    next_index = body.question_index + 1
    next_question = questions[next_index] if next_index < len(questions) else None
    summary = compute_session_summary(scores) if next_question is None else None

    return {
        "run_id": run_id,
        "status": agent_run.status,
        "feedback": output,
        "next_question": next_question,
        "question_index": body.question_index,
        "summary": summary,
    }


@router.get("/session/{session_id}/summary")
async def get_summary(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.id == session_id,
            InterviewSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session
