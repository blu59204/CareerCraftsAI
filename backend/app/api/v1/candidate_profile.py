import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.models.db import CandidateAnswer, CandidateProfile, User

router = APIRouter(prefix="/candidate-profile", tags=["candidate-profile"])


class CandidateProfileSchema(BaseModel):
    first_name: str | None = None
    last_name: str | None = None
    email: str | None = None
    phone: str | None = None
    city: str | None = None
    state: str | None = None
    country: str | None = None
    postal_code: str | None = None
    current_company: str | None = None
    current_title: str | None = None
    years_experience: float | None = None
    notice_period_days: int | None = None
    linkedin_url: str | None = None
    github_url: str | None = None
    portfolio_url: str | None = None
    current_salary: float | None = None
    expected_salary: float | None = None
    currency: str | None = None
    work_authorization: str | None = None
    requires_sponsorship: bool | None = None
    willing_to_relocate: bool | None = None
    remote_preference: str | None = None
    default_resume_id: uuid.UUID | None = None


class CandidateProfileResponse(CandidateProfileSchema):
    user_id: uuid.UUID
    version: int

    model_config = {"from_attributes": True}


class CandidateAnswerResponse(BaseModel):
    id: uuid.UUID
    question_key: str
    normalized_question: str | None
    answer_type: str
    answer: dict
    source: str
    confidence: float
    approved_by_user: bool

    model_config = {"from_attributes": True}


@router.get("/", response_model=CandidateProfileResponse | None)
async def get_candidate_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return (await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )).scalar_one_or_none()


@router.put("/", response_model=CandidateProfileResponse)
async def upsert_candidate_profile(
    payload: CandidateProfileSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    profile = (await db.execute(
        select(CandidateProfile).where(CandidateProfile.user_id == current_user.id)
    )).scalar_one_or_none()
    update_data = payload.model_dump(exclude_unset=True)
    if profile is None:
        profile = CandidateProfile(user_id=current_user.id, **update_data)
        db.add(profile)
    else:
        for field, value in update_data.items():
            setattr(profile, field, value)
        profile.version += 1
    await db.flush()
    return profile


@router.get("/answers", response_model=list[CandidateAnswerResponse])
async def list_candidate_answers(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(CandidateAnswer).where(CandidateAnswer.user_id == current_user.id)
    )
    return result.scalars().all()


@router.delete("/answers/{question_key}")
async def delete_candidate_answer(
    question_key: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Forget a saved answer so it stops being reused (e.g. it changed)."""
    answer = (await db.execute(
        select(CandidateAnswer).where(
            CandidateAnswer.user_id == current_user.id,
            CandidateAnswer.question_key == question_key,
        )
    )).scalar_one_or_none()
    if answer:
        await db.delete(answer)
        await db.flush()
    return {"deleted": answer is not None}
