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

    with patch("app.services.account_deletion_service.erase_external_data", AsyncMock()) as erase:
        removed = await reap_expired_account_deletions(db)

    assert removed == 1
    erase.assert_awaited_once_with(expired_user)
    db.delete.assert_awaited_once_with(expired_user)


@pytest.mark.asyncio
async def test_keeps_the_account_for_the_next_sweep_when_erasure_fails():
    expired_user = _make_user(scheduled_for=datetime.now(UTC) - timedelta(days=1))
    db = _db_returning([expired_user])

    with patch(
        "app.services.account_deletion_service.erase_external_data",
        AsyncMock(side_effect=RuntimeError("Clerk is down")),
    ):
        removed = await reap_expired_account_deletions(db)

    assert removed == 0
    db.delete.assert_not_called()


@pytest.mark.asyncio
async def test_erasure_stops_before_clerk_when_an_earlier_step_fails(monkeypatch):
    from app.services import account_deletion_service as service

    user = _make_user(scheduled_for=datetime.now(UTC))
    calls = []
    monkeypatch.setattr(service, "_terminate_workflows", AsyncMock(side_effect=calls.append))
    monkeypatch.setattr(
        service, "_revoke_integrations", AsyncMock(side_effect=RuntimeError("Nango down"))
    )
    clerk = AsyncMock()
    monkeypatch.setattr("app.core.clerk_auth.delete_clerk_user", clerk)

    with pytest.raises(RuntimeError, match="Nango down"):
        await service.erase_external_data(user)

    assert calls == [user.id]
    clerk.assert_not_called()


@pytest.mark.asyncio
async def test_strict_clerk_deletion_raises_but_a_missing_user_counts_as_deleted(monkeypatch):
    import httpx

    from app.core import clerk_auth

    monkeypatch.setattr(clerk_auth.settings, "CLERK_SECRET_KEY", "sk_test")
    statuses = iter([404, 500])
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(next(statuses)))
    )

    await clerk_auth.delete_clerk_user("user_1", client=client, strict=True)
    with pytest.raises(RuntimeError, match="500"):
        await clerk_auth.delete_clerk_user("user_1", client=client, strict=True)
    await client.aclose()


@pytest.mark.asyncio
async def test_returns_zero_when_nothing_is_due():
    db = _db_returning([])

    removed = await reap_expired_account_deletions(db)

    assert removed == 0
    db.delete.assert_not_called()
