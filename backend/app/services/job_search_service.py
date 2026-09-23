from __future__ import annotations

import asyncio
import hashlib
import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

# Per-platform budget: no single source may stall a run.
PLATFORM_TIMEOUT_SEC = 25

# Canonical normalized job keys returned to agents.
JOB_KEYS = (
    "job_id", "title", "company", "location", "remote", "salary_text",
    "url", "platform", "posted_at", "description",
)


def _stable_id(url: str, title: str, company: str, location: str = "") -> str:
    seed = url.strip().lower() or f"{title.strip()}|{company.strip()}|{location.strip()}".lower()
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:16]


def _normalize(raw: dict, platform: str) -> dict:
    title = str(raw.get("title", "")).strip()
    company = str(raw.get("company", "")).strip()
    url = str(raw.get("job_url", raw.get("url", ""))).strip()
    location = str(raw.get("location", "")).strip()
    return {
        "job_id": _stable_id(url, title, company, location),
        "title": title,
        "company": company,
        "location": location,
        "remote": str(raw.get("remote", raw.get("work_mode", ""))).strip(),
        "salary_text": str(raw.get("salary_text", raw.get("salary", ""))).strip(),
        "url": url,
        "platform": platform,
        "posted_at": raw.get("posted_at"),
        "description": str(raw.get("description", raw.get("jd_text", ""))),
    }


def _dedupe(jobs: list[dict]) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for job in jobs:
        key = job["url"] or f"{job['title']}|{job['company']}|{job['location']}".lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(job)
    return out


# ── Platform adapters (all sync, run in threads; lazy imports avoid cycles) ──

def _adapter_open_apis(query: str, location: str, max_results: int) -> list[dict]:
    from app.agents.job_search import _search_open_job_apis
    return _search_open_job_apis(query, location, max_results)


def _adapter_jobspy(query: str, location: str, max_results: int) -> list[dict]:
    from app.agents.job_search import _job_listings_to_dicts
    from app.services.job_platforms_service import scrape_jobs
    return _job_listings_to_dicts(
        scrape_jobs(search_term=query, location=location, results_wanted=max_results, hours_old=72)
    )


def _adapter_ats(query: str, location: str, max_results: int) -> list[dict]:
    from app.agents.job_search import _search_public_ats_jobs
    return _search_public_ats_jobs(query, location, max_results, "")


def _adapter_remoteok(query: str, location: str, max_results: int) -> list[dict]:
    from app.agents.job_search import _search_remoteok_jobs
    return _search_remoteok_jobs(query, max_results)


def _adapter_searxng(query: str, location: str, max_results: int) -> list[dict]:
    from app.agents.job_search import _search_searxng_jobs
    from app.core.config import settings
    if not settings.SEARXNG_URL:
        return []
    return _search_searxng_jobs(query, location, max_results)


def _adapter_presets(query: str, location: str, max_results: int) -> list[dict]:
    from app.agents.job_search import _search_via_search_presets
    return _search_via_search_presets(query, location, max_results)


_ADAPTERS: dict[str, Callable[[str, str, int], list[dict]]] = {
    "open_apis": _adapter_open_apis,
    "jobspy": _adapter_jobspy,
    "ats": _adapter_ats,
    "remoteok": _adapter_remoteok,
    "searxng": _adapter_searxng,
    "presets": _adapter_presets,
}

DEFAULT_PLATFORMS = ["open_apis", "jobspy", "ats", "remoteok"]


async def search_all_platforms(
    query: dict,
    platforms: list[str] | None = None,
    timeout_s: int = 90,
) -> tuple[list[dict], list[str]]:
    """Fan out across job platforms (and locations) concurrently.

    Args:
        query: {titles: list[str], locations: list[str], remote: str,
            max_results: int}. ``titles`` is required; locations optional.
        platforms: subset of _ADAPTERS keys. Unknown names are skipped with
            a warning. Defaults to DEFAULT_PLATFORMS.
        timeout_s: overall budget; each platform additionally capped at
            PLATFORM_TIMEOUT_SEC.

    Returns:
        (normalized deduped jobs, warnings). Platform failures become
        warnings — this function never raises for source errors.
    """
    titles = query.get("titles") or []
    locations = query.get("locations") or (
        [str(query["location"])] if query.get("location") else []
    ) or ["Remote"]
    max_results = int(query.get("max_results", 10))
    remote = str(query.get("remote") or "").strip().lower()
    q = " ".join(titles) if titles else str(query.get("search_query", "software engineer"))

    names = platforms or DEFAULT_PLATFORMS
    warnings: list[str] = []
    valid_names = []
    for name in names:
        if name in _ADAPTERS:
            valid_names.append(name)
        else:
            warnings.append(f"unknown platform skipped: {name}")

    async def run_one(name: str, location: str) -> list[dict]:
        adapter = _ADAPTERS[name]
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(adapter, q, location, max_results),
                timeout=PLATFORM_TIMEOUT_SEC,
            )
            return [_normalize(job, name) for job in (raw or [])]
        except Exception as exc:
            logger.warning("Platform %s (%s) failed: %s", name, location, exc)
            warnings.append(f"{name} failed: {type(exc).__name__}")
            return []

    # No outer timeout: each platform is individually capped at
    # PLATFORM_TIMEOUT_SEC and run_one never raises, so gather always
    # resolves with partial results. (An outer wait_for would cancel
    # completed sources and discard their jobs.)
    # Fan out over every requested location, not just the first — a
    # multi-location search previously silently dropped all but one city.
    per_source = await asyncio.gather(
        *(run_one(name, location) for name in valid_names for location in locations)
    )

    jobs = _dedupe([job for group in per_source for job in group])
    if remote in ("remote", "hybrid", "onsite"):
        # Post-fetch predicate: none of the adapters accept a remote/work-mode
        # parameter, so filter on each job's normalized location + remote
        # fields directly rather than dropping the request's remote field.
        def _mode_matches(job: dict) -> bool:
            haystack = f"{job.get('location', '')} {job.get('remote', '')}".lower()
            is_remote = "remote" in haystack
            is_hybrid = "hybrid" in haystack
            if remote == "remote":
                return is_remote
            if remote == "hybrid":
                return is_hybrid
            return not is_remote and not is_hybrid  # onsite

        jobs = [j for j in jobs if _mode_matches(j)]
    cap = max_results * max(len(valid_names), 1) * len(locations)
    return jobs[:cap], warnings
