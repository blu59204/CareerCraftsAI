import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, InterviewSession, User

router = APIRouter(prefix="/interview", tags=["interview"])


class StartSessionRequest(BaseModel):
    role: str
    company: str | None = None
    question_type: str | None = None  # behavioral | technical | situational


class AnswerRequest(BaseModel):
    answer: str


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
    await harness.run(
        user_id=str(current_user.id),
        task_type="interview_coach",
        context=body.model_dump(exclude_none=True),
        user_settings={},
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "running"}


@router.post("/session/{session_id}/answer")
async def submit_answer(
    session_id: uuid.UUID,
    body: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if len(body.answer.split()) < 10:
        raise HTTPException(status_code=422, detail="Answer must be at least 10 words")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="interview_coach",
        status="running",
        input={"session_id": str(session_id), "answer": body.answer},
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    await harness.run(
        user_id=str(current_user.id),
        task_type="evaluate_answer",
        context={"session_id": str(session_id), "answer": body.answer},
        user_settings={},
        run_id=run_id,
    )
    return {"run_id": run_id, "status": "running"}


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
