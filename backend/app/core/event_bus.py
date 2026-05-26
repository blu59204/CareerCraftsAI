"""
event_bus.py — Redis Pub/Sub backed SSE event bus.

Replaces the in-memory asyncio.Queue approach which breaks under
multi-worker (Gunicorn) deployments: POST /agents/run and
GET /{run_id}/stream may land on different processes.

Redis channels are keyed by run_id so each stream subscriber only
receives events for its own run.
"""
import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis


def _channel(run_id: str) -> str:
    return f"sse:{run_id}"


def emit(run_id: str, event_type: str, data: str | dict) -> None:
    """Publish an event to the Redis channel for run_id (sync-safe via asyncio.run)."""
    payload = data if isinstance(data, str) else json.dumps(data)
    message = json.dumps({"type": event_type, "data": payload, "ts": int(time.time())})

    async def _pub() -> None:
        r = _get_redis()
        await r.publish(_channel(run_id), message)

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_pub())
    except RuntimeError:
        # Called from a sync thread (agent node) — spin up a new loop
        asyncio.run(_pub())


async def stream_events(run_id: str) -> AsyncIterator[str]:
    """Async generator that yields SSE-formatted strings from Redis Pub/Sub."""
    r = _get_redis()
    pubsub = r.pubsub()
    await pubsub.subscribe(_channel(run_id))
    try:
        while True:
            try:
                msg = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=30.0)
            except TimeoutError:
                yield 'data: {"type":"ping"}\n\n'
                continue

            if msg is None:
                await asyncio.sleep(0.05)
                continue

            raw = msg.get("data", "")
            yield f"data: {raw}\n\n"

            try:
                event = json.loads(raw)
                if event.get("type") in ("complete", "error"):
                    break
            except (json.JSONDecodeError, AttributeError):
                pass
    finally:
        await pubsub.unsubscribe(_channel(run_id))
        await pubsub.close()


# Keep get_queue/remove_queue stubs so existing callers in agents.py don't break
# (agents.py calls get_queue to pre-create the queue before the background task starts)
def get_queue(run_id: str) -> None:  # noqa: ARG001
    """No-op: Redis channels are created on first publish."""


def remove_queue(run_id: str) -> None:  # noqa: ARG001
    """No-op: Redis channels are ephemeral."""
