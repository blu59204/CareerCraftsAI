from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.rate_limit import limiter
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import decrypt_api_key, encrypt_api_key
from app.models.db import AgentRun, JobApplication, User, UserModelSettings, UserPreferences
from app.models.schemas import (
    ModelSettingsCreate,
    ModelSettingsResponse,
    UserPreferencesResponse,
    UserPreferencesSchema,
    UserProfileUpdate,
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


@router.patch("/me", response_model=UserResponse)
async def update_profile(
    payload: UserProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    await db.flush()
    return current_user


@router.get("/me/preferences", response_model=UserPreferencesResponse | None)
async def get_preferences(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    return result.scalar_one_or_none()


@router.patch("/me/preferences", response_model=UserPreferencesResponse)
async def upsert_preferences(
    payload: UserPreferencesSchema,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = result.scalar_one_or_none()
    update_data = payload.model_dump(exclude_none=True)
    if prefs is None:
        prefs = UserPreferences(user_id=current_user.id, **update_data)
        db.add(prefs)
    else:
        for field, value in update_data.items():
            setattr(prefs, field, value)
    await db.flush()
    return prefs


@router.post("/me/models", response_model=ModelSettingsResponse, status_code=201)
@limiter.limit("5/minute")
async def add_model_settings(
    request: Request,
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


class ModelTestRequest(BaseModel):
    model_id: str


@router.patch("/me/models/{model_id}/activate", response_model=ModelSettingsResponse)
async def activate_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid as _uuid
    # deactivate all
    all_res = await db.execute(
        select(UserModelSettings).where(UserModelSettings.user_id == current_user.id)
    )
    for m in all_res.scalars().all():
        m.is_active = False
    # activate target
    target_res = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.id == _uuid.UUID(model_id),
            UserModelSettings.user_id == current_user.id,
        )
    )
    target = target_res.scalars().first()
    if not target:
        raise HTTPException(status_code=404, detail="Model not found")
    target.is_active = True
    await db.flush()
    return target


@router.delete("/me/models/{model_id}", status_code=204)
async def delete_model(
    model_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid as _uuid
    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.id == _uuid.UUID(model_id),
            UserModelSettings.user_id == current_user.id,
        )
    )
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    await db.delete(model)
    await db.flush()


@router.post("/me/models/test")
async def test_model(
    payload: ModelTestRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    import uuid as _uuid
    from langchain_core.messages import HumanMessage
    from app.core.model_router import _build_llm

    result = await db.execute(
        select(UserModelSettings).where(
            UserModelSettings.id == _uuid.UUID(payload.model_id),
            UserModelSettings.user_id == current_user.id,
        )
    )
    model_setting = result.scalars().first()
    if not model_setting:
        raise HTTPException(status_code=404, detail="Model setting not found")

    try:
        api_key = decrypt_api_key(model_setting.api_key_enc, settings.APP_SECRET_KEY)
        # Temporarily swap decrypted key for _build_llm
        original_enc = model_setting.api_key_enc
        model_setting.api_key_enc = encrypt_api_key(api_key, settings.APP_SECRET_KEY)
        llm = _build_llm(model_setting)
        model_setting.api_key_enc = original_enc

        resp = llm.invoke([HumanMessage(content="Reply with exactly: OK")])
        return {"success": True, "response": resp.content.strip()[:200]}
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))



# ---------------------------------------------------------------------------
# LinkedIn Credentials (encrypted) + Auto-mode toggle
# ---------------------------------------------------------------------------


class LinkedInCredentialsRequest(BaseModel):
    email: str
    password: str


class AutoModeRequest(BaseModel):
    mode: str  # 'auto' or 'drafts'


@router.post("/me/linkedin-credentials")
@limiter.limit("5/minute")
async def save_linkedin_credentials(
    request: Request,
    payload: LinkedInCredentialsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store LinkedIn credentials encrypted (AES-256-GCM, same as API keys)."""
    from app.core.security import encrypt_api_key

    current_user.linkedin_email_enc = encrypt_api_key(payload.email, settings.APP_SECRET_KEY)
    current_user.linkedin_password_enc = encrypt_api_key(payload.password, settings.APP_SECRET_KEY)
    await db.flush()
    return {"status": "saved", "message": "LinkedIn credentials stored encrypted"}


@router.delete("/me/linkedin-credentials")
async def delete_linkedin_credentials(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Remove stored LinkedIn credentials."""
    current_user.linkedin_email_enc = None
    current_user.linkedin_password_enc = None
    await db.flush()
    return {"status": "deleted"}


@router.patch("/me/auto-mode")
async def set_auto_mode(
    payload: AutoModeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Toggle auto-mode: 'auto' (send immediately) or 'drafts' (save for review)."""
    if payload.mode not in ("auto", "drafts"):
        raise HTTPException(status_code=400, detail="mode must be 'auto' or 'drafts'")
    current_user.auto_mode = payload.mode
    await db.flush()
    return {"auto_mode": payload.mode}


@router.get("/me/auto-mode")
async def get_auto_mode(
    current_user: User = Depends(get_current_user),
):
    """Get current auto-mode setting."""
    return {"auto_mode": current_user.auto_mode or "drafts"}
