from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.deps import get_current_user, get_db
from app.core.config import settings
from app.core.security import encrypt_api_key
from app.models.db import User, UserModelSettings
from app.models.schemas import (
    ModelSettingsCreate,
    ModelSettingsResponse,
    UserCreate,
    UserResponse,
)

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserResponse, status_code=201)
async def create_user(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.clerk_id == payload.clerk_id))
    existing = result.scalar_one_or_none()
    if existing:
        return existing
    user = User(**payload.model_dump())
    db.add(user)
    await db.flush()
    return user


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
