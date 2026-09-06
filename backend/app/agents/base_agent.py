from __future__ import annotations

from abc import ABC, abstractmethod

from langchain_core.language_models import BaseChatModel
from sqlalchemy.ext.asyncio import AsyncSession
import redis.asyncio as aioredis

from app.agents.state import AgentState


class BaseAgent(ABC):
    """Abstract base for all LangGraph-compatible agents.

    Subclasses implement run() which receives AgentState and returns
    a modified AgentState. The agent is provided with a DB session
    and Redis client at construction. SSE emission is set up via
    set_run_id() which creates an SSEPublisher.

    The _hitl_checkpoint helper sets the Redis pending key and emits
    a checkpoint SSE event — agents call this when they need human
    approval before proceeding.
    """

    def __init__(self, db: AsyncSession, redis: aioredis.Redis) -> None:
        self.db = db
        self.redis = redis
        self.emitter = None
        self._run_id: str | None = None

    async def set_run_id(self, run_id: str) -> None:
        self._run_id = run_id
        from app.services.sse_service import SSEPublisher
        self.emitter = SSEPublisher(run_id, self.redis)

    @abstractmethod
    async def run(self, state: AgentState) -> AgentState:
        ...

    async def _get_llm(self, user_id: str, task_type: str = "") -> BaseChatModel:
        from app.core.model_router import get_llm
        return await get_llm(user_id, self.db, task_type)

    async def _hitl_checkpoint(
        self, state: AgentState, action_type: str, details: dict
    ) -> AgentState:
        """Store HITL pending action in Redis, emit checkpoint SSE."""
        await self.redis.setex(
            f"agent:{state['run_id']}:pending", 600, action_type,
        )
        if self.emitter:
            await self.emitter.checkpoint(action_type, details)
        state["pending_action"] = {"type": action_type, "details": details}
        state["status"] = "awaiting_approval"
        return state
