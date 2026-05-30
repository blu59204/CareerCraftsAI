import logging
import uuid
from datetime import datetime

import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from bullmq import Queue as _BullQueue
    _BULLMQ_AVAILABLE = True
except ImportError:
    _BULLMQ_AVAILABLE = False
    logger.warning("bullmq not installed — follow-up scheduling disabled")

_redis_client: aioredis.Redis | None = None


def _get_redis() -> aioredis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    return _redis_client


def _bullmq_connection() -> dict:
    from urllib.parse import urlparse
    parsed = urlparse(settings.REDIS_URL)
    opts: dict = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 6379,
    }
    if parsed.password:
        opts["password"] = parsed.password
    if parsed.path and parsed.path not in ("", "/"):
        opts["db"] = int(parsed.path.lstrip("/"))
    return opts


async def _enqueue_followup(user_id: str, application_id: str, delay_days: int) -> str:
    """Enqueue a follow-up email job with proper BullMQ delay."""
    if not _BULLMQ_AVAILABLE:
        logger.warning("BullMQ not available — follow-up job not scheduled")
        return ""

    job_id = str(uuid.uuid4())
    delay_ms = delay_days * 24 * 60 * 60 * 1000  # days to milliseconds

    try:
        queue = _BullQueue("agent-queue", {"connection": _bullmq_connection()})
        try:
            await queue.add(
                "followup-email",
                {
                    "user_id": user_id,
                    "application_id": application_id,
                    "day": delay_days,
                },
                {
                    "jobId": job_id,
                    "delay": delay_ms,  # BullMQ handles delayed jobs correctly
                    "attempts": 3,
                    "backoff": {"type": "exponential", "delay": 5000},
                },
            )
            logger.debug(f"Enqueued follow-up job {job_id} to fire in {delay_days} days")
        finally:
            await queue.close()
    except Exception as exc:
        logger.error("Failed to enqueue follow-up for application %s: %s", application_id, exc)
        return ""

    return job_id


async def schedule_followups(user_id: str, application_id: str, applied_at: datetime) -> None:
    """Schedule day-5 and day-12 follow-up emails. Idempotent.

    Uses per-application Redis key with TTL instead of a global set to avoid
    expiry conflicts between applications.
    """
    r = _get_redis()
    # Use per-application key for idempotency tracking
    tracking_key = f"followup:scheduled:{application_id}"

    # Check if already scheduled
    if await r.exists(tracking_key):
        logger.debug("Follow-ups already scheduled for application %s", application_id)
        return

    # Schedule both follow-ups
    job_id_5 = await _enqueue_followup(user_id, application_id, delay_days=5)
    job_id_12 = await _enqueue_followup(user_id, application_id, delay_days=12)

    if job_id_5 or job_id_12:
        # Mark as scheduled with 30-day TTL (per application, not global)
        await r.setex(tracking_key, 30 * 24 * 60 * 60, "1")
        logger.info("Scheduled day-5 and day-12 follow-ups for application %s", application_id)
    else:
        logger.warning("Failed to schedule follow-ups for application %s", application_id)
