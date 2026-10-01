import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
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


class SessionListItem(BaseModel):
    id: uuid.UUID
    role: str
    company: str | None
    status: str
    overall_score: int | None
    question_count: int
    answered_count: int
    started_at: datetime
    completed_at: datetime | None


@router.get("/sessions", response_model=list[SessionListItem])
async def list_sessions(
    limit: int = Query(30, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """The member's past mock interviews, newest first. Question and answer
    text stays in GET /session/{id}/summary; this is just the list."""
    rows = (
        (
            await db.execute(
                select(InterviewSession)
                .where(InterviewSession.user_id == current_user.id)
                .order_by(InterviewSession.started_at.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [
        SessionListItem(
            id=row.id,
            role=row.role,
            company=row.company,
            status=row.status,
            overall_score=row.overall_score,
            question_count=len(row.questions or []),
            answered_count=len(row.answers or []),
            started_at=row.started_at,
            completed_at=row.completed_at,
        )
        for row in rows
    ]


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
