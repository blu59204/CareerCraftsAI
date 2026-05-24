"""
memory/models.py — Pydantic v2 models for the memory subsystem.
"""

from uuid import UUID
from datetime import datetime
from typing import Literal, Optional, Any

from pydantic import BaseModel, Field

MemoryType = Literal["preference", "fact", "outcome", "blacklist", "skill", "style"]
OutcomeType = Literal["success", "failure", "pending", "skipped"]


class Memory(BaseModel):
    """A single user memory record persisted in user_memories."""

    id: Optional[UUID] = None
    user_id: UUID
    memory_type: MemoryType
    content: str
    source_agent: Optional[str] = None
    confidence: float = 1.0
    times_used: int = 0
    is_active: bool = True
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class Episode(BaseModel):
    """A completed agent run episode stored in agent_episodes."""

    id: Optional[UUID] = None
    user_id: UUID
    agent_type: str
    summary: Optional[str] = None
    input: Optional[dict] = None
    output: Optional[dict] = None
    outcome: Optional[OutcomeType] = None
    created_at: Optional[datetime] = None


class Learning(BaseModel):
    """A cross-user agent learning stored in agent_learnings."""

    id: Optional[UUID] = None
    agent_type: str
    learning: str
    evidence_count: int = 1
    success_rate: float = 1.0
    last_applied: Optional[datetime] = None
    created_at: Optional[datetime] = None


class AgentContext(BaseModel):
    """Full context bundle injected into an agent before it runs."""

    preferences: list[str] = Field(default_factory=list)
    blacklist: list[str] = Field(default_factory=list)
    past_episodes: list[dict] = Field(default_factory=list)
    learnings: list[str] = Field(default_factory=list)
    session_context: dict[str, Any] = Field(default_factory=dict)
    user_style: str = ""


class MemorySaveRequest(BaseModel):
    """Request body for POST /api/memory/save."""

    content: str = Field(min_length=1, max_length=5000)
    memory_type: MemoryType
    source_agent: Optional[str] = None
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
