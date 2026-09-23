from __future__ import annotations

import json
import logging
import time
from collections.abc import AsyncGenerator
from typing import Any, Literal

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

EventType = Literal["thinking", "tool_call", "tool_result", "checkpoint", "complete", "error"]
SSE_TIMEOUT_SECONDS = 300


class SSEPublisher:
    """Publishes typed SSE events to Redis pub/sub for a specific agent run.

    Usage:
        pub = SSEPublisher(run_id, redis_client)
        await pub.thinking(1, "Retrieving context...")
        await pub.checkpoint("send_email", {"subject": "...", "body": "..."})
        await pub.complete({"matches": [...]}, tokens_used=1200, duration_ms=4500)
        await pub.error("LLM unavailable")
    """

    def __init__(self, run_id: str, redis: aioredis.Redis) -> None:
        self._run_id = run_id
        self._redis = redis
        self._channel = f"agent:{run_id}:events"

    async def _publish(self, event_type: str, payload: dict) -> None:
        try:
            envelope = json.dumps({"type": event_type, "data": payload, "ts": int(time.time())})
            await self._redis.publish(self._channel, envelope)
        except Exception as exc:
            logger.warning("SSE publish failed for run %s: %s", self._run_id, exc)

    async def thinking(self, step: int, message: str) -> None:
        await self._publish("thinking", {"step": step, "message": message})

    async def tool_call(self, tool: str, input: dict) -> None:
        await self._publish("tool_call", {"tool": tool, "input": input})

    async def tool_result(self, tool: str, output: dict) -> None:
        await self._publish("tool_result", {"tool": tool, "output": output})

    async def checkpoint(self, action_type: str, details: dict) -> None:
        await self._redis.setex(f"agent:{self._run_id}:pending", 600, action_type)
        await self._publish("checkpoint", {"action_type": action_type, "details": details})

    async def complete(self, result: dict, tokens_used: int, duration_ms: int) -> None:
        await self._publish("complete", {
            "result": result, "tokens_used": tokens_used, "duration_ms": duration_ms,
        })

    async def error(self, message: str) -> None:
        await self._publish("error", {"message": message})


async def subscribe_to_run(run_id: str, redis: aioredis.Redis) -> AsyncGenerator[str, None]:
    """Subscribe to Redis pub/sub and yield SSE-formatted event strings.

    Yields:  event: {type}\ndata: {json}\n\n
    Timeout: 300s with error event on expiry.
    """
    channel = f"agent:{run_id}:events"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    start = time.time()
    try:
        while True:
            if (time.time() - start) > SSE_TIMEOUT_SECONDS:
                yield 'event: error\ndata: {"message":"Agent timed out after 5 minutes"}\n\n'
                return

            try:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=5.0)
            except Exception:
                msg = None

            if msg is None:
                yield 'event: ping\ndata: {"type":"ping"}\n\n'
                continue

            raw = msg.get("data", "")
            if not raw:
                continue

            try:
                envelope = json.loads(raw)
                event_type = envelope.get("type", "message")
                data = envelope.get("data", {})
            except Exception:
                event_type = "message"
                data = raw

            yield f"event: {event_type}\ndata: {json.dumps(data, default=str)}\n\n"

            if event_type in ("complete", "error"):
                return
    finally:
        try:
            await pubsub.unsubscribe(channel)
        except Exception:
            pass
        try:
            await pubsub.aclose()
        except Exception:
            pass
