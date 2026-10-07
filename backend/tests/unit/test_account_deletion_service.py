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
        deletion_requested_at=(scheduled_for - timedelta(days=15) if scheduled_for else None),
        deletion_scheduled_for=scheduled_for,
    )


def _db_returning(users):
    db = AsyncMock()
    result = MagicMock()
    result.scalars.return_value.all.return_value = users
    result.first.return_value = None
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
    db.delete.assert_not_awaited()
    final_delete = db.execute.await_args.args[0]
    assert str(final_delete).startswith("DELETE FROM users")
    assert expired_user.id in final_delete.compile().params.values()


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
        service,
        "_revoke_integrations",
        AsyncMock(side_effect=RuntimeError("Nango down")),
    )
    clerk = AsyncMock()
    monkeypatch.setattr("app.core.clerk_auth.delete_clerk_user", clerk)

    with pytest.raises(RuntimeError, match="Nango down"):
        await service.erase_external_data(user)

    assert calls == [user.id]
    clerk.assert_not_called()


@pytest.mark.asyncio
async def test_strict_clerk_deletion_raises_but_a_missing_user_counts_as_deleted(
    monkeypatch,
):
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


@pytest.mark.asyncio
async def test_failed_computer_purge_blocks_identity_erasure(monkeypatch):
    from app.services import account_deletion_service as service

    user = _make_user(scheduled_for=datetime.now(UTC))
    monkeypatch.setattr(service, "_terminate_workflows", AsyncMock())
    monkeypatch.setattr(service, "_revoke_integrations", AsyncMock())
    purge = AsyncMock(side_effect=RuntimeError("Volume is busy"))
    monkeypatch.setattr("app.services.computer_service.purge_user", purge)
    clerk = AsyncMock()
    monkeypatch.setattr("app.core.clerk_auth.delete_clerk_user", clerk)
    files = MagicMock()
    monkeypatch.setattr(service, "_delete_files", files)
    with pytest.raises(RuntimeError, match="busy"):
        await service.erase_external_data(user)
    purge.assert_awaited_once_with(user.id)
    files.assert_not_called()
    clerk.assert_not_called()


@pytest.mark.asyncio
async def test_redis_erasure_includes_memory_and_only_owned_gateway_sessions(
    monkeypatch,
):
    import json

    from app.services.account_deletion_service import _delete_redis_keys

    owner, other = uuid4(), uuid4()
    redis = AsyncMock()
    patterns = []

    async def scan(*, match, count):
        patterns.append(match)
        if match == "llm_gw:session:*":
            yield "llm_gw:session:owned"
            yield "llm_gw:session:foreign"
        if match == f"session:{owner}:*":
            yield f"session:{owner}:role"

    redis.scan_iter = scan
    redis.get.side_effect = [
        json.dumps({"user_id": str(owner)}),
        json.dumps({"user_id": str(other)}),
    ]
    monkeypatch.setattr("app.core.redis_client.get_redis", lambda: redis)
    await _delete_redis_keys(owner)
    deleted = [args.args for args in redis.delete.await_args_list]
    assert ("llm_gw:session:owned",) in deleted
    assert ("llm_gw:session:foreign",) not in deleted
    assert (f"session:{owner}:role",) in deleted


@pytest.mark.asyncio
async def test_erasure_waits_for_live_request_owned_work_before_cleanup():
    user = _make_user(scheduled_for=datetime.now(UTC) - timedelta(minutes=1))
    db = _db_returning([user])
    db.execute.return_value.first.return_value = (uuid4(),)
    with patch("app.services.account_deletion_service.erase_external_data", AsyncMock()) as erase:
        assert await reap_expired_account_deletions(db) == 0
    erase.assert_not_awaited()
    db.delete.assert_not_awaited()
    query = db.execute.await_args.args[0]
    assert "sending_at" in str(query)


@pytest.mark.asyncio
async def test_account_erasure_removes_its_no_fk_document_cleanup_metadata(monkeypatch):
    from app.services.account_deletion_service import _delete_unlinked_rows

    owner = uuid4()
    db = AsyncMock()
    statements = []

    async def execute(query, params=None):
        sql = str(query)
        statements.append((sql, params))
        result = MagicMock()
        result.scalar.return_value = (
            "document_cleanup_queue" if "document_cleanup_queue" in sql else None
        )
        return result

    db.execute.side_effect = execute
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=db)
    context.__aexit__ = AsyncMock(return_value=False)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: context)
    await _delete_unlinked_rows(owner)
    assert (
        "DELETE FROM public.document_cleanup_queue WHERE user_id = :uid",
        {"uid": owner},
    ) in statements
    db.commit.assert_awaited_once()
