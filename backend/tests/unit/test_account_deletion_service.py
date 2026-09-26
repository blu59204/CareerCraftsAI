from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.models.db import User
from app.services.account_deletion_service import reap_expired_account_deletions


def _make_user(*, scheduled_for, clerk_user_id="user_abc"):
    return User(
        id=uuid4(),
        email=f"{uuid4()}@example.com",
        clerk_user_id=clerk_user_id,
        deletion_requested_at=scheduled_for - timedelta(days=15) if scheduled_for else None,
        deletion_scheduled_for=scheduled_for,
    )


def _db_returning(users):
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    db.execute = AsyncMock(return_value=result)
    db.delete = AsyncMock()
    db.flush = AsyncMock()
    return db


@pytest.mark.asyncio
async def test_reaps_users_past_their_grace_period():
    expired_user = _make_user(scheduled_for=datetime.now(UTC) - timedelta(days=1))
    db = _db_returning([expired_user])

    with patch(
        "app.core.clerk_auth.delete_clerk_user", AsyncMock(return_value=None)
    ) as mock_delete_clerk:
        removed = await reap_expired_account_deletions(db)

    assert removed == 1
    db.delete.assert_awaited_once_with(expired_user)
    mock_delete_clerk.assert_awaited_once_with("user_abc")


@pytest.mark.asyncio
async def test_continues_reaping_even_if_clerk_deletion_fails():
    expired_user = _make_user(scheduled_for=datetime.now(UTC) - timedelta(days=1))
    db = _db_returning([expired_user])

    with patch(
        "app.core.clerk_auth.delete_clerk_user",
        AsyncMock(side_effect=RuntimeError("Clerk is down")),
    ):
        removed = await reap_expired_account_deletions(db)

    assert removed == 1
    db.delete.assert_awaited_once_with(expired_user)


@pytest.mark.asyncio
async def test_returns_zero_when_nothing_is_due():
    db = _db_returning([])

    removed = await reap_expired_account_deletions(db)

    assert removed == 0
    db.delete.assert_not_called()
