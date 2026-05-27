"""
indian_platforms_service.py — Browser-use scrapers for Indian job platforms.

Platforms: Naukri, Foundit, Instahyre, Cutshort, Hirect, Internshala,
           Shine, iimjobs, Freshersworld.

Uses browser-use (AI-driven Playwright) to scrape job listings from platforms
that JobSpy doesn't support natively.
"""
import asyncio
import logging
import random
from dataclasses import dataclass

try:
    from browser_use import Agent, Browser, BrowserConfig
    BROWSER_USE_AVAILABLE = True
except ImportError:
    BROWSER_USE_AVAILABLE = False
    Agent = Browser = BrowserConfig = None  # type: ignore
from langchain_core.language_models import BaseChatModel

from app.services.browser_control_service import _get_browser_config
from app.services.job_platforms_service import JobListing

logger = logging.getLogger(__name__)

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
    await asyncio.sleep(random.uniform(2.0, 5.0))


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

    browser_config = _get_browser_config(user_id)
    browser = Browser(config=browser_config)
    agent = Agent(task=task, llm=llm, browser=browser, max_actions_per_step=3)

    try:
        await _human_delay()
        result = await agent.run(max_steps=10)
        raw_text = result.final_result() if result else ""
        return _parse_extraction_result(raw_text, platform)
    except Exception as exc:
        logger.error("Failed to scrape %s: %s", platform, exc)
        return []
    finally:
        await browser.close()


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
        except Exception:
            continue

    return jobs


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
    """Login to an Indian job platform. Cookies are persisted for future scraping."""
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

    task = (
        f"Go to {login_url}. "
        f"Enter email '{email}' and password '{password}'. "
        f"Click the login/sign-in button. Wait for the page to load. "
        f"If there's a CAPTCHA or OTP, stop and report it."
    )

    browser_config = _get_browser_config(user_id)
    browser = Browser(config=browser_config)
    agent = Agent(task=task, llm=llm, browser=browser, max_actions_per_step=3)

    try:
        await _human_delay()
        result = await agent.run(max_steps=10)
        return result.final_result() if result else "Login attempted"
    finally:
        await browser.close()


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

    browser_config = _get_browser_config(user_id)
    browser = Browser(config=browser_config)
    agent = Agent(task=task, llm=llm, browser=browser, max_actions_per_step=3)

    try:
        await _human_delay()
        result = await agent.run(max_steps=12)
        raw_text = result.final_result() if result else ""
        return _parse_extraction_result(raw_text, "google_jobs")
    except Exception as exc:
        logger.error("Google Jobs search failed: %s", exc)
        return []
    finally:
        await browser.close()
