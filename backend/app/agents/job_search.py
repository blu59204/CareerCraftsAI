import asyncio
import concurrent.futures
import inspect
import json
import logging
import os
from urllib.parse import quote_plus

import httpx
from langchain_core.messages import AIMessage, HumanMessage

from app.agents.state import AgentState
from app.core.config import settings as app_settings
from app.core.event_bus import emit
from app.core.model_router import _build_llm
from app.core.sync_db import fetch_model_settings, fetch_user_profile_text

logger = logging.getLogger(__name__)
SOURCE_TIMEOUT_SEC = 45
REMOTEOK_API_URL = "https://remoteok.com/api"
GREENHOUSE_BOARDS = (
    "airbnb",
    "stripe",
    "databricks",
    "doordashusa",
    "figma",
    "gitlab",
    "grammarly",
    "notion",
    "ramp",
    "rippling",
    "robinhood",
    "scaleai",
)
LEVER_COMPANIES = (
    "ashby",
    "benchling",
    "chime",
    "coursera",
    "netflix",
    "reddit",
    "shopify",
    "zapier",
)

LINKEDIN_SEARCH_URL = (
    "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_TPR=r86400"
)

SCORE_PROMPT = """Rate how well this job matches the candidate profile. Return ONLY a number 0-100.

Candidate profile:
{profile}

Job: {title} at {company}
Description: {description}

Score (0-100):"""

EXTRACT_PROMPT = """Extract job listings from this page text. Return a JSON array of objects with keys:
title, company, location, description, job_url.
Extract up to {max_results} jobs. If no jobs found, return [].
Return ONLY valid JSON, no explanation.

Page text:
{text}"""

def _extract_jobs_from_text(llm, page_text: str, max_results: int) -> list[dict]:
    try:
        resp = llm.invoke([HumanMessage(
            content=EXTRACT_PROMPT.format(max_results=max_results, text=page_text[:6000])
        )])
        content = resp.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)[:max_results]
    except Exception as exc:
        logger.warning("Job extraction from page text failed: %s", exc)
        return []


def _heuristic_score_job(job: dict, profile: str) -> int:
    terms = {
        term.lower().strip(".,:;()[]")
        for term in profile.split()
        if len(term.strip(".,:;()[]")) > 2
        and term.lower() not in {"and", "the", "with", "for", "from"}
    }
    haystack = " ".join(
        str(job.get(key, ""))
        for key in ("title", "company", "location", "description", "platform")
    ).lower()
    overlap = sum(1 for term in terms if term in haystack)
    score = 45 + min(35, overlap * 10)
    if "remote" in haystack or "worldwide" in haystack:
        score += 10
    if any(level in haystack for level in ("senior", "lead", "principal")):
        score += 5
    return min(score, 92)


def _score_job(llm, job: dict, profile: str, thinking: str = "") -> int:
    try:
        resp = llm.invoke([HumanMessage(
            content=SCORE_PROMPT.format(
                profile=profile,
                title=job.get("title", ""),
                company=job.get("company", ""),
                description=str(job.get("description", ""))[:500],
            ) + (f"\n\nScoring criteria from analysis:\n{thinking}" if thinking else "")
        )])
        digits = "".join(c for c in resp.content.strip()[:3] if c.isdigit())
        return int(digits) if digits else _heuristic_score_job(job, profile)
    except Exception as exc:
        logger.warning("Score failed for %s at %s: %s", job.get("title"), job.get("company"), exc)
        return _heuristic_score_job(job, profile)


def _job_listings_to_dicts(job_listings) -> list[dict]:
    return [
        {"title": j.title, "company": j.company, "location": j.location,
         "description": j.description, "job_url": j.job_url, "platform": j.platform}
        for j in job_listings
    ]


def _run_async_result(value, timeout_sec: int = 60):
    if inspect.isawaitable(value):
        from app.core.sync_db import run_coro_sync
        return run_coro_sync(asyncio.wait_for(value, timeout=timeout_sec))
    return value


def _run_sync_with_timeout(func, *args, timeout_sec: int = SOURCE_TIMEOUT_SEC, **kwargs):
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        future = executor.submit(func, *args, **kwargs)
        return future.result(timeout=timeout_sec)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)


def _fetch_job_preference_text(user_id: str) -> str:
    try:
        from uuid import UUID
        from sqlalchemy import select
        from app.core.sync_db import _get_sync_factory
        from app.models.db import User, UserPreferences

        factory = _get_sync_factory()
        with factory() as db:
            user_uuid = None
            try:
                user_uuid = UUID(str(user_id))
            except ValueError:
                pass
            criteria = User.supabase_uid == str(user_id)
            if user_uuid:
                criteria = (User.id == user_uuid) | criteria
            user = db.execute(select(User).where(criteria)).scalars().first()
            prefs = db.execute(
                select(UserPreferences).where(UserPreferences.user_id == user.id)
            ).scalars().first() if user else None
            if not prefs:
                return ""
            return "\n".join(
                [
                    "Saved job preferences:",
                    f"Current title: {prefs.current_title or ''}",
                    f"Experience level: {prefs.experience_level or ''}",
                    f"Years experience: {prefs.years_experience if prefs.years_experience is not None else ''}",
                    f"Job type: {prefs.job_type or ''}",
                    f"Work mode: {prefs.work_mode or ''}",
                    f"Target roles: {', '.join(prefs.target_roles or [])}",
                    f"Preferred locations: {', '.join(prefs.preferred_locations or [])}",
                    f"Bio: {(prefs.bio or '')[:500]}",
                ]
            )
    except Exception as exc:
        logger.debug("Could not load job preferences for scoring: %s", exc)
        return ""


def _search_google_jobs_source(
    *,
    llm,
    user_id: str,
    query: str,
    location: str,
    max_results: int,
    live_browser: bool,
    run_id: str,
) -> list[dict]:
    from app.services.indian_platforms_service import search_google_jobs

    google_jobs = _run_async_result(
        search_google_jobs(
            llm=llm,
            user_id=user_id,
            search_term=query,
            location=location,
            results_wanted=max_results,
            live_browser=live_browser,
            run_id=run_id,
        ),
        timeout_sec=SOURCE_TIMEOUT_SEC,
    )
    return _job_listings_to_dicts(google_jobs)


AGENTQL_JOBS_QUERY = """
{
    search_results[] {
        title
        url
        snippet
    }
}
"""


def _domain_of(url: str) -> str:
    try:
        from urllib.parse import urlparse
        host = urlparse(url).netloc.lower().lstrip("www.")
        return host.split(":")[0] or "Unknown"
    except Exception:
        return "Unknown"


def _search_searxng_jobs(query: str, location: str, max_results: int) -> list[dict]:
    """Query a self-hosted SearXNG meta-search for real jobs (JSON, no CAPTCHA).

    SearXNG aggregates Google/Bing/DuckDuckGo/Brave results and accepts dork
    operators (site:, OR, -, filetype:). Off unless SEARXNG_URL is configured.
    """
    base = (app_settings.SEARXNG_URL or "").rstrip("/")
    if not base:
        return []
    try:
        resp = httpx.get(
            f"{base}/search",
            params={"q": f"{query} jobs {location}", "format": "json"},
            timeout=20,
        )
        resp.raise_for_status()
        results = resp.json().get("results", []) or []
    except Exception as exc:
        logger.warning("SearXNG search failed: %s", exc)
        return []
    jobs: list[dict] = []
    for item in results:
        url = (item or {}).get("url")
        title = (item or {}).get("title")
        if not url or not title:
            continue
        jobs.append({
            "title": title,
            "company": _domain_of(url),
            "location": location,
            "description": (item.get("content") or "")[:2000],
            "job_url": url,
            "platform": "searxng",
        })
        if len(jobs) >= max_results:
            break
    return jobs


async def _search_agentql_jobs_browser(
    query: str,
    location: str,
    max_results: int,
    run_id: str,
    live_browser: bool = True,
) -> list[dict]:
    """Scrape real jobs with a live browser using AgentQL (TinyFish).

    Searches DuckDuckGo HTML (bot-friendly, no CAPTCHA, supports site:/OR/-
    operators) and extracts organic results — each links to a real job posting
    on LinkedIn/Naukri/company sites. Google is avoided because it CAPTCHAs
    automated requests. Gated behind AGENTQL_API_KEY; returns [] when the key or
    library is unavailable so callers fall back gracefully.
    """
    if not app_settings.AGENTQL_API_KEY:
        return []
    try:
        import agentql
        from playwright.async_api import async_playwright
    except ImportError as exc:
        logger.warning("AgentQL unavailable for live job search: %s", exc)
        return []

    # AgentQL SDK reads the key from the environment.
    os.environ.setdefault("AGENTQL_API_KEY", app_settings.AGENTQL_API_KEY)

    url = f"https://html.duckduckgo.com/html/?q={quote_plus(f'{query} jobs {location}')}"
    emit(run_id, "browser", {
        "phase": "visible_browser_opening",
        "source": "agentql",
        "url": url,
        "message": "Opening live browser (AgentQL) for DuckDuckGo job search results",
    })
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not live_browser)
        page = await agentql.wrap_async(browser.new_page())
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_page_ready_state()
            data = await page.query_data(AGENTQL_JOBS_QUERY)
            jobs: list[dict] = []
            for item in (data or {}).get("search_results", []) or []:
                title = (item or {}).get("title")
                link = (item or {}).get("url")
                if not title or not link:
                    continue
                jobs.append({
                    "title": title,
                    "company": _domain_of(link),
                    "location": location,
                    "description": (item.get("snippet") or "")[:2000],
                    "job_url": link,
                    "platform": "google",
                })
                if len(jobs) >= max_results:
                    break
            emit(run_id, "browser", {"phase": "visible_browser_done", "source": "agentql", "count": len(jobs)})
            if live_browser:
                await page.wait_for_timeout(3000)
            return jobs
        except Exception as exc:
            logger.warning("AgentQL live job search failed: %s", exc)
            emit(run_id, "browser", {"phase": "visible_browser_failed", "source": "agentql", "error": "AgentQL search failed"})
            return []
        finally:
            await browser.close()


def _remoteok_row_to_job(raw_text: str, job_url: str) -> dict | None:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    lines = [line for line in lines if line.lower() not in {"apply", "ad"}]
    if len(lines) > 2 and len(lines[0]) <= 3:
        lines = lines[1:]
    if len(lines) < 2 or "remote ok premium" in raw_text.lower():
        return None
    location = lines[2] if len(lines) > 2 else "Remote"
    if "remote" not in location.lower():
        location = f"Remote - {location}"
    return {
        "title": lines[0],
        "company": lines[1],
        "location": location,
        "description": " ".join(lines[2:10])[:2000],
        "job_url": job_url,
        "platform": "remoteok",
    }


async def _search_remoteok_jobs_browser(
    query: str,
    max_results: int,
    run_id: str,
    live_browser: bool = True,
) -> list[dict]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        logger.warning("Playwright unavailable for visible RemoteOK search: %s", exc)
        return []

    url = f"https://remoteok.com/?search={quote_plus(query)}"
    emit(run_id, "browser", {
        "phase": "visible_browser_opening",
        "source": "remoteok",
        "url": url,
        "message": "Opening RemoteOK in visible browser",
    })
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=not live_browser)
        page = await browser.new_page(viewport={"width": 1366, "height": 900})
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000)
            for selector in ('button:has-text("×")', '.modal button', '.close'):
                try:
                    await page.locator(selector).first.click(timeout=1000)
                    break
                except Exception as exc:
                    logger.debug("RemoteOK popup close failed for %s: %s", selector, exc)
                    continue

            rows = page.locator("tr.job")
            count = await rows.count()
            jobs: list[dict] = []
            for index in range(min(count, max_results * 4)):
                row = rows.nth(index)
                try:
                    raw = await row.inner_text(timeout=1500)
                    data_url = await row.get_attribute("data-url")
                except Exception as exc:
                    logger.debug("Skipping RemoteOK row %s: %s", index, exc)
                    continue
                job_url = f"https://remoteok.com{data_url}" if data_url else url
                job = _remoteok_row_to_job(raw, job_url)
                if not job or not _matches_query(job, query):
                    continue
                jobs.append(job)
                if len(jobs) >= max_results:
                    break

            emit(run_id, "browser", {"phase": "visible_browser_done", "source": "remoteok", "count": len(jobs)})
            if live_browser:
                await page.wait_for_timeout(5000)
            return jobs
        except Exception as exc:
            logger.warning("Visible RemoteOK search failed: %s", exc)
            emit(run_id, "browser", {"phase": "visible_browser_failed", "source": "remoteok", "error": "Visible browser search failed"})
            return []
        finally:
            await browser.close()


def _search_remoteok_jobs(query: str, max_results: int) -> list[dict]:
    terms = {term.lower() for term in query.split() if len(term) > 2}
    response = httpx.get(
        REMOTEOK_API_URL,
        headers={"User-Agent": "CareerCraftAI/1.0"},
        timeout=15,
    )
    response.raise_for_status()
    rows = response.json()
    jobs: list[dict] = []
    for row in rows:
        if not isinstance(row, dict) or not row.get("position"):
            continue
        haystack = " ".join(
            str(row.get(key, ""))
            for key in ("position", "company", "description", "tags")
        ).lower()
        if terms and not any(term in haystack for term in terms):
            continue
        jobs.append(
            {
                "title": row.get("position") or "Unknown",
                "company": row.get("company") or "Unknown",
                "location": row.get("location") or "Remote",
                "description": row.get("description") or "",
                "job_url": row.get("url") or row.get("apply_url"),
                "platform": "remoteok",
            }
        )
        if len(jobs) >= max_results:
            break
    return jobs


def _query_terms(query: str) -> set[str]:
    stop = {
        "and", "for", "the", "with", "remote", "hybrid", "onsite", "entry",
        "level", "senior", "junior", "lead", "full", "time",
    }
    return {
        term.lower().strip(".,:;()[]")
        for term in query.split()
        if len(term.strip(".,:;()[]")) > 2 and term.lower() not in stop
    }


def _matches_query(job: dict, query: str) -> bool:
    terms = _query_terms(query)
    if not terms:
        return True
    haystack = " ".join(
        str(job.get(key, ""))
        for key in ("title", "company", "location", "description", "platform")
    ).lower()
    return any(term in haystack for term in terms)


def _matches_work_mode(job: dict, work_mode: str, location: str) -> bool:
    modes = [
        item.strip().lower()
        for item in (work_mode or "").split(",")
        if item.strip()
    ]
    if len(modes) > 1:
        return any(_matches_work_mode(job, mode, location) for mode in modes)
    mode = modes[0] if modes else ""
    loc = (job.get("location") or "").lower()
    desired_location = (location or "").lower()
    if mode == "remote":
        return "remote" in loc or desired_location == "remote"
    if mode == "hybrid":
        return "hybrid" in loc or (
            desired_location not in {"", "any", "remote"} and desired_location in loc
        )
    if mode == "onsite":
        return "remote" not in loc and (
            desired_location in {"", "any"} or desired_location in loc
        )
    if desired_location not in {"", "any", "remote"}:
        return desired_location in loc or "remote" in loc
    return True


def _dedupe_jobs(jobs: list[dict], max_results: int) -> list[dict]:
    seen: set[str] = set()
    unique: list[dict] = []
    for job in jobs:
        key = (job.get("job_url") or f"{job.get('company')}::{job.get('title')}").lower()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(job)
        if len(unique) >= max_results:
            break
    return unique


def _search_greenhouse_board(client: httpx.Client, board: str) -> list[dict]:
    response = client.get(
        f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs",
        params={"content": "true"},
    )
    response.raise_for_status()
    rows = response.json().get("jobs", [])
    jobs: list[dict] = []
    for row in rows:
        location = row.get("location") or {}
        jobs.append(
            {
                "title": row.get("title") or "Unknown",
                "company": row.get("company_name") or board.title(),
                "location": location.get("name") if isinstance(location, dict) else str(location),
                "description": row.get("content") or "",
                "job_url": row.get("absolute_url"),
                "platform": "greenhouse",
            }
        )
    return jobs


def _search_lever_company(client: httpx.Client, company: str) -> list[dict]:
    response = client.get(f"https://api.lever.co/v0/postings/{company}", params={"mode": "json"})
    response.raise_for_status()
    rows = response.json()
    jobs: list[dict] = []
    for row in rows:
        categories = row.get("categories") or {}
        jobs.append(
            {
                "title": row.get("text") or "Unknown",
                "company": company.title(),
                "location": categories.get("location") or "Unknown",
                "description": row.get("descriptionPlain") or row.get("description") or "",
                "job_url": row.get("hostedUrl") or row.get("applyUrl"),
                "platform": "lever",
            }
        )
    return jobs


def _search_public_ats_jobs(
    query: str,
    location: str,
    max_results: int,
    work_mode: str = "",
) -> list[dict]:
    jobs: list[dict] = []
    with httpx.Client(headers={"User-Agent": "CareerCraftAI/1.0"}, timeout=8) as client:
        for board in GREENHOUSE_BOARDS:
            try:
                jobs.extend(_search_greenhouse_board(client, board))
            except Exception as exc:
                logger.debug("Greenhouse board %s unavailable: %s", board, exc)
        for company in LEVER_COMPANIES:
            try:
                jobs.extend(_search_lever_company(client, company))
            except Exception as exc:
                logger.debug("Lever company %s unavailable: %s", company, exc)

    filtered = [
        job
        for job in jobs
        if _matches_query(job, query) and _matches_work_mode(job, work_mode, location)
    ]
    return _dedupe_jobs(filtered, max_results)


def _strip_html(text: str) -> str:
    import re

    return re.sub(r"<[^>]+>", " ", text or "").replace("&nbsp;", " ").strip()


def _search_open_job_apis(query: str, location: str, max_results: int) -> list[dict]:
    """Real job listings from free, key-less JSON APIs (Remotive, Arbeitnow, Jobicy).

    Every returned job carries a real `job_url` apply link. Reliable and fast —
    no scraping, no rate-limited search engines. This is the primary source.
    """
    jobs: list[dict] = []
    q = (query or "").strip()
    first_term = q.split()[0] if q else "developer"
    terms = [t.lower() for t in q.split() if len(t) > 2]

    def _relevant(text: str) -> bool:
        if not terms:
            return True
        blob = text.lower()
        return any(t in blob for t in terms)

    with httpx.Client(timeout=15, follow_redirects=True,
                      headers={"User-Agent": "Mozilla/5.0 (CareerCraft)"}) as client:
        # 0a) JSearch (RapidAPI) — aggregates Google for Jobs / LinkedIn / Indeed /
        # Naukri. Best coverage incl. India. Real apply links. Used when key is set.
        if app_settings.RAPIDAPI_KEY:
            try:
                jq = q or first_term
                if location and location.lower() != "any":
                    jq = f"{jq} in {location}"
                r = client.get(
                    "https://jsearch.p.rapidapi.com/search",
                    params={"query": jq, "page": "1", "num_pages": "1", "date_posted": "month"},
                    headers={
                        "X-RapidAPI-Key": app_settings.RAPIDAPI_KEY,
                        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
                    },
                )
                for j in (r.json().get("data") or [])[: max_results * 2]:
                    loc = ", ".join(
                        p for p in (j.get("job_city"), j.get("job_state"), j.get("job_country")) if p
                    )
                    jobs.append({
                        "title": j.get("job_title", ""),
                        "company": j.get("employer_name", ""),
                        "location": loc or "—",
                        "description": _strip_html(j.get("job_description", ""))[:600],
                        "job_url": j.get("job_apply_link", ""),
                        "platform": "jsearch",
                    })
            except Exception as exc:
                logger.warning("JSearch API failed: %s", exc)

        # 0b) Adzuna — free key, strong India coverage. Country code in path.
        if app_settings.ADZUNA_APP_ID and app_settings.ADZUNA_APP_KEY:
            try:
                country = "in" if (location or "").lower() in ("", "any", "india") else "gb"
                r = client.get(
                    f"https://api.adzuna.com/v1/api/jobs/{country}/search/1",
                    params={
                        "app_id": app_settings.ADZUNA_APP_ID,
                        "app_key": app_settings.ADZUNA_APP_KEY,
                        "results_per_page": max_results,
                        "what": q or first_term,
                        "content-type": "application/json",
                    },
                )
                for j in (r.json().get("results") or []):
                    jobs.append({
                        "title": j.get("title", ""),
                        "company": (j.get("company") or {}).get("display_name", ""),
                        "location": (j.get("location") or {}).get("display_name", ""),
                        "description": _strip_html(j.get("description", ""))[:600],
                        "job_url": j.get("redirect_url", ""),
                        "platform": "adzuna",
                    })
            except Exception as exc:
                logger.warning("Adzuna API failed: %s", exc)

        # 1) Remotive — supports server-side search.
        try:
            r = client.get("https://remotive.com/api/remote-jobs",
                           params={"search": q or first_term, "limit": max_results})
            for j in (r.json().get("jobs") or [])[: max_results * 2]:
                jobs.append({
                    "title": j.get("title", ""),
                    "company": j.get("company_name", ""),
                    "location": j.get("candidate_required_location") or "Remote",
                    "description": _strip_html(j.get("description", ""))[:600],
                    "job_url": j.get("url", ""),
                    "platform": "remotive",
                })
        except Exception as exc:
            logger.warning("Remotive API failed: %s", exc)

        # 2) Arbeitnow — recent ATS-sourced board; filter client-side by query.
        try:
            r = client.get("https://www.arbeitnow.com/api/job-board-api")
            for j in (r.json().get("data") or []):
                title = j.get("title", "")
                tags = " ".join(j.get("tags") or [])
                if not _relevant(f"{title} {tags} {j.get('description','')[:300]}"):
                    continue
                jobs.append({
                    "title": title,
                    "company": j.get("company_name", ""),
                    "location": j.get("location") or ("Remote" if j.get("remote") else ""),
                    "description": _strip_html(j.get("description", ""))[:600],
                    "job_url": j.get("url", ""),
                    "platform": "arbeitnow",
                })
        except Exception as exc:
            logger.warning("Arbeitnow API failed: %s", exc)

        # 3) Jobicy — remote jobs feed, tag-filtered.
        try:
            r = client.get("https://jobicy.com/api/v2/remote-jobs",
                           params={"count": max_results, "tag": first_term})
            for j in (r.json().get("jobs") or []):
                jobs.append({
                    "title": j.get("jobTitle", ""),
                    "company": j.get("companyName", ""),
                    "location": j.get("jobGeo") or "Remote",
                    "description": _strip_html(j.get("jobExcerpt", ""))[:600],
                    "job_url": j.get("url", ""),
                    "platform": "jobicy",
                })
        except Exception as exc:
            logger.warning("Jobicy API failed: %s", exc)

    # Keep only jobs with a real apply link, then dedupe.
    jobs = [j for j in jobs if j.get("job_url") and j.get("title")]
    return _dedupe_jobs(jobs, max_results)


def job_search_agent_node(state: AgentState) -> AgentState:
    session = None
    try:
        user_id = state["user_id"]
        ctx = state["context"]
        query = ctx.get("search_query", "software engineer")
        location = ctx.get("location", "Remote")
        work_mode = ctx.get("work_mode", "")
        max_results = min(int(ctx.get("max_results", 10)), 25)
        live_browser = bool(ctx.get("live_browser", False))
        run_id = state["run_id"]

        model_settings = fetch_model_settings(user_id)
        if not model_settings:
            raise ValueError("No active model settings configured for user")

        resume_profile = fetch_user_profile_text(user_id)
        preference_profile = _fetch_job_preference_text(user_id)
        user_profile = "\n\n".join(part for part in (preference_profile, resume_profile) if part)
        llm = _build_llm(model_settings)

        # Note: per-job LLM scoring and the pre-scoring "thinking" model step were
        # removed from the hot path — they added one slow/rate-limited model call per
        # job and blew past the run timeout. Real listings are scored heuristically.

        jobs_raw: list[dict] = []
        emit(run_id, "browser", {
            "phase": "search_start",
            "mode": "visible" if live_browser else "headless",
            "query": query,
            "location": location,
            "work_mode": work_mode,
        })

        google_jobs_tried = False

        # Primary source: free key-less job-board APIs (Remotive/Arbeitnow/Jobicy).
        # Real listings with real apply links, no scraping or rate-limited engines.
        if not jobs_raw and not live_browser:
            try:
                jobs_raw = _run_sync_with_timeout(
                    _search_open_job_apis, query, location, max_results,
                    timeout_sec=SOURCE_TIMEOUT_SEC,
                )
                if jobs_raw:
                    emit(run_id, "browser", {"phase": "open_apis_done",
                                             "source": "remotive+arbeitnow+jobicy",
                                             "count": len(jobs_raw)})
            except Exception as exc:
                logger.warning("Open job APIs failed: %s", exc)
                emit(run_id, "browser", {"phase": "open_apis_failed", "error": "Job APIs unavailable"})

        # Secondary source when configured: SearXNG meta-search (JSON, no CAPTCHA,
        # honors dork queries). Works in headless and live-browser modes.
        if not jobs_raw and app_settings.SEARXNG_URL:
            jobs_raw = _run_sync_with_timeout(
                _search_searxng_jobs, query, location, max_results,
                timeout_sec=SOURCE_TIMEOUT_SEC,
            )
            if jobs_raw:
                emit(run_id, "browser", {"phase": "searxng_done", "count": len(jobs_raw)})
        if live_browser:
            # Prefer AgentQL (robust extraction) when a key is configured.
            if app_settings.AGENTQL_API_KEY:
                jobs_raw = _run_async_result(
                    _search_agentql_jobs_browser(
                        query=query,
                        location=location,
                        max_results=max_results,
                        run_id=run_id,
                        live_browser=True,
                    ),
                    timeout_sec=SOURCE_TIMEOUT_SEC,
                )
            if not jobs_raw:
                google_jobs_tried = True
                try:
                    emit(
                        run_id,
                        "browser",
                        {
                            "phase": "visible_browser_opening",
                            "source": "google_jobs",
                            "message": "Opening a visible browser for live job search",
                        },
                    )
                    jobs_raw = _search_google_jobs_source(
                        llm=llm,
                        user_id=user_id,
                        query=query,
                        location=location,
                        max_results=max_results,
                        live_browser=True,
                        run_id=run_id,
                    )
                    emit(
                        run_id,
                        "browser",
                        {
                            "phase": "visible_browser_done",
                            "source": "google_jobs",
                            "count": len(jobs_raw),
                        },
                    )
                    if not jobs_raw:
                        emit(
                            run_id,
                            "browser",
                            {
                                "phase": "visible_browser_retry",
                                "source": "remoteok",
                                "reason": "google_jobs_empty_or_blocked",
                            },
                        )
                        jobs_raw = _run_async_result(
                            _search_remoteok_jobs_browser(
                                query=query,
                                max_results=max_results,
                                run_id=run_id,
                                live_browser=True,
                            ),
                            timeout_sec=SOURCE_TIMEOUT_SEC,
                        )
                except Exception as google_exc:
                    logger.warning("Visible Google Jobs search failed (%s) - trying JobSpy", google_exc)
                    emit(
                        run_id,
                        "browser",
                        {
                            "phase": "visible_browser_failed",
                            "error": "Visible browser search failed",
                        },
                    )

        try:
            if not jobs_raw:
                # Primary headless source; live-browser searches try Google first so users see the crawl.
                from app.services.job_platforms_service import scrape_jobs as jobspy_scrape
                job_listings = _run_sync_with_timeout(
                    jobspy_scrape,
                    search_term=query,
                    location=location,
                    results_wanted=max_results,
                    hours_old=72,
                )
                jobs_raw = _job_listings_to_dicts(job_listings)
                emit(run_id, "browser", {"phase": "jobspy_done", "count": len(jobs_raw)})
        except Exception as jobspy_exc:
            logger.warning("JobSpy unavailable (%s) — trying Google Jobs", jobspy_exc)
            emit(
                run_id,
                "browser",
                {"phase": "jobspy_failed", "error": "JobSpy search failed"},
            )

        if not jobs_raw and not google_jobs_tried:
            try:
                jobs_raw = _search_google_jobs_source(
                    llm=llm,
                    user_id=user_id,
                    query=query,
                    location=location,
                    max_results=max_results,
                    live_browser=False,
                    run_id=run_id,
                )
            except Exception as google_exc:
                logger.warning("Google Jobs unavailable (%s) — falling through to ATS", google_exc)
                emit(
                    run_id,
                    "browser",
                    {
                        "phase": "google_jobs_failed",
                        "error": "Google Jobs search failed",
                    },
                )

        if not jobs_raw:
            try:
                emit(run_id, "browser", {"phase": "public_ats_search", "source": "greenhouse+lever"})
                jobs_raw = _run_sync_with_timeout(
                    _search_public_ats_jobs,
                    query,
                    location,
                    max_results,
                    work_mode,
                    timeout_sec=SOURCE_TIMEOUT_SEC,
                )
                emit(
                    run_id,
                    "browser",
                    {"phase": "public_ats_done", "source": "greenhouse+lever", "count": len(jobs_raw)},
                )
            except Exception as ats_exc:
                logger.warning("Public ATS search unavailable (%s) — trying RemoteOK", ats_exc)
                emit(
                    run_id,
                    "browser",
                    {
                        "phase": "public_ats_failed",
                        "error": "Public ATS search failed",
                    },
                )

        work_modes = {
            item.strip().lower()
            for item in (work_mode or "").split(",")
            if item.strip()
        }
        remote_search_allowed = not work_modes or "remote" in work_modes or location.lower() == "remote"
        if not jobs_raw and remote_search_allowed:
            try:
                emit(run_id, "browser", {"phase": "remoteok_search", "source": "remoteok"})
                jobs_raw = _search_remoteok_jobs(query, max_results)
                emit(
                    run_id,
                    "browser",
                    {"phase": "remoteok_done", "source": "remoteok", "count": len(jobs_raw)},
                )
            except Exception as remoteok_exc:
                logger.warning("RemoteOK unavailable (%s) — no remaining sources", remoteok_exc)
                emit(
                    run_id,
                    "browser",
                    {"phase": "remoteok_failed", "error": "RemoteOK search failed"},
                )
        elif not jobs_raw:
            emit(
                run_id,
                "browser",
                {"phase": "remoteok_skipped", "reason": f"work_mode={work_mode or 'unspecified'}"},
            )

        if not jobs_raw:
            # All remote APIs (Google Jobs, Greenhouse/Lever ATS, RemoteOK)
            # returned no results. The browser-use fallback (browser_control_service)
            # is the primary modern path and is invoked from the orchestrator; here
            # we honestly report zero results rather than mock data.
            emit(run_id, "browser", {"phase": "all_sources_empty", "sources_tried": ["google_jobs", "ats", "remoteok"]})

        # Score real listings with the fast deterministic heuristic. Per-job LLM
        # scoring is skipped here on purpose: with a rate-limited/slow model it adds
        # one network round-trip per job and pushes the whole run past its timeout.
        # The heuristic is a real keyword/skills-overlap score on the real jobs.
        scored = [
            {**job, "match_score": _heuristic_score_job(job, user_profile)}
            for job in jobs_raw
        ]
        scored.sort(key=lambda j: j["match_score"], reverse=True)

        top = scored[0] if scored else {}
        summary = (
            f"Found {len(scored)} jobs. Top match: {top.get('title')} at "
            f"{top.get('company')} ({top.get('match_score')}%)"
            if scored
            else "No jobs found."
        )

        return {
            **state,
            "status": "completed",
            "result": {"matches": scored, "total_found": len(jobs_raw)},
            "messages": state["messages"] + [AIMessage(content=summary)],
        }
    except Exception as exc:
        logger.error("Job search agent failed for user %s: %s", state.get("user_id"), exc)
        return {**state, "status": "failed", "error": "Agent failed"}
    finally:
        if session:
            session.close()
