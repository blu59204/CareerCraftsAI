"""A placeholder email that Clerk cannot repair is retried hourly, not per request."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core import clerk_auth
from app.models.db import User


class _FakeRedis:
    def __init__(self):
        self.keys = {}

    async def exists(self, key):
        return int(key in self.keys)

    async def set(self, key, value, ex=None):
        self.keys[key] = (value, ex)


@pytest.mark.asyncio
async def test_failed_repair_is_not_retried_until_the_backoff_expires(monkeypatch):
    redis = _FakeRedis()
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: redis)
    fetch = AsyncMock(return_value=None)  # Clerk has no verified email
    monkeypatch.setattr(clerk_auth, "fetch_clerk_profile", fetch)
    user = User(
        id=uuid.uuid4(),
        email=f"user_1{clerk_auth.PLACEHOLDER_EMAIL_DOMAIN}",
        clerk_user_id="user_1",
    )

    await clerk_auth._repair_placeholder_profile(MagicMock(), user)
    await clerk_auth._repair_placeholder_profile(MagicMock(), user)

    fetch.assert_awaited_once()
    assert redis.keys[f"clerk_profile_repair:{user.id}"][1] == clerk_auth._REPAIR_RETRY_SECONDS
