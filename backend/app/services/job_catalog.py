"""Durable source cache/health and failure-isolated public discovery."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from sqlalchemy import text

from app.services.job_connectors import Source, dedupe, fetch_page, normalize
from app.services.jobs_database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Catalog rows seen within this window are served before any live fetch.
CATALOG_FRESH_DAYS = 14
# Cold/gap-fill refresh targets: bounded set of fast public sources.
PREFERRED_SOURCES = {
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


def sources() -> list[Source]:
    from app.core.config import settings

    rows = json.loads(Path(__file__).with_name("job_sources.json").read_text())
    mapped = {
        row["id"]: Source(
            **{
                k: row[k]
                for k in ("id", "family", "tenant", "permitted", "url", "refresh_hours")
                if k in row
            }
        )
        for row in rows
    }
    for row in settings.JOB_SOURCE_OVERRIDES[:100]:
        source = Source(**row)
        mapped[source.id] = source
    return [source for source in mapped.values() if source.permitted]


async def upsert_jobs(db, jobs: list[dict], source_id: str) -> None:
    """Upsert normalized jobs into the shared catalog + occurrences (caller commits)."""
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
                "posted": (datetime.fromisoformat(job["posted_at"]) if job["posted_at"] else None),
                "data": json.dumps(job),
            },
        )
        await db.execute(
            text("""INSERT INTO job_source_occurrences(job_id,source_id)
            VALUES(:job,:source) ON CONFLICT(job_id,source_id)
            DO UPDATE SET last_seen_at=now()"""),
            {"job": job["job_id"], "source": source_id},
        )


async def write_through(raw_jobs: list[dict], platform: str) -> int:
    """Store live-fetched jobs (url/title/company/... dicts) under source ``live:<platform>``.

    Never raises: a failed catalog write must not fail the user's search.
    """
    try:
        source = Source(id=f"live:{platform}", family=platform)
        jobs = []
        for raw in raw_jobs:
            # Live adapters emit free-text "remote"; only the literal flag counts here.
            flag = str(raw.get("remote", "")).lower() == "remote"
            job = normalize({**raw, "remote": flag}, source)
            if job:
                jobs.append(job)
        if not jobs:
            return 0
        async with AsyncSessionLocal() as db:
            await db.execute(
                text(
                    "INSERT INTO job_source_health(source_id) VALUES (:id) ON CONFLICT DO NOTHING"
                ),
                {"id": source.id},
            )
            await upsert_jobs(db, jobs, source.id)
            await db.commit()
        return len(jobs)
    except Exception as exc:
        logger.warning(
            "job_catalog_write_through_failed",
            extra={"platform": platform, "error_type": type(exc).__name__},
        )
        return 0


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
    interval = timedelta(hours=24 if source.family == "remotive" else source.refresh_hours)
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
            await upsert_jobs(db, jobs, source.id)
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


def _live_only(job: dict) -> bool:
    occ = job.get("occurrences") or []
    return bool(occ) and all(str(o.get("source_id", "")).startswith("live:") for o in occ)


def _location_ok(job: dict, locations: list[str]) -> bool:
    hay = f"{job.get('location', '')} {job.get('remote', '')}".lower()
    return (
        not locations
        or "remote" in hay
        or any(loc.split(",")[0].strip().lower() in hay for loc in locations if loc.strip())
    )


async def search_catalog(query: dict, selected_sources=None, live_platforms=()):
    """Serve fresh shared-catalog jobs first; refresh public sources only for a shortfall.

    ``live_platforms`` also reads jobs other users' live searches stored under ``live:<name>``.
    """
    families = set(selected_sources or [])
    live_ids = [f"live:{p}" for p in live_platforms]
    public = (
        []
        if live_ids and not families
        else [s for s in sources() if not families or s.family in families or s.id in families]
    )
    if not public and not live_ids:
        return [], ["No public source matches the requested filters"]
    terms = (
        (" ".join(query.get("titles") or []) or query.get("search_query") or "software engineer")
        .lower()
        .split()
    )
    days = query.get("posted_within_days", 30)
    need = int(query.get("max_results") or 10)
    locations = [str(x) for x in (query.get("locations") or [query.get("location") or ""]) if x]
    remote = query.get("remote", "any")

    def relevant_of(rows):
        out = [
            j
            for j in dedupe(rows, days)
            if any(w in (j["title"] + " " + j["description"]).lower() for w in terms if len(w) > 2)
            and (not _live_only(j) or _location_ok(j, locations))
        ]
        if remote in {"remote", "hybrid", "onsite"}:
            out = [
                j
                for j in out
                if j["remote"] == remote or (remote == "onsite" and j["remote"] == "unknown")
            ]
        return out

    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    # ponytail: LIMIT 2000 is a safety ceiling on rows read per search, not a
                    # product cap; page by posted_at if a query ever saturates it.
                    text("""SELECT c.data || jsonb_build_object('occurrences',
            jsonb_agg(jsonb_build_object('source_id',o.source_id,'url',c.url))) FROM job_catalog c
            JOIN job_source_occurrences o ON o.job_id=c.job_id
            WHERE o.source_id=ANY(:sources) AND c.last_seen_at > :fresh
            AND (c.posted_at IS NULL OR c.posted_at >= :cutoff)
            AND lower(c.title) LIKE ANY(:terms)
            GROUP BY c.job_id ORDER BY c.posted_at DESC NULLS LAST LIMIT 2000"""),
                    {
                        "sources": [s.id for s in public] + live_ids,
                        "terms": ["%" + t + "%" for t in terms if len(t) > 2],
                        "fresh": datetime.now(UTC) - timedelta(days=CATALOG_FRESH_DAYS),
                        "cutoff": datetime.now(UTC) - timedelta(days=days),
                    },
                )
            )
            .scalars()
            .all()
        )
    warnings = []
    relevant = relevant_of(rows)
    if public and len(relevant) < need:
        semaphore = asyncio.Semaphore(6)
        # Gap fill is bounded (<=12 sources, 6 at a time); refresh_source honours its own
        # lease/backoff so repeated shortfalls do not re-hit upstream. The Schedule refreshes
        # the complete employer catalog.
        preferred = [s for s in public if s.id in PREFERRED_SOURCES]

        async def one(source):
            async with semaphore:
                try:
                    return await refresh_source(source)
                except Exception as exc:
                    return [], source.id + ": " + type(exc).__name__

        results = await asyncio.gather(*(one(s) for s in (preferred or public)[:12]))
        rows = rows + [j for jobs, _ in results for j in jobs]
        warnings.extend(w for _, w in results if w)
        relevant = relevant_of(rows)
    return relevant, warnings
