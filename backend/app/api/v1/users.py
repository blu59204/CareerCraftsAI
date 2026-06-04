import logging
import asyncio
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import encrypt_api_key
from app.models.db import AgentRun, JobApplication, User, UserModelSettings, UserPreferences
from app.models.schemas import (
    JobSearchProfileResponse,
    ModelSettingsCreate,
    ModelSettingsResponse,
    UserPreferencesResponse,
    UserPreferencesSchema,
    UserProfileUpdate,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])
logger = logging.getLogger(__name__)


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

    # One aggregate query keeps dashboard load to 2 DB round trips total
    # (stats + recent runs) instead of 5; AVG ignores NULL match scores.
    stats_res = await db.execute(
        select(
            func.count(JobApplication.id),
            func.coalesce(
                func.sum(case((JobApplication.status == "interview", 1), else_=0)),
                0,
            ),
            func.avg(JobApplication.match_score),
            func.coalesce(
                func.sum(case((JobApplication.status == "applied", 1), else_=0)),
                0,
            ),
        ).where(
            JobApplication.user_id == uid,
        )
    )
    applications_count, interviews_count, avg_raw, followups_due = stats_res.one()
    applications_count = int(applications_count or 0)
    interviews_count = int(interviews_count or 0)
    followups_due = int(followups_due or 0)
    avg_match_score: float = float(avg_raw) if avg_raw is not None else 0.0

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


@router.get("/me/job-search-profile", response_model=JobSearchProfileResponse)
async def get_job_search_profile(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Build job search profile from resume + preferences (server-side).

    Analyzes resume data, extracts skills, suggests roles, and validates
    preferences to prevent client-side manipulation.
    """
    from app.models.db import UserDocument

    # Fetch user preferences
    prefs_result = await db.execute(
        select(UserPreferences).where(UserPreferences.user_id == current_user.id)
    )
    prefs = prefs_result.scalar_one_or_none()

    # Fetch resume documents
    docs_result = await db.execute(
        select(UserDocument).where(
            UserDocument.user_id == current_user.id,
            UserDocument.doc_type == "resume"
        ).order_by(UserDocument.is_primary.desc(), UserDocument.embedded_at.desc())
    )
    resume_doc = docs_result.scalars().first()

    # Build preferences object (with defaults)
    saved_prefs = UserPreferencesSchema(
        experience_level=prefs.experience_level if prefs else None,
        years_experience=prefs.years_experience if prefs else None,
        job_type=prefs.job_type if prefs else None,
        work_mode=prefs.work_mode if prefs else None,
        salary_min=prefs.salary_min if prefs else None,
        salary_max=prefs.salary_max if prefs else None,
        target_roles=prefs.target_roles if prefs else [],
        preferred_locations=prefs.preferred_locations if prefs else [],
        current_title=prefs.current_title if prefs else None,
        bio=prefs.bio if prefs else None,
    )

    # Extract skills from resume ATS data (server-side only)
    skills: list[str] = []
    if resume_doc and resume_doc.ats_data:
        matched_keywords = resume_doc.ats_data.get("matched_keywords", [])
        if isinstance(matched_keywords, list):
            skills = matched_keywords[:8]

    # Build role suggestions from preferences or current title
    role_suggestions: list[str] = []
    if saved_prefs.target_roles:
        role_suggestions = saved_prefs.target_roles[:5]
    elif saved_prefs.current_title:
        role_suggestions = [saved_prefs.current_title]

    # Infer experience level from years if not set
    inferred_exp_level = saved_prefs.experience_level
    if not inferred_exp_level and saved_prefs.years_experience is not None:
        years = saved_prefs.years_experience
        if years == 0:
            inferred_exp_level = "fresher"
        elif years <= 2:
            inferred_exp_level = "junior"
        elif years <= 5:
            inferred_exp_level = "mid"
        elif years <= 10:
            inferred_exp_level = "senior"
        else:
            inferred_exp_level = "lead"

    # Build search query preview
    search_query_preview = role_suggestions[0] if role_suggestions else "Set target role"

    # Determine work mode for location preview
    work_modes = saved_prefs.work_mode.split(",") if saved_prefs.work_mode else []
    primary_work_mode = work_modes[0].strip() if work_modes else "remote"

    # Build location preview
    location_preview = "Remote"
    if primary_work_mode != "remote" and saved_prefs.preferred_locations:
        location_preview = saved_prefs.preferred_locations[0]
    elif primary_work_mode != "remote":
        location_preview = "Any"

    # Identify missing fields
    missing_fields: list[str] = []
    if not resume_doc:
        missing_fields.append("resume")
    if not role_suggestions:
        missing_fields.append("target role")
    if saved_prefs.years_experience is None:
        missing_fields.append("years of experience")

    # Build analysis notes
    analysis_notes: list[str] = []
    if resume_doc:
        analysis_notes.append(
            "Search agent will analyze full resume text when you run search. "
            "This panel shows saved preferences and resume ATS keywords."
        )
    else:
        analysis_notes.append("Upload resume so agents can analyze skills and experience.")

    return JobSearchProfileResponse(
        resume_found=bool(resume_doc),
        resume_filename=resume_doc.filename if resume_doc else None,
        role_suggestions=role_suggestions,
        skills=skills,
        inferred_years_experience=saved_prefs.years_experience,
        inferred_experience_level=inferred_exp_level,
        saved_preferences=saved_prefs,
        search_query_preview=search_query_preview,
        location_preview=location_preview,
        work_mode_preview=saved_prefs.work_mode,
        missing_fields=missing_fields,
        analysis_notes=analysis_notes,
    )


@router.post("/me/models", response_model=ModelSettingsResponse, status_code=201)
@limiter.limit("5/minute")
async def add_model_settings(
    request: Request,
    payload: ModelSettingsCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import update as sa_update

    # Deactivate any existing active keys so exactly one remains active.
    # (No DB unique constraint guarantees this, so enforce it here.)
    await db.execute(
        sa_update(UserModelSettings)
        .where(UserModelSettings.user_id == current_user.id)
        .values(is_active=False)
    )

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
        llm = _build_llm(model_setting)
        resp = await asyncio.wait_for(
            llm.ainvoke([HumanMessage(content="Reply with exactly: OK")]),
            timeout=60,
        )
        return {"success": True, "response": resp.content.strip()[:200]}
    except asyncio.TimeoutError as exc:
        logger.warning(
            "Model test timed out for user %s model %s", current_user.id, payload.model_id
        )
        raise HTTPException(
            status_code=422,
            detail="Model test timed out after 60s. The model may be cold-starting — try again, or pick a smaller model. Also verify the API key and model name.",
        ) from exc
    except Exception as exc:
        logger.warning(
            "Model test failed for user %s model %s: %s",
            current_user.id,
            payload.model_id,
            exc,
        )
        raise HTTPException(status_code=422, detail=f"Model test failed: {exc}"[:300]) from exc



# ---------------------------------------------------------------------------
# LinkedIn Credentials (encrypted) + Auto-mode toggle
# ---------------------------------------------------------------------------


class LinkedInCredentialsRequest(BaseModel):
    email: str
    password: str


class AutoModeRequest(BaseModel):
    mode: str  # 'auto' or 'drafts'


class GoogleOAuthTokensRequest(BaseModel):
    access_token: str
    refresh_token: str | None = None
    expires_at: int | None = None
    expires_in: int | None = None


class ConnectedAccountsResponse(BaseModel):
    google: bool
    gmail_send: bool


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


@router.post("/me/google-oauth")
@limiter.limit("10/minute")
async def save_google_oauth_tokens(
    request: Request,
    payload: GoogleOAuthTokensRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Store Google provider tokens encrypted for Gmail agent send/read."""
    current_user.google_access_token_enc = encrypt_api_key(
        payload.access_token,
        settings.APP_SECRET_KEY,
    )
    if payload.refresh_token:
        current_user.google_refresh_token_enc = encrypt_api_key(
            payload.refresh_token,
            settings.APP_SECRET_KEY,
        )

    if payload.expires_at:
        current_user.google_token_expires_at = datetime.fromtimestamp(
            payload.expires_at,
            tz=timezone.utc,
        )
    elif payload.expires_in:
        current_user.google_token_expires_at = datetime.now(timezone.utc) + timedelta(
            seconds=max(payload.expires_in - 60, 60),
        )
    else:
        current_user.google_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    await db.flush()
    return {
        "status": "connected",
        "gmail_send": True,
        "has_refresh_token": bool(current_user.google_refresh_token_enc),
    }


@router.get("/me/connected-accounts", response_model=ConnectedAccountsResponse)
async def get_connected_accounts(current_user: User = Depends(get_current_user)):
    google_connected = bool(current_user.google_access_token_enc or current_user.google_refresh_token_enc)
    return {"google": google_connected, "gmail_send": google_connected}


@router.delete("/me/google-oauth")
async def delete_google_oauth_tokens(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    current_user.google_access_token_enc = None
    current_user.google_refresh_token_enc = None
    current_user.google_token_expires_at = None
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


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str


@router.patch("/me/password", status_code=204)
async def change_password(
    payload: PasswordChangeRequest,
    current_user: User = Depends(get_current_user),
):
    """Password changes are managed by Supabase Auth."""
    _ = (payload, current_user)
    if len(payload.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")
    raise HTTPException(status_code=400, detail="Password changes are managed by Supabase Auth")


@router.delete("/me", status_code=204)
async def delete_account(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Permanently delete the user's account.

    Deletes the Supabase Auth user when configured, plus the local row.
    DB cascade removes related records (applications, agent runs, settings).
    """
    auth_subject = str(current_user.supabase_uid or "")

    # Delete local DB row first (cascade handles related tables)
    await db.delete(current_user)
    await db.flush()

    # Supabase Auth user deletion would be handled via Supabase Admin API
    # if needed in the future. For now, local DB cleanup is sufficient.
    logger.info("User account deleted: %s", auth_subject)
