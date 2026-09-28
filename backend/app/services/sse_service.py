from __future__ import annotations

import json
import logging
import time

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

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


