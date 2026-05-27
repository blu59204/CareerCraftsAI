"""
job_platforms_service.py — Multi-platform job scraping via JobSpy + Indian platforms.

JobSpy: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Wellfound.
Indian (browser-use): Naukri, Foundit, Instahyre, Cutshort, Hirect, Internshala, Shine, iimjobs, Freshersworld.
"""
import asyncio
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class JobListing:
    title: str
    company: str
    location: str
    description: str
    job_url: str
    platform: str
    date_posted: str | None = None
    salary: str | None = None


# JobSpy-supported platforms
JOBSPY_PLATFORMS = ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]

# Indian platforms requiring browser-use
INDIAN_BROWSER_PLATFORMS = [
    "naukri", "foundit", "instahyre", "cutshort",
    "hirect", "internshala", "shine", "iimjobs", "freshersworld",
]

ALL_PLATFORMS = JOBSPY_PLATFORMS + INDIAN_BROWSER_PLATFORMS


def scrape_jobs(
    search_term: str,
    location: str = "Remote",
    results_wanted: int = 20,
    hours_old: int = 72,
    platforms: list[str] | None = None,
    country: str = "India",
) -> list[JobListing]:
    """Scrape jobs from JobSpy-supported platforms.

    Args:
        search_term: Job title/keywords to search
        location: Location filter
        results_wanted: Max results per platform
        hours_old: Only jobs posted within this many hours
        platforms: List of platforms to scrape (default: all JobSpy platforms)
        country: Country for Indeed/Google localization

    Returns:
        List of JobListing objects from all platforms combined.
    """
    from jobspy import scrape_jobs as jobspy_scrape

    target_platforms = platforms or JOBSPY_PLATFORMS

    try:
        df = jobspy_scrape(
            site_name=target_platforms,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            hours_old=hours_old,
            country_indeed=country,
            linkedin_fetch_description=True,
        )

        if df is None or df.empty:
            logger.info("JobSpy returned no results for '%s' in '%s'", search_term, location)
            return []

        jobs: list[JobListing] = []
        for _, row in df.iterrows():
            jobs.append(JobListing(
                title=str(row.get("title", "")),
                company=str(row.get("company", "")),
                location=str(row.get("location", location)),
                description=str(row.get("description", ""))[:2000],
                job_url=str(row.get("job_url", "")),
                platform=str(row.get("site", "unknown")),
                date_posted=str(row.get("date_posted", "")) if row.get("date_posted") else None,
                salary=str(row.get("min_amount", "")) if row.get("min_amount") else None,
            ))

        logger.info("JobSpy found %d jobs across %s for '%s'", len(jobs), target_platforms, search_term)
        return jobs

    except Exception as exc:
        logger.error("JobSpy scraping failed for '%s': %s", search_term, exc)
        return []


async def scrape_all_platforms(
    search_term: str,
    location: str = "Bangalore",
    results_wanted: int = 20,
    hours_old: int = 72,
    include_indian: bool = True,
    indian_platforms: list[str] | None = None,
    llm=None,
    user_id: str | None = None,
) -> list[JobListing]:
    """Scrape from both JobSpy and Indian browser-use platforms.

    Args:
        search_term: Job keywords
        location: Location filter
        results_wanted: Max results per platform
        hours_old: Max age for JobSpy results
        include_indian: Whether to include Indian browser-use platforms
        indian_platforms: Specific Indian platforms (default: all)
        llm: LLM instance (required for Indian platforms)
        user_id: User ID (required for Indian platforms)

    Returns:
        Combined job listings from all sources.
    """
    # JobSpy results (sync, run in executor)
    loop = asyncio.get_event_loop()
    jobspy_jobs = await loop.run_in_executor(
        None, scrape_jobs, search_term, location, results_wanted, hours_old, None, "India"
    )

    # Indian platforms (async, browser-use)
    indian_jobs: list[JobListing] = []
    if include_indian and llm and user_id:
        from app.services.indian_platforms_service import scrape_all_indian_platforms
        indian_jobs = await scrape_all_indian_platforms(
            llm=llm,
            user_id=user_id,
            search_term=search_term,
            location=location,
            results_wanted=results_wanted,
            platforms=indian_platforms,
        )

    combined = jobspy_jobs + indian_jobs
    logger.info("Total jobs found: %d (JobSpy: %d, Indian: %d)", len(combined), len(jobspy_jobs), len(indian_jobs))
    return combined


def get_active_platforms() -> list[dict]:
    """Return list of all supported job platforms with status."""
    return [
        {"name": "LinkedIn", "id": "linkedin", "status": "active", "url": "https://linkedin.com/jobs", "method": "jobspy"},
        {"name": "Indeed", "id": "indeed", "status": "active", "url": "https://indeed.com", "method": "jobspy"},
        {"name": "Glassdoor", "id": "glassdoor", "status": "active", "url": "https://glassdoor.com", "method": "jobspy"},
        {"name": "Google Jobs", "id": "google", "status": "active", "url": "https://google.com/jobs", "method": "jobspy"},
        {"name": "ZipRecruiter", "id": "zip_recruiter", "status": "active", "url": "https://ziprecruiter.com", "method": "jobspy"},
        {"name": "Naukri", "id": "naukri", "status": "active", "url": "https://naukri.com", "method": "browser-use"},
        {"name": "Foundit", "id": "foundit", "status": "active", "url": "https://foundit.in", "method": "browser-use"},
        {"name": "Instahyre", "id": "instahyre", "status": "active", "url": "https://instahyre.com", "method": "browser-use"},
        {"name": "Cutshort", "id": "cutshort", "status": "active", "url": "https://cutshort.io", "method": "browser-use"},
        {"name": "Hirect", "id": "hirect", "status": "active", "url": "https://hirect.in", "method": "browser-use"},
        {"name": "Internshala", "id": "internshala", "status": "active", "url": "https://internshala.com", "method": "browser-use"},
        {"name": "Shine", "id": "shine", "status": "active", "url": "https://shine.com", "method": "browser-use"},
        {"name": "iimjobs", "id": "iimjobs", "status": "active", "url": "https://iimjobs.com", "method": "browser-use"},
        {"name": "Freshersworld", "id": "freshersworld", "status": "active", "url": "https://freshersworld.com", "method": "browser-use"},
    ]
