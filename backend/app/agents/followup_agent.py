import logging
import uuid
from datetime import UTC, datetime, timedelta

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

# 30 days covers day-12 plus slack; long enough that a scheduled/executed
# marker never expires while the job it guards could still be pending.
_TRACKING_TTL_SECONDS = 30 * 24 * 60 * 60


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


async def _enqueue_followup(user_id: str, application_id: str, day: int, delay_ms: int) -> str:
    """Enqueue a follow-up email job with an explicit BullMQ delay in ms."""
    if not _BULLMQ_AVAILABLE:
        logger.warning("BullMQ not available — follow-up job not scheduled")
        return ""

    job_id = str(uuid.uuid4())

    try:
        queue = _BullQueue("agent-queue", {"connection": _bullmq_connection()})
        try:
            await queue.add(
                "followup-email",
                {
                    "user_id": user_id,
                    "application_id": application_id,
                    "day": day,
                },
                {
                    "jobId": job_id,
                    "delay": delay_ms,  # BullMQ handles delayed jobs correctly
                    "attempts": 3,
                    "backoff": {"type": "exponential", "delay": 5000},
                },
            )
            logger.debug(
                "Enqueued follow-up job %s (day %d) to fire in %dms", job_id, day, delay_ms
            )
        finally:
            await queue.close()
    except Exception as exc:
        logger.error("Failed to enqueue follow-up for application %s: %s", application_id, exc)
        return ""

    return job_id


async def schedule_followups(user_id: str, application_id: str, applied_at: datetime) -> None:
    """Schedule day-5 and day-12 follow-up emails, keyed off applied_at.

    Idempotent per (application_id, day): each day's tracking key is claimed
    atomically with SET NX before enqueuing, so a duplicate scheduling call —
    or a race between two concurrent callers — can never double-schedule the
    same day's job (the old exists-then-setex sequence could).
    """
    r = _get_redis()
    now = datetime.now(UTC)
    if applied_at is None:
        applied_at = now
    elif applied_at.tzinfo is None:
        applied_at = applied_at.replace(tzinfo=UTC)

    for day in (5, 12):
        tracking_key = f"followup:scheduled:{application_id}:day{day}"
        claimed = await r.set(tracking_key, "1", nx=True, ex=_TRACKING_TTL_SECONDS)
        if not claimed:
            logger.debug(
                "Follow-up day-%d already scheduled for application %s", day, application_id
            )
            continue

        delay_ms = max(0, int((applied_at + timedelta(days=day) - now).total_seconds() * 1000))
        job_id = await _enqueue_followup(user_id, application_id, day, delay_ms)
        if job_id:
            logger.info("Scheduled day-%d follow-up for application %s", day, application_id)
        else:
            # Enqueue failed — release the claim so a later retry isn't
            # blocked forever by a phantom "scheduled" marker.
            await r.delete(tracking_key)
            logger.warning(
                "Failed to schedule day-%d follow-up for application %s", day, application_id
            )


def _fallback_followup_draft(company: str, role: str, stage: str) -> dict:
    company_text = company or "the team"
    role_text = role or "the role"
    nudge = (
        "wanted to briefly follow up" if stage == "day5"
        else "wanted to check in one last time"
    )
    subject = f"Following up: {role_text} at {company_text}"
    body = (
        f"Hi,\n\nI {nudge} on my application for {role_text} at {company_text}. "
        "I remain very interested and would welcome any update on next steps.\n\n"
        "Thanks for your time,\n"
    )
    return {"subject": subject, "body": body}


def build_followup_draft(
    user_id: str, company: str, role: str, applied_at: datetime | None, day: int,
) -> dict:
    """Draft a day-5/day-12 follow-up email. DRAFT ONLY — the caller
    (internal.py::run_followup) must route this through a human approval
    checkpoint before anything is sent; this function never sends email.
    """
    stage = "day5" if day <= 5 else "day12"
    try:
        from app.agents._llm_json import call_llm_json
        from app.agents.prompts.followup_prompt import OUTPUT_SCHEMA as FollowupOutput
        from app.agents.prompts.followup_prompt import SYSTEM_PROMPT as FOLLOWUP_SYSTEM_PROMPT
        from app.agents.prompts.followup_prompt import build_user_prompt as build_followup_prompt
        from app.core.model_router import _build_llm
        from app.core.sync_db import fetch_model_settings

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("no active model settings for user")
        llm = _build_llm(model_settings)
        parsed = call_llm_json(
            llm,
            FOLLOWUP_SYSTEM_PROMPT,
            build_followup_prompt({
                "role": role or "NOT_PROVIDED",
                "company": company or "NOT_PROVIDED",
                "applied_on": applied_at.date().isoformat() if applied_at else "NOT_PROVIDED",
                "followup_stage": stage,
            }),
            FollowupOutput,
        )
        return {"subject": parsed.subject, "body": parsed.body}
    except Exception as exc:
        logger.warning("Follow-up draft LLM failed for user %s, using template: %s", user_id, exc)
        return _fallback_followup_draft(company, role, stage)
