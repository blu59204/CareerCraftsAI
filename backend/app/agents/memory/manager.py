"""
memory.manager — MemoryManager for episodic memory, preference storage, and
                  agent learnings backed by PostgreSQL + Redis.

Tables expected (created lazily on first use):
  - agent_episodes     (id, user_id, agent_type, task_type, strategy, success,
                        context_summary, output_summary, created_at)
  - agent_learnings    (id, user_id, agent_type, learning, success_rate,
                        sample_count, created_at, updated_at)
  - user_preferences   (id, user_id, preference_key, preference_value, created_at)

If the tables do not exist the manager logs a warning and returns safe empty
values — it never raises so the harness can degrade gracefully.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg

logger = logging.getLogger(__name__)

# DDL executed once per connection pool lifetime
_DDL = """
CREATE TABLE IF NOT EXISTS agent_episodes (
    id            BIGSERIAL PRIMARY KEY,
    user_id       TEXT        NOT NULL,
    agent_type    TEXT        NOT NULL,
    task_type     TEXT        NOT NULL,
    strategy      TEXT        NOT NULL DEFAULT 'standard',
    success       BOOLEAN     NOT NULL DEFAULT FALSE,
    context_summary TEXT,
    output_summary  TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_episodes_user_agent
    ON agent_episodes (user_id, agent_type, created_at DESC);

CREATE TABLE IF NOT EXISTS agent_learnings (
    id           BIGSERIAL PRIMARY KEY,
    user_id      TEXT        NOT NULL,
    agent_type   TEXT        NOT NULL,
    learning     TEXT        NOT NULL,
    success_rate FLOAT       NOT NULL DEFAULT 0.0,
    sample_count INT         NOT NULL DEFAULT 0,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, agent_type, learning)
);
CREATE INDEX IF NOT EXISTS idx_learnings_user_agent
    ON agent_learnings (user_id, agent_type, success_rate DESC);

CREATE TABLE IF NOT EXISTS user_preferences (
    id               BIGSERIAL PRIMARY KEY,
    user_id          TEXT NOT NULL,
    preference_key   TEXT NOT NULL,
    preference_value TEXT,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, preference_key)
);
CREATE INDEX IF NOT EXISTS idx_prefs_user ON user_preferences (user_id);
"""


class MemoryManager:
    """
    Manages episodic memory, learnings, and preferences for an agent harness.

    Usage::

        mgr = MemoryManager(db_url="postgresql://...", redis_url="redis://...")
        await mgr.initialize()           # creates tables, warms caches
        ctx = await mgr.build_agent_context(user_id, task_type)
        await mgr.save_episode(...)
        await mgr.close()
    """

    def __init__(self, db_url: str, redis_url: str) -> None:
        # Convert SQLAlchemy URL to asyncpg-compatible URL
        self._db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        self._redis_url = redis_url
        self._pool: asyncpg.Pool | None = None
        self._redis: Any | None = None          # redis.asyncio.Redis
        self._tables_ready: bool = False
        self._tables_checked: bool = False      # log once only

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        """Create the connection pool and ensure memory tables exist."""
        try:
            self._pool = await asyncpg.create_pool(
                self._db_url,
                min_size=1,
                max_size=5,
                command_timeout=10,
            )
            await self._ensure_tables()
        except Exception as exc:
            logger.warning("MemoryManager: DB pool init failed — memory disabled: %s", exc)
            self._pool = None

        try:
            import redis.asyncio as aioredis  # type: ignore[import]

            self._redis = aioredis.from_url(
                self._redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
        except Exception as exc:
            logger.warning("MemoryManager: Redis init failed — caching disabled: %s", exc)
            self._redis = None

    async def close(self) -> None:
        if self._pool:
            await self._pool.close()
        if self._redis:
            await self._redis.aclose()

    # ------------------------------------------------------------------
    # Table bootstrap
    # ------------------------------------------------------------------

    async def _ensure_tables(self) -> None:
        if self._tables_checked:
            return
        self._tables_checked = True
        if not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(_DDL)
            self._tables_ready = True
            logger.debug("MemoryManager: memory tables verified/created")
        except Exception as exc:
            logger.warning(
                "MemoryManager: could not create memory tables — %s. "
                "Memory features will be skipped for this session.",
                exc,
            )
            self._tables_ready = False

    # ------------------------------------------------------------------
    # Context building
    # ------------------------------------------------------------------

    async def build_agent_context(
        self,
        user_id: str,
        task_type: str,
        agent_type: str,
        max_episodes: int = 5,
    ) -> dict[str, Any]:
        """
        Returns a context dict with:
          - preferences:  {key: value} from user_preferences
          - learnings:    list[str] of top learnings sorted by success_rate
          - past_episodes: list[dict] summarising recent episodes
          - blacklist:    list[str] of strategies with success_rate < 0.2
        """
        empty: dict[str, Any] = {
            "preferences": {},
            "learnings": [],
            "past_episodes": [],
            "blacklist": [],
        }
        if not self._tables_ready or not self._pool:
            return empty

        try:
            async with self._pool.acquire() as conn:
                # Preferences
                prefs_rows = await conn.fetch(
                    "SELECT preference_key, preference_value "
                    "FROM user_preferences WHERE user_id = $1",
                    user_id,
                )
                preferences = {r["preference_key"]: r["preference_value"] for r in prefs_rows}

                # Learnings
                learning_rows = await conn.fetch(
                    "SELECT learning, success_rate FROM agent_learnings "
                    "WHERE user_id = $1 AND agent_type = $2 "
                    "ORDER BY success_rate DESC LIMIT 20",
                    user_id,
                    agent_type,
                )
                learnings = [r["learning"] for r in learning_rows if r["success_rate"] >= 0.2]
                blacklist = [r["learning"] for r in learning_rows if r["success_rate"] < 0.2]

                # Past episodes
                ep_rows = await conn.fetch(
                    "SELECT task_type, strategy, success, output_summary, created_at "
                    "FROM agent_episodes "
                    "WHERE user_id = $1 AND agent_type = $2 "
                    "ORDER BY created_at DESC LIMIT $3",
                    user_id,
                    agent_type,
                    max_episodes,
                )
                past_episodes = [
                    {
                        "task_type": r["task_type"],
                        "strategy": r["strategy"],
                        "success": r["success"],
                        "summary": r["output_summary"] or "",
                        "when": r["created_at"].isoformat() if r["created_at"] else "",
                    }
                    for r in ep_rows
                ]

            return {
                "preferences": preferences,
                "learnings": learnings,
                "past_episodes": past_episodes,
                "blacklist": blacklist,
            }
        except Exception as exc:
            logger.warning("MemoryManager.build_agent_context failed: %s", exc)
            return empty

    # ------------------------------------------------------------------
    # Episode saving
    # ------------------------------------------------------------------

    async def save_episode(
        self,
        user_id: str,
        agent_type: str,
        task_type: str,
        strategy: str,
        success: bool,
        context_summary: str = "",
        output_summary: str = "",
    ) -> None:
        """Persist a completed episode."""
        if not self._tables_ready or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                await conn.execute(
                    """
                    INSERT INTO agent_episodes
                        (user_id, agent_type, task_type, strategy,
                         success, context_summary, output_summary)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                    """,
                    user_id,
                    agent_type,
                    task_type,
                    strategy,
                    success,
                    context_summary[:2000] if context_summary else "",
                    output_summary[:2000] if output_summary else "",
                )
        except Exception as exc:
            logger.warning("MemoryManager.save_episode failed: %s", exc)

    # ------------------------------------------------------------------
    # Learning upsert
    # ------------------------------------------------------------------

    async def upsert_learning(
        self,
        user_id: str,
        agent_type: str,
        learning: str,
        success: bool,
    ) -> None:
        """Increment success/failure count for a strategy learning entry."""
        if not self._tables_ready or not self._pool:
            return
        try:
            async with self._pool.acquire() as conn:
                # Upsert: create or increment counters
                await conn.execute(
                    """
                    INSERT INTO agent_learnings
                        (user_id, agent_type, learning, success_rate, sample_count, updated_at)
                    VALUES ($1, $2, $3, $4, 1, NOW())
                    ON CONFLICT (user_id, agent_type, learning) DO UPDATE SET
                        sample_count = agent_learnings.sample_count + 1,
                        success_rate = (
                            agent_learnings.success_rate * agent_learnings.sample_count
                            + $4
                        ) / (agent_learnings.sample_count + 1),
                        updated_at = NOW()
                    """,
                    user_id,
                    agent_type,
                    learning,
                    1.0 if success else 0.0,
                )
        except Exception as exc:
            logger.warning("MemoryManager.upsert_learning failed: %s", exc)

    # ------------------------------------------------------------------
    # Bulk learning save (from reflection)
    # ------------------------------------------------------------------

    async def save_learnings(
        self,
        user_id: str,
        agent_type: str,
        learnings: list[dict[str, Any]],
    ) -> None:
        """
        Bulk-save reflection-derived learnings.

        Each item: {"learning": str, "success_rate": float, "sample_count": int}
        """
        if not self._tables_ready or not self._pool:
            return
        for item in learnings:
            try:
                async with self._pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO agent_learnings
                            (user_id, agent_type, learning,
                             success_rate, sample_count, updated_at)
                        VALUES ($1, $2, $3, $4, $5, NOW())
                        ON CONFLICT (user_id, agent_type, learning) DO UPDATE SET
                            success_rate = EXCLUDED.success_rate,
                            sample_count = EXCLUDED.sample_count,
                            updated_at   = NOW()
                        """,
                        user_id,
                        agent_type,
                        item.get("learning", ""),
                        float(item.get("success_rate", 0.0)),
                        int(item.get("sample_count", 0)),
                    )
            except Exception as exc:
                logger.warning("MemoryManager.save_learnings item failed: %s", exc)

    # ------------------------------------------------------------------
    # Redis helpers
    # ------------------------------------------------------------------

    async def redis_get(self, key: str) -> str | None:
        if not self._redis:
            return None
        try:
            return await self._redis.get(key)
        except Exception as exc:
            logger.debug("Redis GET %s failed: %s", key, exc)
            return None

    async def redis_set(self, key: str, value: str, ttl_seconds: int = 86400) -> None:
        if not self._redis:
            return
        try:
            await self._redis.set(key, value, ex=ttl_seconds)
        except Exception as exc:
            logger.debug("Redis SET %s failed: %s", key, exc)

    # ------------------------------------------------------------------
    # Episode count since timestamp (for reflection gating)
    # ------------------------------------------------------------------

    async def episode_count_since(
        self,
        agent_type: str,
        since: datetime,
        user_id: str | None = None,
    ) -> int:
        """Count episodes for agent_type after *since* (optionally per-user)."""
        if not self._tables_ready or not self._pool:
            return 0
        try:
            async with self._pool.acquire() as conn:
                if user_id:
                    row = await conn.fetchrow(
                        "SELECT COUNT(*) AS cnt FROM agent_episodes "
                        "WHERE agent_type = $1 AND user_id = $2 AND created_at > $3",
                        agent_type,
                        user_id,
                        since,
                    )
                else:
                    row = await conn.fetchrow(
                        "SELECT COUNT(*) AS cnt FROM agent_episodes "
                        "WHERE agent_type = $1 AND created_at > $2",
                        agent_type,
                        since,
                    )
                return int(row["cnt"]) if row else 0
        except Exception as exc:
            logger.warning("MemoryManager.episode_count_since failed: %s", exc)
            return 0

    # ------------------------------------------------------------------
    # Recent episodes for reflection
    # ------------------------------------------------------------------

    async def recent_episodes(
        self,
        agent_type: str,
        limit: int = 50,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        if not self._tables_ready or not self._pool:
            return []
        try:
            async with self._pool.acquire() as conn:
                if user_id:
                    rows = await conn.fetch(
                        "SELECT user_id, task_type, strategy, success, "
                        "context_summary, output_summary, created_at "
                        "FROM agent_episodes "
                        "WHERE agent_type = $1 AND user_id = $2 "
                        "ORDER BY created_at DESC LIMIT $3",
                        agent_type,
                        user_id,
                        limit,
                    )
                else:
                    rows = await conn.fetch(
                        "SELECT user_id, task_type, strategy, success, "
                        "context_summary, output_summary, created_at "
                        "FROM agent_episodes "
                        "WHERE agent_type = $1 "
                        "ORDER BY created_at DESC LIMIT $2",
                        agent_type,
                        limit,
                    )
                return [dict(r) for r in rows]
        except Exception as exc:
            logger.warning("MemoryManager.recent_episodes failed: %s", exc)
            return []
