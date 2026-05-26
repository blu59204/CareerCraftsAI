import asyncio
import logging
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)

try:
    from bullmq import Queue as _BullQueue
    _BULLMQ_AVAILABLE = True
except ImportError:
    _BULLMQ_AVAILABLE = False
    logger.warning("bullmq not installed — job-search queue disabled")


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


async def _run_job_search_inline(
    user_id: str,
    run_id: str,
    search_query: str,
    location: str,
    max_results: int,
) -> None:
    """Dev fallback: run job search agent directly without BullMQ."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.agents.harness import AgentHarness
        from app.models.db import AgentRun, UserModelSettings
        from sqlalchemy import select
        import uuid as _uuid

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(UserModelSettings).where(
                    UserModelSettings.user_id == _uuid.UUID(user_id),
                    UserModelSettings.is_active == True,  # noqa: E712
                )
            )
            model_settings = result.scalars().first()
            if not model_settings:
                logger.warning("Dev inline: no active model settings for user %s", user_id)
                return

            from app.core.security import decrypt_api_key
            user_settings = {
                "provider": model_settings.provider,
                "model_name": model_settings.model_name,
                "api_key": decrypt_api_key(model_settings.api_key_enc, settings.APP_SECRET_KEY),
                "ollama_url": model_settings.ollama_url,
            }

        harness = AgentHarness(db_url=settings.DATABASE_URL, redis_url=settings.REDIS_URL)
        output = await harness.run(
            user_id=user_id,
            task_type="job_search",
            context={
                "search_query": search_query,
                "location": location,
                "max_results": max_results,
            },
            user_settings=user_settings,
            run_id=run_id,
        )

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentRun).where(AgentRun.id == _uuid.UUID(run_id))
            )
            run = result.scalars().first()
            if run:
                run.status = "completed"
                run.output = output
                await db.commit()

            # Persist matched jobs as saved JobApplications
            if output.get("status") == "completed":
                matches = (output.get("result") or {}).get("matches", [])
                from app.models.db import JobApplication
                async with AsyncSessionLocal() as db2:
                    for job in matches:
                        app = JobApplication(
                            user_id=_uuid.UUID(user_id),
                            company=job.get("company", "Unknown"),
                            role=job.get("title", "Unknown"),
                            job_url=job.get("job_url"),
                            jd_text=job.get("description"),
                            match_score=job.get("match_score"),
                            status="saved",
                        )
                        db2.add(app)
                    await db2.commit()

    except Exception as exc:
        logger.error("Dev inline job-search failed for run %s: %s", run_id, exc)
        try:
            from app.core.database import AsyncSessionLocal
            from app.models.db import AgentRun
            from sqlalchemy import select
            import uuid as _uuid
            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(AgentRun).where(AgentRun.id == _uuid.UUID(run_id))
                )
                run = result.scalars().first()
                if run:
                    run.status = "failed"
                    run.output = {"error": str(exc)}
                    await db.commit()
        except Exception:
            pass


async def enqueue_job_search(
    user_id: str,
    run_id: str,
    search_query: str,
    location: str,
    max_results: int,
) -> str:
    job_id = str(uuid.uuid4())

    if not _BULLMQ_AVAILABLE:
        if settings.APP_ENV == "development":
            logger.info("Dev mode: running job-search inline (no BullMQ)")
            asyncio.create_task(_run_job_search_inline(user_id, run_id, search_query, location, max_results))
            return job_id
        raise RuntimeError("bullmq is not installed; run: pip install bullmq")

    try:
        queue = _BullQueue("agent-queue", {"connection": _bullmq_connection()})
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
        finally:
            await queue.close()
    except Exception as exc:
        if settings.APP_ENV == "development":
            logger.warning("Dev mode: Redis unavailable (%s) — running job-search inline", exc)
            asyncio.create_task(_run_job_search_inline(user_id, run_id, search_query, location, max_results))
            return job_id
        logger.error("Failed to enqueue job-search for run %s: %s", run_id, exc)
        raise RuntimeError(f"Queue unavailable: {exc}") from exc

    return job_id
