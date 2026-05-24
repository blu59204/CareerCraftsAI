import logging
import uuid
from urllib.parse import urlparse

from bullmq import Queue

from app.core.config import settings

logger = logging.getLogger(__name__)


def _bullmq_connection() -> dict:
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


async def enqueue_job_search(
    user_id: str,
    run_id: str,
    search_query: str,
    location: str,
    max_results: int,
) -> str:
    job_id = str(uuid.uuid4())
    queue = Queue("agent-queue", connection=_bullmq_connection())
    try:
        await queue.add(
            "job-search",
            {
                "user_id": user_id,
                "run_id": run_id,
                "search_query": search_query,
                "location": location,
                "max_results": max_results,
            },
            {
                "jobId": job_id,
                "attempts": 3,
                "backoff": {"type": "exponential", "delay": 5000},
            },
        )
    except Exception as exc:
        logger.error("Failed to enqueue job-search for run %s: %s", run_id, exc)
        raise RuntimeError(f"Queue unavailable: {exc}") from exc
    finally:
        await queue.close()
    return job_id
