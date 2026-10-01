import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import queue_agent_run
from app.models.db import CoverLetterVersion, User

router = APIRouter(prefix="/cover-letter", tags=["cover-letter"])

VALID_TONES = {"formal", "casual", "bold"}


class GenerateRequest(BaseModel):
    application_id: uuid.UUID | None = None
    tone: str = "formal"
    jd_text: str | None = None


class GenerateResponse(BaseModel):
    run_id: str
    status: str
    content: str | None = None
    tone: str | None = None
    warnings: list[str] = []
    document_id: str | None = None
    version_number: int | None = None


@router.post("/generate", response_model=GenerateResponse)
async def generate_cover_letter(
    payload: GenerateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.tone not in VALID_TONES:
        raise HTTPException(status_code=400, detail=f"tone must be one of: {VALID_TONES}")

    jd_text = (payload.jd_text or "").strip()
    if not jd_text and payload.application_id:
        # Fall back to the application's stored JD (owner-checked).
        from app.models.db import JobApplication

        app_row = (
            (
                await db.execute(
                    select(JobApplication).where(
                        JobApplication.id == payload.application_id,
                        JobApplication.user_id == current_user.id,
                    )
                )
            )
            .scalars()
            .first()
        )
        if app_row is None:
            raise HTTPException(status_code=404, detail="Application not found")
        jd_text = (app_row.jd_text or "").strip()
    if not jd_text:
        raise HTTPException(
            status_code=400,
            detail="jd_text is required (or pick an application with a saved job description)",
        )

    # Runs as a durable agent workflow; the client polls GET /agents/runs/{id}
    # and approves the draft through POST /agents/{id}/approve.
    run_id = await queue_agent_run(
        db,
        current_user,
        "cover_letter",
        {
            "tone": payload.tone,
            "job_application_id": (str(payload.application_id) if payload.application_id else None),
            "jd_text": jd_text,
        },
    )
    return GenerateResponse(run_id=run_id, status="queued", tone=payload.tone)


@router.get("/{app_id}/history")
async def cover_letter_history(
    app_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CoverLetterVersion)
        .where(
            CoverLetterVersion.job_application_id == app_id,
            CoverLetterVersion.user_id == current_user.id,
        )
        .order_by(CoverLetterVersion.created_at.desc())
    )
    return result.scalars().all()
