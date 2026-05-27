import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, CoverLetterVersion, User

router = APIRouter(prefix="/cover-letter", tags=["cover-letter"])

VALID_TONES = {"formal", "casual", "bold"}


class GenerateRequest(BaseModel):
    application_id: uuid.UUID | None = None
    tone: str = "formal"
    jd_text: str | None = None


class GenerateResponse(BaseModel):
    run_id: str
    status: str


@router.post("/generate", response_model=GenerateResponse)
async def generate_cover_letter(
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.tone not in VALID_TONES:
        raise HTTPException(status_code=400, detail=f"tone must be one of: {VALID_TONES}")

    run_id = str(uuid.uuid4())
    agent_run = AgentRun(
        id=uuid.UUID(run_id),
        user_id=current_user.id,
        agent_type="cover_letter",
        status="running",
        input={"tone": payload.tone, "application_id": str(payload.application_id) if payload.application_id else None},
    )
    db.add(agent_run)
    await db.flush()

    harness = await get_harness()
    await harness.run(
        user_id=str(current_user.id),
        task_type="cover_letter",
        context={
            "tone": payload.tone,
            "application_id": str(payload.application_id) if payload.application_id else None,
            "jd_text": payload.jd_text,
        },
        user_settings={},
        run_id=run_id,
    )

    return GenerateResponse(run_id=run_id, status="running")


@router.get("/{app_id}/history")
async def cover_letter_history(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CoverLetterVersion)
        .where(
            CoverLetterVersion.application_id == app_id,
            CoverLetterVersion.user_id == current_user.id,
        )
        .order_by(CoverLetterVersion.created_at.desc())
    )
    return result.scalars().all()
