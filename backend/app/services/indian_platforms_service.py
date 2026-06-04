"""
indian_platforms_service.py — Browser-use scrapers for Indian job platforms.

Platforms: Naukri, Foundit, Instahyre, Cutshort, Hirect, Internshala,
           Shine, iimjobs, Freshersworld.

Uses browser-use (AI-driven Playwright) to scrape job listings from platforms
that JobSpy doesn't support natively.
"""
import asyncio
import logging
import secrets
from dataclasses import dataclass
from urllib.parse import quote_plus

from langchain_core.language_models import BaseChatModel

from app.core.event_bus import emit
from app.services.browser_control_service import run_browser_task
from app.services.job_platforms_service import JobListing

logger = logging.getLogger(__name__)
_RANDOM = secrets.SystemRandom()

# Platform search URL templates — {query} and {location} are replaced at runtime
INDIAN_PLATFORMS = {
    "naukri": {
        "name": "Naukri",
        "search_url": "https://www.naukri.com/{query}-jobs-in-{location}",
        "url": "https://www.naukri.com",
    },
    "foundit": {
        "name": "Foundit",
        "search_url": "https://www.foundit.in/srp/results?query={query}&locations={location}",
        "url": "https://www.foundit.in",
    },
    "instahyre": {
        "name": "Instahyre",
        "search_url": "https://www.instahyre.com/search-jobs/?search={query}&location={location}",
        "url": "https://www.instahyre.com",
    },
    "cutshort": {
        "name": "Cutshort",
        "search_url": "https://cutshort.io/jobs?q={query}&city={location}",
        "url": "https://cutshort.io",
    },
    "hirect": {
        "name": "Hirect",
        "search_url": "https://www.hirect.in/jobs?keyword={query}&location={location}",
        "url": "https://www.hirect.in",
    },
    "internshala": {
        "name": "Internshala",
        "search_url": "https://internshala.com/jobs/{query}-jobs-in-{location}",
        "url": "https://internshala.com",
    },
    "shine": {
        "name": "Shine",
        "search_url": "https://www.shine.com/job-search/{query}-jobs-in-{location}",
        "url": "https://www.shine.com",
    },
    "iimjobs": {
        "name": "iimjobs",
        "search_url": "https://www.iimjobs.com/search?q={query}&l={location}",
        "url": "https://www.iimjobs.com",
    },
    "freshersworld": {
        "name": "Freshersworld",
        "search_url": "https://www.freshersworld.com/jobs?q={query}&city={location}",
        "url": "https://www.freshersworld.com",
    },
}

# Extraction prompt template for the browser-use agent
_EXTRACT_PROMPT = """Go to {url}.
Wait for job listings to load. Extract up to {limit} job listings visible on the page.
For each job, extract: title, company name, location, job URL, and a brief description (first 200 chars).
Return the results as a structured list in this exact format (one per line):
TITLE: <title> | COMPANY: <company> | LOCATION: <location> | URL: <url> | DESC: <description>

If there are no results, return "NO_RESULTS".
Do NOT click on individual jobs — only extract what's visible on the search results page."""


async def _human_delay():
    """Random delay to mimic human browsing (2-5s)."""
    await asyncio.sleep(_RANDOM.uniform(2.0, 5.0))


async def scrape_indian_platform(
    llm: BaseChatModel,
    user_id: str,
    platform: str,
    search_term: str,
    location: str = "bangalore",
    results_wanted: int = 10,
) -> list[JobListing]:
    """Scrape jobs from a single Indian platform using browser-use.

    Args:
        llm: LLM for browser agent decision-making
        user_id: User ID for persistent browser session
        platform: Platform key (e.g., "naukri", "foundit")
        search_term: Job search keywords
        location: City/location filter
        results_wanted: Max results to extract

    Returns:
        List of JobListing objects
    """
    if platform not in INDIAN_PLATFORMS:
        logger.warning("Unknown platform: %s", platform)
        return []

    config = INDIAN_PLATFORMS[platform]
    query_slug = search_term.lower().replace(" ", "-")
    location_slug = location.lower().replace(" ", "-")
    search_url = config["search_url"].format(query=query_slug, location=location_slug)

    task = _EXTRACT_PROMPT.format(url=search_url, limit=results_wanted)

    try:
        await _human_delay()
        raw_text = await run_browser_task(llm, task, user_id, max_steps=10)
        return _parse_extraction_result(raw_text, platform)
    except Exception as exc:
        logger.error("Failed to scrape %s: %s", platform, exc)
        return []


def _parse_extraction_result(raw_text: str, platform: str) -> list[JobListing]:
    """Parse the structured text output from browser-use agent into JobListing objects."""
    if not raw_text or "NO_RESULTS" in raw_text:
        return []

    jobs: list[JobListing] = []
    for line in raw_text.strip().split("\n"):
        line = line.strip()
        if not line or "TITLE:" not in line:
            continue
        try:
            parts = {}
            for segment in line.split(" | "):
                if ":" in segment:
                    key, val = segment.split(":", 1)
                    parts[key.strip().upper()] = val.strip()

            if parts.get("TITLE"):
                jobs.append(JobListing(
                    title=parts.get("TITLE", ""),
                    company=parts.get("COMPANY", "Unknown"),
                    location=parts.get("LOCATION", ""),
                    description=parts.get("DESC", "")[:2000],
                    job_url=parts.get("URL", ""),
                    platform=platform,
                ))
        except Exception as exc:
            logger.debug("Skipping unparsable %s job line: %s", platform, exc)
            continue

    return jobs


def _job_from_card_text(raw_text: str, fallback_url: str) -> JobListing | None:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    lines = [line for line in lines if line.lower() not in {"new", "via linkedin", "via indeed"}]
    if len(lines) < 2:
        return None

    title = lines[0]
    company = lines[1] if len(lines) > 1 else "Unknown"
    location = lines[2] if len(lines) > 2 else ""
    description = " ".join(lines[3:8])[:2000]
    return JobListing(
        title=title,
        company=company,
        location=location,
        description=description,
        job_url=fallback_url,
        platform="google_jobs",
    )


async def _search_google_jobs_playwright(
    user_id: str,
    search_term: str,
    location: str,
    results_wanted: int,
    live_browser: bool,
    run_id: str | None,
) -> list[JobListing]:
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        logger.error("Playwright is required for Google Jobs fallback: %s", exc)
        return []

    from app.services.browser_control_service import BROWSER_DATA_DIR

    query = quote_plus(f"{search_term} jobs in {location}")
    url = f"https://www.google.com/search?q={query}&ibp=htl;jobs"
    user_dir = BROWSER_DATA_DIR / user_id / "google_jobs"
    user_dir.mkdir(parents=True, exist_ok=True)

    if run_id:
        emit(run_id, "browser", {
            "phase": "navigate",
            "mode": "visible" if live_browser else "headless",
            "url": url,
            "task": "Search Google Jobs with Playwright",
        })

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=not live_browser,
            viewport={"width": 1366, "height": 900},
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await page.wait_for_timeout(5000 if live_browser else 2500)
            if run_id:
                emit(run_id, "browser", {"phase": "extracting", "source": "google_jobs"})

            jobs: list[JobListing] = []
            cards = page.locator('div[role="treeitem"]')
            count = await cards.count()
            for index in range(min(count, results_wanted)):
                try:
                    raw = await cards.nth(index).inner_text(timeout=1500)
                except Exception as exc:
                    logger.debug("Skipping Google Jobs card %s: %s", index, exc)
                    continue
                job = _job_from_card_text(raw, url)
                if job:
                    jobs.append(job)

            if run_id:
                emit(run_id, "browser", {"phase": "extracted", "source": "google_jobs", "count": len(jobs)})
            if live_browser:
                await page.wait_for_timeout(5000)
            return jobs
        except Exception as exc:
            logger.error("Google Jobs Playwright fallback failed: %s", exc)
            if run_id:
                emit(
                    run_id,
                    "browser",
                    {
                        "phase": "failed",
                        "source": "google_jobs",
                        "error": "Google Jobs search failed",
                    },
                )
            return []
        finally:
            await context.close()
            if run_id:
                emit(run_id, "browser", {"phase": "closed", "source": "google_jobs"})


async def scrape_all_indian_platforms(
    llm: BaseChatModel,
    user_id: str,
    search_term: str,
    location: str = "bangalore",
    results_wanted: int = 10,
    platforms: list[str] | None = None,
) -> list[JobListing]:
    """Scrape jobs from multiple Indian platforms concurrently.

    Args:
        llm: LLM for browser agent
        user_id: User ID
        search_term: Job keywords
        location: City filter
        results_wanted: Max results per platform
        platforms: Specific platforms to scrape (default: all)

    Returns:
        Combined list of JobListing from all platforms
    """
    target = platforms or list(INDIAN_PLATFORMS.keys())
    tasks = [
        scrape_indian_platform(llm, user_id, p, search_term, location, results_wanted)
        for p in target
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_jobs: list[JobListing] = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning("Platform %s failed: %s", target[i], result)
        elif isinstance(result, list):
            all_jobs.extend(result)

    logger.info("Indian platforms: found %d jobs across %d platforms", len(all_jobs), len(target))
    return all_jobs


async def login_to_platform(
    llm: BaseChatModel,
    user_id: str,
    platform: str,
    email: str,
    password: str,
) -> str:
    """Login to an Indian job platform. Cookies are persisted for future scraping.

    Credentials are filled directly through Playwright so they never enter an
    LLM prompt, SSE event, or provider-side trace.
    """
    del llm

    if platform not in INDIAN_PLATFORMS:
        return f"Unknown platform: {platform}"

    config = INDIAN_PLATFORMS[platform]
    login_urls = {
        "naukri": "https://www.naukri.com/nlogin/login",
        "foundit": "https://www.foundit.in/login",
        "instahyre": "https://www.instahyre.com/login/",
        "internshala": "https://internshala.com/login",
    }
    login_url = login_urls.get(platform, config["url"])

    try:
        from playwright.async_api import TimeoutError as PlaywrightTimeoutError
        from playwright.async_api import async_playwright
    except ImportError as exc:  # pragma: no cover - dependency is optional in some test envs
        raise RuntimeError("Playwright is required for secure platform login") from exc

    from app.services.browser_control_service import BROWSER_DATA_DIR

    user_dir = BROWSER_DATA_DIR / user_id / platform
    user_dir.mkdir(parents=True, exist_ok=True)
    email_selectors = (
        'input[type="email"], input[name*="email" i], input[name*="user" i], '
        'input[id*="email" i], input[id*="user" i], input[type="text"]'
    )
    # CSS selectors for password fields, not stored credentials.
    password_selectors = (
        'input[type="password"], input[name*="password" i], input[id*="password" i]'  # noqa: S105  # nosec B105
    )
    submit_selectors = 'button[type="submit"], input[type="submit"], button:has-text("Login"), button:has-text("Sign in")'

    async with async_playwright() as p:
        context = await p.chromium.launch_persistent_context(
            user_data_dir=str(user_dir),
            headless=True,
        )
        page = context.pages[0] if context.pages else await context.new_page()
        try:
            await page.goto(login_url, wait_until="domcontentloaded")
            await _human_delay()
            await page.locator(email_selectors).first.fill(email)
            await page.locator(password_selectors).first.fill(password)
            await page.locator(submit_selectors).first.click()
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                pass
            page_text = (await page.locator("body").inner_text(timeout=5000)).lower()
            if any(marker in page_text for marker in ("captcha", "otp", "verification code")):
                return f"{config['name']} security challenge requires manual review"
            return f"{config['name']} login submitted"
        finally:
            await context.close()


def get_indian_platforms() -> list[dict]:
    """Return list of supported Indian job platforms."""
    return [
        {"name": v["name"], "id": k, "status": "active", "url": v["url"]}
        for k, v in INDIAN_PLATFORMS.items()
    ]


async def search_google_jobs(
    llm: BaseChatModel,
    user_id: str,
    search_term: str,
    location: str = "India",
    results_wanted: int = 15,
    live_browser: bool = False,
    run_id: str | None = None,
) -> list[JobListing]:
    """Search Google Jobs (google.com/jobs) via browser-use.

    Google indexes jobs from company career pages that aren't on any job board.
    This catches roles that only exist on company websites.

    Args:
        llm: LLM for browser agent
        user_id: User ID for persistent session
        search_term: Job keywords (e.g., "Senior Python Developer")
        location: Location filter
        results_wanted: Max results to extract

    Returns:
        List of JobListing from Google Jobs
    """
    query = f"{search_term} jobs in {location}".replace(" ", "+")
    url = f"https://www.google.com/search?q={query}&ibp=htl;jobs"

    task = (
        f"Go to {url}. "
        f"Wait for the Google Jobs panel to load on the left side. "
        f"Extract up to {results_wanted} job listings from the panel. "
        f"For each job, extract: title, company name, location, and the job URL (click to get it). "
        f"Return results in this format (one per line): "
        f"TITLE: <title> | COMPANY: <company> | LOCATION: <location> | URL: <url> | DESC: <brief description>"
        f"\nIf no jobs panel appears, return NO_RESULTS."
    )

    if run_id:
        emit(run_id, "browser", {
            "phase": "navigate",
            "mode": "visible" if live_browser else "headless",
            "url": url,
            "task": "Search Google Jobs for real-time job listings",
        })

    try:
        await _human_delay()
        if run_id:
            emit(run_id, "browser", {"phase": "extracting", "source": "google_jobs"})
        raw_text = await run_browser_task(
            llm, task, user_id, max_steps=12, live_browser=live_browser, run_id=run_id
        )
        jobs = _parse_extraction_result(raw_text, "google_jobs")
        if run_id:
            emit(run_id, "browser", {"phase": "extracted", "source": "google_jobs", "count": len(jobs)})
        return jobs
    except Exception as exc:
        logger.error("Google Jobs search failed: %s", exc)
        return await _search_google_jobs_playwright(
            user_id=user_id,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            live_browser=live_browser,
            run_id=run_id,
        )
