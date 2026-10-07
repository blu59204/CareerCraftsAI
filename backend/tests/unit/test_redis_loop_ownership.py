import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.core.redis_client import close_redis, get_redis
from app.core.sync_db import run_coro_sync


def test_pool_is_reused_only_on_its_own_loop_and_closed_by_sync_runner():
    pools = []

    def create_pool(*args, **kwargs):
        pool = MagicMock(connection_kwargs={"protocol": 2}, disconnect=AsyncMock())
        pools.append(pool)
        return pool

    async def use_pool():
        first = get_redis().connection_pool
        assert first is get_redis().connection_pool
        return first

    with patch("app.core.redis_client.aioredis.ConnectionPool.from_url", side_effect=create_pool):
        first = run_coro_sync(use_pool())
        second = run_coro_sync(use_pool())
    assert first is not second
    assert len(pools) == 2
    for pool in pools:
        pool.disconnect.assert_awaited_once()


def test_gateway_and_budget_share_current_loop_pool():
    from app.core.llm_gateway import _get_redis as gateway_redis
    from app.services.token_budget_service import _get_redis as budget_redis

    async def check():
        pool = MagicMock(connection_kwargs={"protocol": 2}, disconnect=AsyncMock())
        with patch("app.core.redis_client.aioredis.ConnectionPool.from_url", return_value=pool):
            budget = await budget_redis()
            assert budget.connection_pool is gateway_redis().connection_pool
            await close_redis()
            assert not hasattr(asyncio.get_running_loop(), "_careercraft_redis_pool")

    asyncio.run(check())
