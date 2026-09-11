"""
platform_detector.py — Detect job platform from URL and return CSS selectors.

Used by JobSearchAgent to locate job details on listing pages, and by
FormFillerService to target platform-specific form elements.
"""


def detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "linkedin.com" in url_lower:
        return "linkedin"
    if "indeed.com" in url_lower:
        return "indeed"
    if "naukri.com" in url_lower:
        return "naukri"
    if "shine.com" in url_lower:
        return "shine"
    if "freshersworld.com" in url_lower:
        return "freshersworld"
    if "glassdoor" in url_lower:
        return "glassdoor"
    return "generic"


def extract_job_details_selectors(platform: str) -> dict[str, str]:
    selectors: dict[str, dict[str, str]] = {
        "linkedin": {
            "title": ".job-details-jobs-unified-top-card__job-title",
            "company": ".job-details-jobs-unified-top-card__company-name",
            "location": ".job-details-jobs-unified-top-card__bullet",
            "description": ".jobs-description__content",
            "apply_button": ".jobs-apply-button",
        },
        "indeed": {
            "title": ".jobsearch-JobInfoHeader-title",
            "company": "[data-testid='inlineHeader-companyName']",
            "description": "#jobDescriptionText",
            "apply_button": ".jobsearch-IndeedApplyButton-newDesign",
        },
        "naukri": {
            "title": ".jd-header-title",
            "company": ".jd-header-comp-name",
            "description": ".job-desc",
            "apply_button": ".apply-button",
        },
        "generic": {
            "title": "h1",
            "company": "[class*='company']",
            "description": "[class*='description'], [class*='job-desc']",
            "apply_button": "[class*='apply'], button[type='submit']",
        },
    }
    return selectors.get(platform, selectors["generic"])


# CSS selectors for job search result cards
JOB_CARD_SELECTORS: dict[str, dict[str, str]] = {
    "linkedin": {
        "container": ".job-card-container",
        "title": ".job-card-list__title",
        "company": ".job-card-container__company-name",
        "location": ".job-card-container__metadata-item",
        "url": "a.job-card-container__link",
    },
    "indeed": {
        "container": ".job_seen_beacon",
        "title": "[data-testid='jobTitle']",
        "company": "[data-testid='company-name']",
        "location": "[data-testid='text-location']",
        "url": "a[data-testid='jobTitle']",
    },
    "naukri": {
        "container": ".jobTuple",
        "title": ".title",
        "company": ".subTitle",
        "location": ".ellipsis",
        "url": "a.title",
    },
    "glassdoor": {
        "container": ".jobCard",
        "title": ".jobCard__jobTitle",
        "company": ".jobCard__companyName",
        "location": ".jobCard__location",
        "url": "a.jobCard__titleLink",
    },
    "generic": {
        "container": "[class*='job']",
        "title": "h2, h3, [class*='title']",
        "company": "[class*='company']",
        "location": "[class*='location']",
        "url": "a",
    },
}

# Search result page URLs for each platform
PLATFORM_SEARCH_URLS: dict[str, str] = {
    "linkedin": "https://www.linkedin.com/jobs/search/?keywords={query}&location={location}&f_TPR=r86400",
    "indeed": "https://in.indeed.com/jobs?q={query}&l={location}&fromage=1",
    "naukri": "https://www.naukri.com/{query_slug}-jobs?location={location}",
    "glassdoor": "https://www.glassdoor.co.in/Job/jobs.htm?sc.keyword={query}&locT=C&locId=0",
}
