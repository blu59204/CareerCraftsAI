import json
import logging
import time
import uuid

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

AGENT_QUEUE_KEY = "bull:agent-queue:wait"

_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def enqueue_job_search(
    user_id: str,
    run_id: str,
    search_query: str,
    location: str,
    max_results: int,
) -> str:
    job_id = str(uuid.uuid4())
    payload = {
        "id": job_id,
        "name": "job-search",
        "data": {
            "user_id": user_id,
            "run_id": run_id,
            "search_query": search_query,
            "location": location,
            "max_results": max_results,
        },
        "opts": {"attempts": 3, "backoff": {"type": "exponential", "delay": 5000}},
        "timestamp": int(time.time() * 1000),
    }
    try:
        _get_redis().rpush(AGENT_QUEUE_KEY, json.dumps(payload))
    except Exception as exc:
        logger.error("Failed to enqueue job-search for run %s: %s", run_id, exc)
        raise RuntimeError(f"Queue unavailable: {exc}") from exc
    return job_id
