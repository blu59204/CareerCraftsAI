import asyncio
import json
import logging
import time
from collections.abc import AsyncIterator

logger = logging.getLogger(__name__)

_queues: dict[str, asyncio.Queue] = {}


def get_queue(run_id: str) -> asyncio.Queue:
    if run_id not in _queues:
        _queues[run_id] = asyncio.Queue(maxsize=100)
    return _queues[run_id]


def remove_queue(run_id: str) -> None:
    _queues.pop(run_id, None)


def emit(run_id: str, event_type: str, data: str | dict) -> None:
    """Emit from sync agent thread to async SSE stream."""
    q = _queues.get(run_id)
    if q is None:
        return
    payload = data if isinstance(data, str) else json.dumps(data)
    try:
        q.put_nowait({"type": event_type, "data": payload, "ts": int(time.time())})
    except asyncio.QueueFull:
        logger.warning("SSE queue full for run %s, dropping event %s", run_id, event_type)


async def stream_events(run_id: str) -> AsyncIterator[str]:
    """Async generator that yields SSE-formatted strings."""
    q = get_queue(run_id)
    try:
        while True:
            try:
                event = await asyncio.wait_for(q.get(), timeout=30.0)
                yield f"data: {json.dumps(event)}\n\n"
                if event["type"] in ("complete", "error"):
                    break
            except TimeoutError:
                yield "data: {\"type\":\"ping\"}\n\n"
    finally:
        remove_queue(run_id)
