import json
import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_AGENT_QUEUE_KEY = "bull:agent-queue:wait"
_SCHEDULED_SET_KEY = "followup:scheduled"

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


async def _enqueue_followup(user_id: str, application_id: str, delay_days: int) -> str:
    job_id = str(uuid.uuid4())
    fire_at = datetime.now(timezone.utc) + timedelta(days=delay_days)
    delay_ms = int((fire_at - datetime.now(timezone.utc)).total_seconds() * 1000)
    payload = {
        "id": job_id,
        "name": "followup-email",
        "data": {"user_id": user_id, "application_id": application_id, "day": delay_days},
        "opts": {"delay": delay_ms, "attempts": 3},
        "timestamp": int(time.time() * 1000),
    }
    r = _get_redis()
    await r.rpush(_AGENT_QUEUE_KEY, json.dumps(payload))
    return job_id


async def schedule_followups(user_id: str, application_id: str, applied_at: datetime) -> None:
    """Schedule day-5 and day-12 follow-up emails. Idempotent."""
    r = _get_redis()
    if await r.sismember(_SCHEDULED_SET_KEY, application_id):
        logger.debug("Follow-ups already scheduled for application %s", application_id)
        return

    await _enqueue_followup(user_id, application_id, delay_days=5)
    await _enqueue_followup(user_id, application_id, delay_days=12)
    await r.sadd(_SCHEDULED_SET_KEY, application_id)

    # Auto-expire the tracking set entry 30 days after application
    expire_ts = int((applied_at + timedelta(days=30)).timestamp())
    await r.expireat(_SCHEDULED_SET_KEY, expire_ts)

    logger.info("Scheduled day-5 and day-12 follow-ups for application %s", application_id)
