"""Official/public source connector contract, normalization and deduplication."""

from __future__ import annotations

import hashlib
import html
import json
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from html.parser import HTMLParser
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

from app.core.config import settings
from app.services.public_http import public_get

FAMILIES = {
    "greenhouse",
    "lever",
    "ashby",
    "workable",
    "smartrecruiters",
    "recruitee",
    "adzuna",
    "remotive",
    "remoteok",
    "arbeitnow",
    "himalayas",
    "jooble",
    "hn_hiring",
    "rss",
    "jsonld",
}


@dataclass(frozen=True)
class Source:
    id: str
    family: str
    tenant: str = ""
    url: str = ""
    permitted: bool = True
    # How often the catalog re-reads this source: busy boards every few
    # hours, quiet ones daily.
    refresh_hours: int = 1


@dataclass
class Page:
    jobs: list[dict]
    next_cursor: str | None = None


def canonical_url(value: str) -> str:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.hostname or parts.username or parts.password:
        raise ValueError("Jobs require a HTTPS URL without credentials")
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query)
        if not k.lower().startswith("utm_") and k.lower() not in {"ref", "source", "trackingid"}
    ]
    return urlunsplit(
        (parts.scheme, parts.netloc.lower(), parts.path.rstrip("/"), urlencode(sorted(query)), "")
    )


def posted(value):
    if not value:
        return None
    try:
        if isinstance(value, (float, int)):
            stamp = value / 1000 if value > 10**11 else value
            return datetime.fromtimestamp(stamp, UTC)
        date = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return date.replace(tzinfo=UTC) if date.tzinfo is None else date.astimezone(UTC)
    except (ValueError, OverflowError, OSError):
        return None


def plain(value) -> str:
    return html.unescape(re.sub(r"<[^>]*>", " ", str(value or "")))[:16000].strip()


def normalize(raw: dict, source: Source) -> dict | None:
    try:
        url = canonical_url(str(raw.get("url") or ""))
    except ValueError:
        return None
    title, company = plain(raw.get("title")), plain(raw.get("company"))
    if not title or not company:
        return None
    location = plain(raw.get("location"))
    date = posted(raw.get("posted_at"))
    now = datetime.now(UTC)
    if date and date > now + timedelta(days=1):
        date = None
    expires = posted(raw.get("expires_at"))
    return {
        "job_id": hashlib.sha256(url.encode()).hexdigest()[:32],
        "source_id": source.id,
        "source_job_id": str(raw.get("id") or url),
        "title": title[:300],
        "company": company[:300],
        "location": location[:500],
        "remote": (
            "remote"
            if raw.get("remote") or "remote" in location.lower()
            else "hybrid" if "hybrid" in location.lower() else "unknown"
        ),
        "salary_text": plain(raw.get("salary_text"))[:300],
        "url": url,
        "platform": source.family,
        "posted_at": date.isoformat() if date else None,
        "first_seen_at": now.isoformat(),
        "last_seen_at": now.isoformat(),
        "expires_at": expires.isoformat() if expires else None,
        "description": plain(raw.get("description")),
        "occurrences": [{"source_id": source.id, "url": url}],
    }


# Hosts of applicant tracking systems. A posting on one of these is the
# original; the same role on an aggregator or board is a pointer to it.
ATS_HOSTS = (
    "greenhouse.io",
    "lever.co",
    "ashbyhq.com",
    "workable.com",
    "smartrecruiters.com",
    "recruitee.com",
    "myworkdayjobs.com",
    "icims.com",
    "jobvite.com",
    "bamboohr.com",
)
_COMPANY_SUFFIX = re.compile(
    r"\b(inc|llc|ltd|limited|pvt|private|corp|corporation|co|gmbh|technologies|technology|"
    r"solutions|labs|india)\b",
    re.IGNORECASE,
)


def _squash(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def role_key(job: dict) -> str:
    """The same role listed on different boards, whatever its URL: company
    (without legal suffixes), exact title, and where (remote collapses)."""
    company = _squash(_COMPANY_SUFFIX.sub(" ", str(job.get("company") or "")))
    location = str(job.get("location") or "")
    remote = job.get("remote") == "remote" or "remote" in location.lower()
    title = _squash(str(job.get("title") or ""))
    return f"{company}|{title}|{'remote' if remote else _squash(location)}"


def is_ats_url(url: str) -> bool:
    host = (urlsplit(url).hostname or "").lower()
    return any(host == h or host.endswith("." + h) for h in ATS_HOSTS)


def _merge(old: dict, new: dict) -> dict:
    """One role seen twice: keep the ATS posting as the main entry, remember
    every place it was listed, and keep the earliest date and fullest text."""
    primary, other = (
        (new, old) if is_ats_url(new["url"]) and not is_ats_url(old["url"]) else (old, new)
    )
    merged = dict(primary)
    merged["occurrences"] = list(
        {item["source_id"]: item for item in old["occurrences"] + new["occurrences"]}.values()
    )
    dates = [d for d in (old.get("posted_at"), new.get("posted_at")) if d]
    merged["posted_at"] = min(dates) if dates else None
    if len(other.get("description") or "") > len(merged.get("description") or ""):
        merged["description"] = other["description"]
    return merged


def dedupe(jobs: list[dict], days=30, now=None) -> list[dict]:
    """Drop expired and old jobs, then merge duplicates: first by URL, then by
    role across boards (see `role_key`)."""
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=days)
    by_url: dict[str, dict] = {}
    for job in jobs:
        date, expiry = posted(job.get("posted_at")), posted(job.get("expires_at"))
        if (date and date < cutoff) or (expiry and expiry <= now):
            continue
        key = canonical_url(job["url"])
        by_url[key] = _merge(by_url[key], job) if key in by_url else dict(job)
    by_role: dict[str, dict] = {}
    for job in by_url.values():
        key = role_key(job)
        by_role[key] = _merge(by_role[key], job) if key in by_role else job
    return list(by_role.values())


class JobPostingParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.active = False
        self.parts = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag == "script" and dict(attrs).get("type", "").lower() == "application/ld+json":
            self.active, self.parts = True, []

    def handle_data(self, data):
        if self.active:
            self.parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.active:
            self.blocks.append("".join(self.parts))
            self.active = False


def jsonld_jobs(text: str, url: str) -> list[dict]:
    parser = JobPostingParser()
    parser.feed(text)
    out = []

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            types = value.get("@type", [])
            if types == "JobPosting" or "JobPosting" in types:
                org = value.get("hiringOrganization") or {}
                locations = value.get("jobLocation") or []
                if isinstance(locations, dict):
                    locations = [locations]
                cities = [
                    str((loc.get("address") or {}).get("addressLocality") or "")
                    for loc in locations
                    if isinstance(loc, dict)
                ]
                out.append(
                    {
                        "id": str(value.get("identifier", "")),
                        "title": value.get("title"),
                        "company": org.get("name") if isinstance(org, dict) else org,
                        "location": ", ".join(cities),
                        "url": value.get("url") or url,
                        "posted_at": value.get("datePosted"),
                        "expires_at": value.get("validThrough"),
                        "description": value.get("description"),
                        "remote": value.get("jobLocationType") == "TELECOMMUTE",
                    }
                )
            for item in value.values():
                if isinstance(item, (dict, list)):
                    walk(item)

    for block in parser.blocks:
        try:
            walk(json.loads(block))
        except (ValueError, TypeError):
            continue
    return out[:200]


# ── community and feed sources ────────────────────────────────────────────


def parse_hn_post(comment_html: str) -> dict | None:
    """A "Who is hiring?" post: the first line is `Company | Role | Location | ...`.

    Posts that do not follow that convention are skipped rather than guessed at.
    """
    first = re.split(r"<p>|\n", comment_html or "", maxsplit=1)[0]
    parts = [plain(part) for part in first.split("|")]
    if len(parts) < 2 or not parts[0] or not parts[1]:
        return None
    rest = parts[2:]
    return {
        "company": parts[0],
        "title": parts[1],
        "location": next((p for p in rest if p and "remote" not in p.lower()), ""),
        "remote": any("remote" in p.lower() for p in parts),
        "description": plain(comment_html),
    }


def parse_rss(xml_text: str, source_url: str) -> list[dict]:
    """Items of an RSS feed as raw jobs. Titles of the form `Company: Role`
    (We Work Remotely and similar) are split; otherwise the company is the
    feed's host."""
    from defusedxml import ElementTree

    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []
    out = []
    for item in root.iter("item"):
        title = (item.findtext("title") or "").strip()
        company, _, role = title.partition(": ")
        if not role:
            company, role = urlsplit(source_url).hostname or "", title
        pub = item.findtext("pubDate")
        try:
            from email.utils import parsedate_to_datetime

            posted_at = parsedate_to_datetime(pub).isoformat() if pub else None
        except (TypeError, ValueError):
            posted_at = None
        out.append(
            {
                "id": item.findtext("guid") or item.findtext("link"),
                "title": role,
                "company": company,
                "url": (item.findtext("link") or "").strip(),
                "location": item.findtext("region") or "",
                "remote": True,
                "description": item.findtext("description"),
                "posted_at": posted_at,
            }
        )
    return out


async def _fetch_hn_hiring(page: int) -> tuple[list[dict], str | None]:
    """The latest monthly "Ask HN: Who is hiring?" thread, one page of posts
    at a time, through HN's public Algolia search."""
    found = await public_get(
        "https://hn.algolia.com/api/v1/search_by_date?"
        + urlencode({"tags": "story,author_whoishiring", "query": "who is hiring"})
        + "&hitsPerPage=5"
    )
    found.raise_for_status()
    thread = next(
        (
            hit
            for hit in found.json().get("hits", [])
            if str(hit.get("title", "")).lower().startswith("ask hn: who is hiring")
        ),
        None,
    )
    if not thread:
        return [], None
    story = thread["objectID"]
    if not re.fullmatch(r"\d{1,12}", str(story)):
        return [], None
    response = await public_get(
        "https://hn.algolia.com/api/v1/search_by_date?"
        + urlencode({"tags": f"comment,story_{story}", "hitsPerPage": 100, "page": page - 1})
    )
    response.raise_for_status()
    data = response.json()
    rows = []
    for hit in data.get("hits", []):
        if str(hit.get("parent_id")) != str(story):
            continue  # a reply, not a posting
        job = parse_hn_post(hit.get("comment_text") or "")
        if job:
            job.update(
                {
                    "id": hit["objectID"],
                    "url": f"https://news.ycombinator.com/item?id={hit['objectID']}",
                    "posted_at": hit.get("created_at"),
                }
            )
            rows.append(job)
    more = page < int(data.get("nbPages", 0))
    return rows, str(page + 1) if more else None


async def fetch_page(source: Source, query: str = "", cursor: str | None = None) -> Page:
    if source.family not in FAMILIES or not source.permitted:
        raise ValueError("Source is not permitted")
    tenant = source.tenant
    if tenant and not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", tenant):
        raise ValueError("Invalid source tenant")
    family = source.family
    page = int(cursor or "1")
    if page < 1 or page > 10:
        raise ValueError("Pagination limit exceeded")
    headers = {}
    if family == "hn_hiring":
        rows, next_cursor = await _fetch_hn_hiring(page)
        return Page([job for raw in rows if (job := normalize(raw, source))], next_cursor)
    urls = {
        "greenhouse": f"https://boards-api.greenhouse.io/v1/boards/{tenant}/jobs?content=true",
        "lever": f"https://api.lever.co/v0/postings/{tenant}?mode=json&limit=100&skip={(page-1)*100}",
        "ashby": f"https://api.ashbyhq.com/posting-api/job-board/{tenant}",
        "workable": f"https://{tenant}.workable.com/spi/v3/jobs?state=published",
        "smartrecruiters": f"https://api.smartrecruiters.com/v1/companies/{tenant}/postings?limit=100&offset={(page-1)*100}",
        "recruitee": f"https://{tenant}.recruitee.com/api/offers/",
        "remotive": "https://remotive.com/api/remote-jobs",
        "remoteok": "https://remoteok.com/api",
        "arbeitnow": f"https://www.arbeitnow.com/api/job-board-api?page={page}",
        "himalayas": f"https://himalayas.app/jobs/api?limit=100&offset={(page-1)*100}",
    }
    if family == "workable":
        token = settings.WORKABLE_API_TOKENS.get(tenant)
        if not token:
            raise ValueError("Workable requires an authorized read-only API token")
        headers["Authorization"] = "Bearer " + token
    if family == "adzuna":
        if not settings.ADZUNA_APP_ID or not settings.ADZUNA_APP_KEY:
            raise ValueError("Adzuna credentials are not configured")
        url = f"https://api.adzuna.com/v1/api/jobs/{tenant or 'gb'}/search/{page}?" + urlencode(
            {
                "app_id": settings.ADZUNA_APP_ID,
                "app_key": settings.ADZUNA_APP_KEY,
                "what": "",
                "results_per_page": 100,
            }
        )
    elif family == "jsonld":
        url = canonical_url(source.url)
        parsed = urlsplit(url)
        robots_url = f"https://{parsed.netloc}/robots.txt"
        robots = await public_get(robots_url, max_bytes=200_000)
        if robots.status_code not in (200, 404):
            raise ValueError("Robots policy unavailable")
        if robots.status_code == 200:
            policy = RobotFileParser()
            policy.parse(robots.text.splitlines())
            if not policy.can_fetch("CareerCraftJobDiscovery", url):
                raise ValueError("Robots disallows access")
    elif family == "rss":
        url = canonical_url(source.url)
    elif family == "jooble":
        if not settings.JOOBLE_API_KEY:
            raise ValueError("Jooble credentials are not configured")
        url = f"https://jooble.org/api/{settings.JOOBLE_API_KEY}"
        jooble_body = {"keywords": query or "", "location": tenant, "page": page}
    else:
        url = urls[family]
    response = await public_get(
        url, headers=headers, json_body=jooble_body if family == "jooble" else None
    )
    response.raise_for_status()
    data = response.json() if family not in {"jsonld", "rss"} else None
    rows, next_cursor = [], None
    if family == "greenhouse":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": tenant,
                "url": j.get("absolute_url"),
                "location": (j.get("location") or {}).get("name"),
                "description": j.get("content"),
                "posted_at": j.get("first_published"),
            }
            for j in data.get("jobs", [])
        ]
    elif family == "lever":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("text"),
                "company": tenant,
                "url": j.get("hostedUrl"),
                "location": (j.get("categories") or {}).get("location"),
                "description": j.get("descriptionPlain"),
                "posted_at": j.get("createdAt"),
            }
            for j in data
        ]
        next_cursor = str(page + 1) if len(data) == 100 else None
    elif family == "ashby":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": tenant,
                "url": j.get("jobUrl"),
                "location": j.get("location"),
                "remote": j.get("isRemote"),
                "description": j.get("descriptionPlain"),
                "posted_at": j.get("publishedAt"),
            }
            for j in data.get("jobs", [])
        ]
    elif family == "smartrecruiters":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("name"),
                "company": tenant,
                "url": f"https://jobs.smartrecruiters.com/{tenant}/{j.get('id')}",
                "location": (j.get("location") or {}).get("city"),
                "posted_at": j.get("releasedDate"),
                "description": j.get("jobAd", {}).get("sections", {}),
            }
            for j in data.get("content", [])
        ]
        next_cursor = str(page + 1) if page * 100 < data.get("totalFound", 0) else None
    elif family in {"workable", "recruitee"}:
        items = data.get("results", data.get("jobs", data.get("offers", [])))
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": tenant,
                "url": j.get("url") or j.get("careers_url"),
                "location": (
                    j.get("location")
                    if isinstance(j.get("location"), str)
                    else str(j.get("location") or "")
                ),
                "description": j.get("description"),
                "posted_at": j.get("created_at") or j.get("published_at"),
            }
            for j in items
        ]
    elif family == "adzuna":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": (j.get("company") or {}).get("display_name"),
                "url": j.get("redirect_url"),
                "location": (j.get("location") or {}).get("display_name"),
                "description": j.get("description"),
                "posted_at": j.get("created"),
                "salary_text": f"{j.get('salary_min', '')}–{j.get('salary_max', '')}",
            }
            for j in data.get("results", [])
        ]
        next_cursor = str(page + 1) if page * 100 < data.get("count", 0) else None
    elif family == "remotive":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": j.get("company_name"),
                "url": j.get("url"),
                "location": j.get("candidate_required_location"),
                "remote": True,
                "description": j.get("description"),
                "posted_at": j.get("publication_date"),
                "salary_text": j.get("salary"),
            }
            for j in data.get("jobs", [])
        ]
    elif family == "remoteok":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("position"),
                "company": j.get("company"),
                "url": j.get("url"),
                "location": j.get("location"),
                "remote": True,
                "description": j.get("description"),
                "posted_at": j.get("date"),
            }
            for j in data
            if j.get("position")
        ]
    elif family == "arbeitnow":
        rows = [
            {
                "id": j.get("slug"),
                "title": j.get("title"),
                "company": j.get("company_name"),
                "url": j.get("url"),
                "location": j.get("location"),
                "remote": j.get("remote"),
                "description": j.get("description"),
                "posted_at": j.get("created_at"),
            }
            for j in data.get("data", [])
        ]
        next_cursor = str(page + 1) if (data.get("links") or {}).get("next") else None
    elif family == "jooble":
        rows = [
            {
                "id": j.get("id"),
                "title": j.get("title"),
                "company": j.get("company"),
                "url": j.get("link"),
                "location": j.get("location"),
                "description": j.get("snippet"),
                "posted_at": j.get("updated"),
                "salary_text": j.get("salary"),
            }
            for j in data.get("jobs", [])
        ]
        next_cursor = str(page + 1) if page * 20 < int(data.get("totalCount") or 0) else None
    elif family == "himalayas":
        rows = [
            {
                "id": j.get("guid") or j.get("applicationLink"),
                "title": j.get("title"),
                "company": j.get("companyName"),
                "url": j.get("applicationLink") or j.get("guid"),
                "location": ", ".join(j.get("locationRestrictions") or []) or "Worldwide",
                "remote": True,
                "description": j.get("description") or j.get("excerpt"),
                "posted_at": j.get("pubDate"),
                "expires_at": j.get("expiryDate"),
                "salary_text": (
                    f"{j.get('minSalary')}–{j.get('maxSalary')} {j.get('currency') or ''}".strip()
                    if j.get("minSalary")
                    else ""
                ),
            }
            for j in data.get("jobs", [])
        ]
        total = int(data.get("totalCount") or 0)
        next_cursor = str(page + 1) if page * 100 < total else None
    elif family == "rss":
        rows = parse_rss(response.text, url)
    elif family == "jsonld":
        rows = jsonld_jobs(response.text, url)
    return Page([job for raw in rows[:1000] if (job := normalize(raw, source))], next_cursor)
