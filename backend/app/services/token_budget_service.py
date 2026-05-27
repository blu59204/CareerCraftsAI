"""
token_budget_service.py — Daily token usage limits per user.

Tracks tokens consumed via Redis counters with 24h TTL.
Raises TokenBudgetExceeded when user exceeds their daily limit.

Default: 500,000 tokens/day (adjustable per user tier).
"""
import logging
from datetime import date

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

DEFAULT_DAILY_LIMIT = 500_000  # tokens per user per day

_redis: aioredis.Redis | None = None


async def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL, encoding="utf-8", decode_responses=True
        )
    return _redis


def _budget_key(user_id: str) -> str:
    return f"token_budget:{user_id}:{date.today().isoformat()}"


class TokenBudgetExceeded(Exception):
    """Raised when a user exceeds their daily token budget."""

    def __init__(self, user_id: str, used: int, limit: int):
        self.user_id = user_id
        self.used = used
        self.limit = limit
        super().__init__(f"User {user_id} exceeded daily token limit: {used}/{limit}")


async def check_budget(user_id: str, limit: int = DEFAULT_DAILY_LIMIT) -> int:
    """Check remaining token budget. Returns tokens remaining."""
    r = await _get_redis()
    key = _budget_key(user_id)
    used = int(await r.get(key) or 0)
    return max(0, limit - used)


async def consume_tokens(user_id: str, tokens: int, limit: int = DEFAULT_DAILY_LIMIT) -> int:
    """Record token consumption. Raises TokenBudgetExceeded if over limit.

    Returns new total used today.
    """
    r = await _get_redis()
    key = _budget_key(user_id)

    # Atomic increment
    new_total = await r.incrby(key, tokens)

    # Set TTL on first use (expire at end of day — 24h max)
    if new_total == tokens:
        await r.expire(key, 86400)

    if new_total > limit:
        raise TokenBudgetExceeded(user_id, new_total, limit)

    return new_total


async def get_usage(user_id: str) -> dict:
    """Get current usage stats for a user."""
    r = await _get_redis()
    key = _budget_key(user_id)
    used = int(await r.get(key) or 0)
    return {
        "user_id": user_id,
        "tokens_used_today": used,
        "daily_limit": DEFAULT_DAILY_LIMIT,
        "remaining": max(0, DEFAULT_DAILY_LIMIT - used),
        "date": date.today().isoformat(),
    }
