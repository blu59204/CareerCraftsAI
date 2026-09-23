"""
company_careers_service.py — Direct career-page scraping for 16 companies.

Unlike the Indian platforms (Naukri/LinkedIn/Indeed) which need a search
query, the 10 Indian IT companies + 6 global AI labs in
``search_presets.COMPANY_CAREER_PAGES`` publish their own career feeds. We
hit each URL directly with browser-use, extract job titles + apply links
with a structured ``TITLE | COMPANY | LOCATION | URL`` prompt, and surface
them as :class:`CareerJob` objects — same shape as
``indian_platforms_service.JobListing`` so the rest of the pipeline doesn't
care where the job came from.

The orchestrator lives in :func:`scrape_all_company_careers`; it fans out
across all 16 companies in parallel (bounded by ``max_concurrent``) and
dedupes by URL. Per-company errors are logged and skipped, never raised.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Any

from app.services.search_presets import (
    COMPANY_CAREER_PAGES,
    CompanyCareer,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Data model — mirrors JobListing in indian_platforms_service.py
# ---------------------------------------------------------------------------


@dataclass
class CareerJob:
    title: str
    company: str
    location: str = ""
    description: str = ""
    job_url: str = ""
    department: str = ""
    posted_at: str = ""
    platform: str = "company_career"

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "description": self.description,
            "job_url": self.job_url,
            "department": self.department,
            "posted_at": self.posted_at,
            "platform": self.platform,
        }


# ---------------------------------------------------------------------------
# Helpers — look up by name (case-insensitive)
# ---------------------------------------------------------------------------


def _find_company(name: str) -> CompanyCareer | None:
    """Look up a company in COMPANY_CAREER_PAGES by name (case-insensitive)."""
    needle = name.strip().lower()
    for c in COMPANY_CAREER_PAGES:
        if c.get("name", "").strip().lower() == needle:
            return c
    return None


def list_company_names() -> list[str]:
    """Return all company names known to the career-page catalog."""
    return [c.get("name", "") for c in COMPANY_CAREER_PAGES if c.get("name")]


# ---------------------------------------------------------------------------
# Extraction prompt — same TITLE | ... format as indian_platforms_service
# ---------------------------------------------------------------------------


_EXTRACT_CAREER_PROMPT = """\
You are browsing {url} which is the public career page of {company}.

Your task: extract up to {limit} currently-open job listings.

For EACH job, output a SINGLE LINE in EXACTLY this format:
  TITLE: <role title> | COMPANY: {company} | LOCATION: <city or "Remote"> | URL: <full apply URL>

If you cannot find any job listings, output a single line:
  NO_RESULTS

If you hit a CAPTCHA, login wall, or rate-limit, output:
  BLOCKED: <reason>

Important:
- Prefer canonical apply URLs (/careers/job/{{id}} or full absolute links).
- Do NOT include closed/expired roles.
- Do NOT include generic pages (about us, contact, press).
- Keep titles to 80 chars max — no descriptions, no responsibilities.
"""


# ---------------------------------------------------------------------------
# Single-company scraper
# ---------------------------------------------------------------------------


async def scrape_company_career_page(
    llm,
    user_id: str,
    company_name: str,
    results_wanted: int = 10,
    max_steps: int = 8,
) -> list[CareerJob]:
    """Scrape one company's career page via browser-use.

    Args:
        llm: BYOK LLM (LangChain ``BaseChatModel``).
        user_id: User ID for persistent browser session.
        company_name: Display name (e.g. ``"TCS"``, ``"Google"``,
            ``"Infosys"``). Matched case-insensitively.
        results_wanted: Max jobs to extract.
        max_steps: browser-use agent max steps.

    Returns:
        List of :class:`CareerJob`. Empty on error, CAPTCHA, or no results.
    """
    entry = _find_company(company_name)
    if not entry:
        logger.warning("Unknown company name: %s", company_name)
        return []

    url = entry.get("url", "")
    company = entry.get("name", company_name)
    if not url:
        return []

    task = _EXTRACT_CAREER_PROMPT.format(
        url=url, company=company, limit=results_wanted,
    )

    try:
        from app.services.browser_control_service import (
            run_browser_task_with_captcha_retry,
        )
        raw = await run_browser_task_with_captcha_retry(
            llm, task, user_id, max_steps=max_steps, live_browser=False,
        )
    except Exception as exc:
        # CaptchaBlocked, browser crash, network error — log and skip.
        logger.warning("scrape_company_career_page(%s) failed: %s", company_name, exc)
        return []

    return _parse_career_extraction(raw, company)


# ---------------------------------------------------------------------------
# Parser — same shape as indian_platforms_service._parse_extraction_result
# ---------------------------------------------------------------------------


def _parse_career_extraction(raw_text: str, company: str) -> list[CareerJob]:
    if not raw_text or "NO_RESULTS" in raw_text:
        return []
    if "BLOCKED:" in raw_text and len(raw_text) < 200:
        logger.info("Company %s blocked: %s", company, raw_text.strip())
        return []

    out: list[CareerJob] = []
    for line in raw_text.strip().splitlines():
        line = line.strip()
        if not line or "TITLE:" not in line:
            continue
        parts: dict[str, str] = {}
        for seg in line.split(" | "):
            if ":" in seg:
                k, v = seg.split(":", 1)
                parts[k.strip().upper()] = v.strip()
        title = parts.get("TITLE", "").strip()
        if not title or len(title) < 3:
            continue
        out.append(CareerJob(
            title=title[:120],
            company=parts.get("COMPANY", company),
            location=parts.get("LOCATION", ""),
            description="",
            job_url=parts.get("URL", ""),
            platform="company_career",
        ))
    return out


# ---------------------------------------------------------------------------
# Fan-out orchestrator
# ---------------------------------------------------------------------------


async def scrape_all_company_careers(
    llm,
    user_id: str,
    companies: list[str] | None = None,
    results_per_company: int = 5,
    max_concurrent: int = 3,
) -> list[CareerJob]:
    """Fan out across multiple company career pages in parallel.

    Args:
        llm: BYOK LLM.
        user_id: User ID.
        companies: List of company names (e.g. ``["TCS", "Google"]``).
            Defaults to all companies in
            ``search_presets.COMPANY_CAREER_PAGES``.
        results_per_company: Max jobs per company.
        max_concurrent: Parallel browser sessions (1-3; high values may
            trigger IP-based rate limits).

    Returns:
        Deduplicated list of :class:`CareerJob` sorted by company then title.
    """
    names = companies or list_company_names()
    names = [n for n in names if _find_company(n)]
    if not names:
        return []

    sem = asyncio.Semaphore(max(1, max_concurrent))

    async def _run(name: str) -> list[CareerJob]:
        async with sem:
            return await scrape_company_career_page(
                llm, user_id, name, results_wanted=results_per_company,
            )

    results = await asyncio.gather(*[_run(n) for n in names], return_exceptions=True)
    out: list[CareerJob] = []
    for name, r in zip(names, results):
        if isinstance(r, Exception):
            logger.warning("Company %s scrape raised: %s", name, r)
            continue
        out.extend(r)
    return _dedupe_career_jobs(out)


# ---------------------------------------------------------------------------
# Dedupe
# ---------------------------------------------------------------------------


def _normalize_url(url: str) -> str:
    """Drop query strings + fragments for dedupe key."""
    if not url:
        return ""
    return url.split("?")[0].split("#")[0]


def _dedupe_career_jobs(jobs: list[CareerJob]) -> list[CareerJob]:
    seen: set[str] = set()
    out: list[CareerJob] = []
    for j in jobs:
        key = _normalize_url(j.job_url) or f"{j.company}::{j.title.lower()}"
        if key in seen:
            continue
        seen.add(key)
        out.append(j)
    return out
