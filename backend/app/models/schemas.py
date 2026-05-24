import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    supabase_uid: str = Field(min_length=36, max_length=36)


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelSettingsCreate(BaseModel):
    provider: Literal["anthropic", "openai", "google", "ollama", "nvidia_nim"]
    api_key: str = Field(min_length=1, max_length=200)
    model_name: str
    ollama_url: str | None = None


class ModelSettingsResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
