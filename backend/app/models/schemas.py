import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str | None = None
    clerk_id: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    full_name: str | None
    avatar_url: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ModelSettingsCreate(BaseModel):
    provider: Literal["anthropic", "openai", "google", "ollama", "nvidia_nim"]
    api_key: str
    model_name: str
    ollama_url: str | None = None


class ModelSettingsResponse(BaseModel):
    id: uuid.UUID
    provider: str
    model_name: str | None
    is_active: bool

    model_config = {"from_attributes": True}
