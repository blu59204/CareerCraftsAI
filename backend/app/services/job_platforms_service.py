"""
job_platforms_service.py — Multi-platform job scraping via JobSpy.

Scrapes simultaneously from: LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter.
Returns unified job listings with company, title, location, description, URL.
"""
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


# Platforms to scrape — all supported by JobSpy
PLATFORMS = ["linkedin", "indeed", "glassdoor", "google", "zip_recruiter"]


def scrape_jobs(
    search_term: str,
    location: str = "Remote",
    results_wanted: int = 20,
    hours_old: int = 72,
    platforms: list[str] | None = None,
    country: str = "India",
) -> list[JobListing]:
    """Scrape jobs from multiple platforms simultaneously.

    Args:
        search_term: Job title/keywords to search
        location: Location filter
        results_wanted: Max results per platform
        hours_old: Only jobs posted within this many hours
        platforms: List of platforms to scrape (default: all)
        country: Country for Indeed/Google localization

    Returns:
        List of JobListing objects from all platforms combined.
    """
    from jobspy import scrape_jobs as jobspy_scrape

    target_platforms = platforms or PLATFORMS

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


def get_active_platforms() -> list[dict]:
    """Return list of supported job platforms with status."""
    return [
        {"name": "LinkedIn", "id": "linkedin", "status": "active", "url": "https://linkedin.com/jobs"},
        {"name": "Indeed", "id": "indeed", "status": "active", "url": "https://indeed.com"},
        {"name": "Glassdoor", "id": "glassdoor", "status": "active", "url": "https://glassdoor.com"},
        {"name": "Google Jobs", "id": "google", "status": "active", "url": "https://google.com/jobs"},
        {"name": "ZipRecruiter", "id": "zip_recruiter", "status": "active", "url": "https://ziprecruiter.com"},
    ]
