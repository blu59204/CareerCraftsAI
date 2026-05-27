"""
memory/routes.py — FastAPI router for the memory subsystem.

Mounted at /api/memory in app/main.py.
All endpoints require a valid Supabase JWT (via get_current_user).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import redis
from fastapi import APIRouter, Depends, HTTPException, Query

from app.api.v1.deps import get_current_user
from app.core.config import settings
from app.models.db import User
from memory.embedder import MemoryEmbedder
from memory.manager import MemoryManager
from memory.models import Memory, MemorySaveRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/memory", tags=["memory"])


# ---------------------------------------------------------------------------
# Dependency helpers
# ---------------------------------------------------------------------------

def _redis_client() -> redis.Redis:
    """Return a module-level Redis client (thread-safe, connection-pooled)."""
    return redis.from_url(settings.REDIS_URL, decode_responses=True)


def _get_manager(user: User) -> MemoryManager:
    """
    Build a MemoryManager scoped to the current request.

    Reads the user's active model settings to configure the embedder.
    Falls back to a plain dict with no api_key when no settings exist.
    """
    # Resolve the active provider/key from the user's model_settings relationship.
    # model_settings is a list (eagerly loaded by SQLAlchemy in get_current_user).
    user_settings: dict[str, str] = {"provider": "openai", "api_key": ""}
    if user.model_settings:
        for ms in user.model_settings:
            if ms.is_active:
                user_settings = {
                    "provider": ms.provider,
                    "api_key": ms.api_key_enc or "",  # decryption handled upstream
                }
                break

    rc = _redis_client()
    embedder = MemoryEmbedder(user_settings, redis_client=rc)

    # asyncpg requires a plain postgresql:// DSN — strip SQLAlchemy driver prefix
    db_url = settings.DATABASE_URL.replace("+asyncpg", "")
    return MemoryManager(
        db_url=db_url,
        redis_client=rc,
        embedder=embedder,
    )


def _std(data: Any, count: int | None = None) -> dict:
    """Standard response envelope."""
    if count is None:
        count = len(data) if isinstance(data, list) else 1
    return {"success": True, "data": data, "count": count}


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/preferences")
async def list_preferences(
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all active preference memories for the authenticated user."""
    mgr = _get_manager(current_user)
    memories = await mgr.get_preferences(current_user.id)
    return _std([m.model_dump(mode="json") for m in memories])


@router.get("/blacklist")
async def list_blacklist(
    current_user: User = Depends(get_current_user),
) -> dict:
    """List all active blacklist memories (companies / roles to avoid)."""
    mgr = _get_manager(current_user)
    memories = await mgr.get_blacklist(current_user.id)
    return _std([m.model_dump(mode="json") for m in memories])


@router.get("/recall")
async def recall_memories(
    q: str = Query(..., min_length=1, description="Semantic search query"),
    k: int = Query(default=5, ge=1, le=20, description="Number of results"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Semantic recall — return the k memories most relevant to query q.
    Falls back to keyword search when the embedding provider is unavailable.
    """
    mgr = _get_manager(current_user)
    memories = await mgr.recall(current_user.id, query=q, k=k)
    return _std([m.model_dump(mode="json") for m in memories])


@router.post("/save")
async def save_memory(
    body: MemorySaveRequest,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Save a new memory for the authenticated user."""
    mgr = _get_manager(current_user)
    memory = Memory(
        user_id=current_user.id,
        memory_type=body.memory_type,
        content=body.content,
        source_agent=body.source_agent,
        confidence=body.confidence,
    )
    mem_id = await mgr.save_memory(memory)
    if mem_id is None:
        raise HTTPException(status_code=500, detail="Failed to save memory")
    return _std({"id": str(mem_id)}, count=1)


@router.delete("/{memory_id}")
async def delete_memory(
    memory_id: UUID,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Soft-delete a memory by ID (sets is_active = false)."""
    mgr = _get_manager(current_user)
    ok = await mgr.delete_memory(memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Memory not found or already deleted")
    return _std({"deleted": str(memory_id)}, count=1)


@router.get("/episodes/{agent_type}")
async def list_episodes(
    agent_type: str,
    current_user: User = Depends(get_current_user),
) -> dict:
    """Return the 10 most recent episodes for a given agent type."""
    mgr = _get_manager(current_user)
    episodes = await mgr.recall_episodes(current_user.id, agent_type, limit=10)
    return _std([ep.model_dump(mode="json") for ep in episodes])


@router.get("/context/{agent_type}")
async def get_agent_context(
    agent_type: str,
    task: str = Query(default="", description="Task description for semantic context retrieval"),
    current_user: User = Depends(get_current_user),
) -> dict:
    """
    Build and return the full AgentContext for the given agent_type.

    This is the bundle injected into every LangGraph agent node before it runs.
    """
    mgr = _get_manager(current_user)
    ctx = await mgr.build_agent_context(current_user.id, agent_type, task=task)
    return _std(ctx.model_dump(mode="json"), count=1)


@router.post("/clear-session")
async def clear_session(
    current_user: User = Depends(get_current_user),
) -> dict:
    """Delete all short-term Redis session keys for the authenticated user."""
    mgr = _get_manager(current_user)
    deleted = mgr.clear_session(current_user.id)
    return _std({"keys_deleted": deleted}, count=deleted)
