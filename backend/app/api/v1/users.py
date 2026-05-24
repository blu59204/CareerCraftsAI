from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import encrypt_api_key
from app.models.db import AgentRun, JobApplication, User, UserModelSettings
from app.models.schemas import (
    ModelSettingsCreate,
    ModelSettingsResponse,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


class DashboardStats(BaseModel):
    applications_count: int
    interviews_count: int
    avg_match_score: float
    followups_due: int
    recent_agent_runs: list[dict]


@router.get("/me/stats", response_model=DashboardStats)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    uid = current_user.id

    # applications_count
    apps_count_res = await db.execute(
        select(func.count(JobApplication.id)).where(JobApplication.user_id == uid)
    )
    applications_count: int = apps_count_res.scalar_one() or 0

    # interviews_count
    interviews_res = await db.execute(
        select(func.count(JobApplication.id)).where(
            JobApplication.user_id == uid,
            JobApplication.status == "interview",
        )
    )
    interviews_count: int = interviews_res.scalar_one() or 0

    # avg_match_score
    avg_res = await db.execute(
        select(func.avg(JobApplication.match_score)).where(
            JobApplication.user_id == uid,
            JobApplication.match_score.isnot(None),
        )
    )
    avg_raw = avg_res.scalar_one()
    avg_match_score: float = float(avg_raw) if avg_raw is not None else 0.0

    # followups_due (status == 'applied', implying follow-up needed)
    followups_res = await db.execute(
        select(func.count(JobApplication.id)).where(
            JobApplication.user_id == uid,
            JobApplication.status == "applied",
        )
    )
    followups_due: int = followups_res.scalar_one() or 0

    # recent_agent_runs — last 5
    runs_res = await db.execute(
        select(AgentRun)
        .where(AgentRun.user_id == uid)
        .order_by(AgentRun.started_at.desc())
        .limit(5)
    )
    runs = runs_res.scalars().all()
    recent_agent_runs = [
        {
            "id": str(r.id),
            "agent_type": r.agent_type,
            "status": r.status,
            "created_at": r.started_at.isoformat() if r.started_at else None,
        }
        for r in runs
    ]

    return DashboardStats(
        applications_count=applications_count,
        interviews_count=interviews_count,
        avg_match_score=avg_match_score,
        followups_due=followups_due,
        recent_agent_runs=recent_agent_runs,
    )


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.post("/me/models", response_model=ModelSettingsResponse, status_code=201)
async def add_model_settings(
    payload: ModelSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    encrypted_key = encrypt_api_key(payload.api_key, settings.APP_SECRET_KEY)
    model_setting = UserModelSettings(
        user_id=current_user.id,
        provider=payload.provider,
        api_key_enc=encrypted_key,
        model_name=payload.model_name,
        ollama_url=payload.ollama_url,
        is_active=True,
    )
    db.add(model_setting)
    await db.flush()
    return model_setting


@router.get("/me/models", response_model=list[ModelSettingsResponse])
async def list_model_settings(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserModelSettings).where(UserModelSettings.user_id == current_user.id)
    )
    return result.scalars().all()
