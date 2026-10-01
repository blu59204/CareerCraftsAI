import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import queue_agent_run
from app.models.db import InterviewSession, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/interview", tags=["interview"])


class StartSessionRequest(BaseModel):
    role: str
    company: str | None = None
    question_type: str | None = None  # behavioral | technical | situational


class AnswerRequest(BaseModel):
    answer_text: str = Field(max_length=8000)
    question_index: int = Field(ge=0, le=100)


@router.post("/session/start")
async def start_session(
    body: StartSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Durable agent run: poll GET /agents/runs/{run_id}; its output carries
    # session_id and questions.
    run_id = await queue_agent_run(
        db, current_user, "interview_coach", body.model_dump(exclude_none=True)
    )
    return {"run_id": run_id, "status": "queued"}


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

    # Durable agent run: poll GET /agents/runs/{run_id} for the feedback,
    # then read the session for the next question or the summary.
    run_id = await queue_agent_run(
        db,
        current_user,
        "evaluate_answer",
        {
            "session_id": str(session_id),
            "question_index": body.question_index,
            "answer_text": body.answer_text,
        },
    )
    return {"run_id": run_id, "status": "queued", "question_index": body.question_index}


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
