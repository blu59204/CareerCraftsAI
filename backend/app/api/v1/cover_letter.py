import asyncio
import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.harness import get_harness
from app.api.v1.deps import get_current_user, get_db
from app.api.v1.run_utils import apply_harness_result
from app.models.db import AgentRun, CoverLetterVersion, User

router = APIRouter(prefix="/cover-letter", tags=["cover-letter"])

VALID_TONES = {"formal", "casual", "bold"}
HARNESS_TIMEOUT_SECONDS = 120


class GenerateRequest(BaseModel):
    application_id: uuid.UUID | None = None
    tone: str = "formal"
    jd_text: str | None = None


class GenerateResponse(BaseModel):
    run_id: str
    status: str
    content: str | None = None
    tone: str | None = None
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
            await db.execute(
                select(JobApplication).where(
                    JobApplication.id == payload.application_id,
                    JobApplication.user_id == current_user.id,
                )
            )
        ).scalars().first()
        if app_row is None:
            raise HTTPException(status_code=404, detail="Application not found")
        jd_text = (app_row.jd_text or "").strip()
    if not jd_text:
        raise HTTPException(
            status_code=400,
            detail="jd_text is required (or pick an application with a saved job description)",
        )

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
    try:
        harness_result = await asyncio.wait_for(
            harness.run(
                user_id=str(current_user.id),
                task_type="cover_letter",
                context={
                    "tone": payload.tone,
                    "job_application_id": str(payload.application_id) if payload.application_id else None,
                    "jd_text": jd_text,
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
        raise HTTPException(status_code=504, detail="Cover letter generation timed out") from None

    apply_harness_result(agent_run, harness_result)
    await db.flush()

    # Pull the generated cover letter from the harness result so the
    # client gets the real content (not just a run_id to poll).
    action = harness_result.get("pending_action") or harness_result.get("result") or {}
    if not isinstance(action, dict):
        action = {}
    content = action.get("cover_letter_markdown") or action.get("content")
    status = harness_result.get("status", "completed")

    return GenerateResponse(
        run_id=run_id,
        status=status,
        content=content,
        tone=payload.tone,
        document_id=action.get("document_id"),
        version_number=action.get("version_number"),
    )


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
