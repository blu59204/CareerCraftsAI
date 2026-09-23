import asyncio
import logging

from app.core.config import settings

logger = logging.getLogger(__name__)
CLIENT_SAFE_AGENT_ERROR = "Agent failed"

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
    live_browser: bool = False,
    work_mode: str = "",
    platforms: list[str] | None = None,
    remote: str = "any",
) -> None:
    """Dev fallback: run job search agent directly without BullMQ."""
    try:
        from app.core.database import AsyncSessionLocal
        from app.core.event_bus import emit
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
        output = await asyncio.wait_for(
            harness.run(
                user_id=user_id,
                task_type="job_search",
                context={
                    "search_query": search_query,
                    "location": location,
                    "max_results": max_results,
                    "live_browser": live_browser,
                    "work_mode": work_mode,
                    "platforms": platforms or [],
                    "remote": remote,
                },
                user_settings=user_settings,
                run_id=run_id,
            ),
            timeout=300,
        )

        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(AgentRun).where(AgentRun.id == _uuid.UUID(run_id))
            )
            run = result.scalars().first()
            final_status = output.get("status", "failed")
            if run:
                run.status = final_status
                if final_status == "completed":
                    run.output = output
                else:
                    if output.get("error"):
                        logger.warning(
                            "Inline job-search run %s failed: %s",
                            run_id,
                            output.get("error"),
                        )
                    run.output = {"error": CLIENT_SAFE_AGENT_ERROR}
                await db.commit()

        if output.get("status") == "completed":
            matches = (output.get("result") or {}).get("matches", [])
            from sqlalchemy import select as _select

            from app.models.db import JobApplication
            async with AsyncSessionLocal() as db2:
                for job in matches:
                    url = job.get("url") or job.get("job_url")
                    if not url or (job.get("match_score") or 0) < 50:
                        continue
                    exists = (
                        await db2.execute(
                            _select(JobApplication.id).where(
                                JobApplication.user_id == _uuid.UUID(user_id),
                                JobApplication.job_url == url,
                            )
                        )
                    ).scalar_one_or_none()
                    if exists is not None:
                        continue
                    db2.add(JobApplication(
                        user_id=_uuid.UUID(user_id),
                        company=job.get("company", "Unknown") or "Unknown",
                        role=job.get("title", "Unknown") or "Unknown",
                        location=job.get("location"),
                        job_url=url,
                        jd_text=(job.get("description") or "")[:4000],
                        match_score=job.get("match_score"),
                        status="saved",
                    ))
                await db2.commit()

        if final_status == "completed":
            emit(run_id, "complete", output.get("result") or {})
        elif final_status == "awaiting_approval":
            emit(run_id, "checkpoint", output.get("pending_action") or {})
        else:
            emit(run_id, "error", CLIENT_SAFE_AGENT_ERROR)

    except Exception as exc:
        logger.error(
            "Dev inline job-search failed for run %s: %s",
            run_id,
            exc,
            exc_info=True,
        )
        from app.core.event_bus import emit
        emit(run_id, "error", CLIENT_SAFE_AGENT_ERROR)
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
                    run.output = {"error": CLIENT_SAFE_AGENT_ERROR}
                    await db.commit()
        except Exception as db_exc:
            logger.warning("Failed to mark inline job-search run %s failed: %s", run_id, db_exc)


def make_job_search_id(user_id: str, search_query: str, location: str, max_results: int) -> str:
    """Deterministic BullMQ job id — duplicate clicks don't double-run."""
    import hashlib

    digest = hashlib.sha256(
        f"{user_id}:{search_query}:{location}:{max_results}".encode("utf-8")
    ).hexdigest()[:16]
    return f"{user_id}:job_search:{digest}"


async def enqueue_job_search(
    user_id: str,
    run_id: str,
    search_query: str,
    location: str,
    max_results: int,
    live_browser: bool = False,
    work_mode: str = "",
    job_id: str | None = None,
    platforms: list[str] | None = None,
    remote: str = "any",
) -> tuple[str, bool]:
    """Enqueue a job-search run. Returns (job_id, queued).

    queued=True means BullMQ accepted the job. queued=False means the dev
    inline fallback ran (development only, with a WARNING). Production with
    an unreachable queue raises RuntimeError — never inline.
    """
    job_id = job_id or make_job_search_id(user_id, search_query, location, max_results)
    payload = {
        "user_id": user_id,
        "run_id": run_id,
        "search_query": search_query,
        "location": location,
        "max_results": max_results,
        "live_browser": live_browser,
        "work_mode": work_mode,
        "platforms": platforms or [],
        "remote": remote,
    }

    if not _BULLMQ_AVAILABLE:
        if settings.APP_ENV == "development":
            logger.info("Dev mode: running job-search inline (no BullMQ)")
            asyncio.create_task(_run_job_search_inline(
                user_id, run_id, search_query, location, max_results,
                live_browser, work_mode, platforms, remote,
            ))
            return job_id, False
        raise RuntimeError("bullmq is not installed; run: pip install bullmq")

    try:
        queue = _BullQueue("agent-queue", {"connection": _bullmq_connection()})
        try:
            await queue.add(
                "job-search",
                payload,
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
            asyncio.create_task(_run_job_search_inline(
                user_id, run_id, search_query, location, max_results,
                live_browser, work_mode, platforms, remote,
            ))
            return job_id, False
        logger.error("Failed to enqueue job-search for run %s: %s", run_id, exc)
        raise RuntimeError("Queue unavailable") from exc

    return job_id, True
