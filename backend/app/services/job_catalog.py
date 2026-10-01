"""Durable source cache/health and failure-isolated public discovery."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import text

from app.services.job_connectors import Source, dedupe, fetch_page
from app.services.jobs_database import AsyncSessionLocal

logger = logging.getLogger(__name__)


def sources() -> list[Source]:
    from app.core.config import settings

    rows = json.loads(Path(__file__).with_name("job_sources.json").read_text())
    mapped = {
        row["id"]: Source(**{k: row[k] for k in ("id", "family", "tenant", "permitted")})
        for row in rows
    }
    for row in settings.JOB_SOURCE_OVERRIDES[:100]:
        source = Source(**row)
        mapped[source.id] = source
    return [source for source in mapped.values() if source.permitted]


async def refresh_source(source: Source, query="", force=False) -> tuple[list[dict], str | None]:
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("INSERT INTO job_source_health(source_id) VALUES (:id) ON CONFLICT DO NOTHING"),
            {"id": source.id},
        )
        cached = (
            (
                await db.execute(
                    text("SELECT * FROM job_source_health WHERE source_id=:id FOR UPDATE"),
                    {"id": source.id},
                )
            )
            .mappings()
            .one()
        )
        if cached["next_allowed_at"] and cached["next_allowed_at"] > now:
            return cached["cached_jobs"] or [], cached["warning"]
        # A persisted lease prevents multiple API/worker processes refreshing one source.
        await db.execute(
            text("UPDATE job_source_health SET next_allowed_at=:lease WHERE source_id=:id"),
            {"id": source.id, "lease": now + timedelta(minutes=5)},
        )
        await db.commit()
    jobs, warning, cursor, retry_after = [], None, None, None
    try:
        for _ in range(3):
            for attempt in range(2):
                try:
                    result = await asyncio.wait_for(fetch_page(source, query, cursor), 15)
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in {401, 403, 429}:
                        raise
                    if attempt or exc.response.status_code < 500:
                        raise
                    await asyncio.sleep(1)
                except (httpx.TransportError, TimeoutError):
                    if attempt:
                        raise
                    await asyncio.sleep(1)
            jobs.extend(result.jobs)
            cursor = result.next_cursor
            if not cursor or len(jobs) >= 1000:
                break
            await asyncio.sleep(1)
    except Exception as exc:
        if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code in {401, 403, 429}:
            retry_after = 3600
            try:
                retry_after = max(
                    3600, min(86400, int(exc.response.headers.get("retry-after", "3600")))
                )
            except ValueError:
                pass
        # Never log URL/request/response bodies: they may contain API keys.
        warning = f"{source.id}: {type(exc).__name__}"
        logger.warning(
            "job_source_failure", extra={"source_id": source.id, "error_type": type(exc).__name__}
        )
        jobs = cached["cached_jobs"] or []
    interval = timedelta(hours=24 if source.family == "remotive" else 1)
    if warning:
        interval = timedelta(minutes=min(60, 2 ** min(int(cached["failures"] or 0) + 1, 6)))
        if retry_after:
            interval = timedelta(seconds=retry_after)
    async with AsyncSessionLocal() as db:
        await db.execute(
            text("""UPDATE job_source_health SET checked_at=:now, next_allowed_at=:next,
            cached_jobs=CAST(:jobs AS jsonb), warning=:warning,
            failures=CASE WHEN CAST(:warning AS text) IS NULL THEN 0 ELSE failures+1 END,
            status=CASE WHEN CAST(:warning AS text) IS NULL THEN 'healthy' ELSE 'degraded' END
            WHERE source_id=:id"""),
            {
                "id": source.id,
                "now": now,
                "next": now + interval,
                "jobs": json.dumps(jobs),
                "warning": warning,
            },
        )
        if not warning:
            for job in dedupe(jobs, 90):
                await db.execute(
                    text("""INSERT INTO job_catalog(job_id,url,title,company,posted_at,data)
                    VALUES(:id,:url,:title,:company,:posted,CAST(:data AS jsonb))
                    ON CONFLICT(job_id) DO UPDATE SET data=EXCLUDED.data ||
                    jsonb_build_object('first_seen_at',job_catalog.first_seen_at),title=EXCLUDED.title,
                    company=EXCLUDED.company,posted_at=EXCLUDED.posted_at,last_seen_at=now()"""),
                    {
                        "id": job["job_id"],
                        "url": job["url"],
                        "title": job["title"],
                        "company": job["company"],
                        "posted": (
                            datetime.fromisoformat(job["posted_at"]) if job["posted_at"] else None
                        ),
                        "data": json.dumps(job),
                    },
                )
                await db.execute(
                    text("""INSERT INTO job_source_occurrences(job_id,source_id)
                    VALUES(:job,:source) ON CONFLICT(job_id,source_id)
                    DO UPDATE SET last_seen_at=now()"""),
                    {"job": job["job_id"], "source": source.id},
                )
            if cursor is None:
                await db.execute(
                    text(
                        "DELETE FROM job_source_occurrences WHERE source_id=:id "
                        "AND NOT(job_id=ANY(:jobs))"
                    ),
                    {"id": source.id, "jobs": [job["job_id"] for job in jobs]},
                )
        await db.commit()
    logger.info(
        "job_source_health",
        extra={
            "source_id": source.id,
            "status": "degraded" if warning else "healthy",
            "job_count": len(jobs),
        },
    )
    return jobs, warning


async def refresh_catalog() -> dict:
    semaphore = asyncio.Semaphore(8)

    async def one(source):
        async with semaphore:
            try:
                jobs, warning = await refresh_source(source)
                return len(jobs), warning
            except Exception as exc:
                logger.warning(
                    "job_source_storage_failure",
                    extra={"source_id": source.id, "error_type": type(exc).__name__},
                )
                return 0, source.id + ": unavailable"

    results = await asyncio.gather(*(one(source) for source in sources()))
    return {
        "sources": len(results),
        "healthy": sum(w is None for _, w in results),
        "jobs": sum(n for n, _ in results),
    }


async def search_catalog(query: dict, selected_sources=None):
    families = set(selected_sources or [])
    public = [s for s in sources() if not families or s.family in families or s.id in families]
    if not public:
        return [], ["No public source matches the requested filters"]
    terms = (
        (" ".join(query.get("titles") or []) or query.get("search_query") or "software engineer")
        .lower()
        .split()
    )
    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    text("""SELECT c.data || jsonb_build_object('occurrences',
            jsonb_agg(jsonb_build_object('source_id',o.source_id,'url',c.url))) FROM job_catalog c
            JOIN job_source_occurrences o ON o.job_id=c.job_id
            WHERE o.source_id=ANY(:sources) AND c.last_seen_at > now()-interval '7 days'
            AND (c.posted_at IS NULL OR c.posted_at >= :cutoff)
            AND lower(c.title) LIKE ANY(:terms)
            GROUP BY c.job_id ORDER BY c.posted_at DESC NULLS LAST LIMIT 2000"""),
                    {
                        "sources": [s.id for s in public],
                        "terms": ["%" + t + "%" for t in terms if len(t) > 2],
                        "cutoff": datetime.now(UTC)
                        - timedelta(days=query.get("posted_within_days", 30)),
                    },
                )
            )
            .scalars()
            .all()
        )
    warnings = []
    if not rows:
        semaphore = asyncio.Semaphore(6)
        # Cold start is bounded; the Schedule refreshes the complete employer catalog.
        preferred = [
            s
            for s in public
            if s.id
            in {
                "greenhouse:stripe",
                "greenhouse:gitlab",
                "greenhouse:figma",
                "lever:netflix",
                "lever:benchling",
                "ashby:linear",
                "ashby:vanta",
                "remotive",
                "remoteok",
                "arbeitnow",
            }
        ]

        async def one(source):
            async with semaphore:
                try:
                    return await refresh_source(source)
                except Exception as exc:
                    return [], source.id + ": " + type(exc).__name__

        results = await asyncio.gather(*(one(s) for s in (preferred or public)[:12]))
        rows = [j for jobs, _ in results for j in jobs]
        warnings.extend(w for _, w in results if w)
    jobs = dedupe(rows, query.get("posted_within_days", 30))
    relevant = [
        j
        for j in jobs
        if any(
            word in (j["title"] + " " + j["description"]).lower() for word in terms if len(word) > 2
        )
    ]
    remote = query.get("remote", "any")
    if remote in {"remote", "hybrid", "onsite"}:
        relevant = [
            j
            for j in relevant
            if j["remote"] == remote or (remote == "onsite" and j["remote"] == "unknown")
        ]
    return relevant[:300], warnings
