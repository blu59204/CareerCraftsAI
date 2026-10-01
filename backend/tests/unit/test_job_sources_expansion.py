"""Community feeds, new boards, cross-board dedupe, and refresh tiers."""

import httpx
import pytest

from app.services import job_connectors as connectors
from app.services.job_connectors import Source

HN_THREAD = {"hits": [{"objectID": "4242", "title": "Ask HN: Who is hiring? (October 2026)"}]}
HN_COMMENTS = {
    "nbPages": 1,
    "hits": [
        {
            "objectID": "9001",
            "parent_id": 4242,
            "created_at": "2026-10-01T08:00:00Z",
            "comment_text": (
                "Acme | Backend Engineer | Bangalore | REMOTE<p>We build things. "
                "Apply: jobs@acme.com"
            ),
        },
        {"objectID": "9002", "parent_id": 4242, "comment_text": "Just chatting, no pipe format"},
        {"objectID": "9003", "parent_id": 9001, "comment_text": "Acme | Reply | not a post"},
    ],
}


def _router(routes):
    async def get(url, **kwargs):
        for needle, payload in routes.items():
            if needle in url:
                kind = {"json": payload} if not isinstance(payload, str) else {"text": payload}
                return httpx.Response(200, request=httpx.Request("GET", url), **kind)
        raise AssertionError(f"unexpected request {url}")

    return get


@pytest.mark.asyncio
async def test_hn_hiring_posts_become_jobs_and_replies_are_ignored(monkeypatch):
    monkeypatch.setattr(
        connectors,
        "public_get",
        _router({"author_whoishiring": HN_THREAD, "story_4242": HN_COMMENTS}),
    )
    page = await connectors.fetch_page(Source("hn-whos-hiring", "hn_hiring"))
    assert [(j["company"], j["title"], j["remote"]) for j in page.jobs] == [
        ("Acme", "Backend Engineer", "remote")
    ]
    assert page.jobs[0]["url"] == "https://news.ycombinator.com/item?id=9001"
    assert page.next_cursor is None


RSS = """<?xml version="1.0"?><rss><channel>
<item><title>Globex: Senior Python Developer</title><link>https://weworkremotely.com/jobs/1</link>
<guid>1</guid><pubDate>Wed, 01 Oct 2026 08:00:00 +0000</pubDate><region>Anywhere</region>
<description>Build APIs</description></item>
<item><title>No company prefix here</title><link>https://weworkremotely.com/jobs/2</link></item>
</channel></rss>"""


@pytest.mark.asyncio
async def test_rss_feed_splits_company_from_title(monkeypatch):
    monkeypatch.setattr(connectors, "public_get", _router({"weworkremotely": RSS}))
    source = Source("rss:wwr", "rss", url="https://weworkremotely.com/remote-jobs.rss")
    page = await connectors.fetch_page(source)
    first, second = page.jobs
    assert (first["company"], first["title"]) == ("Globex", "Senior Python Developer")
    assert first["posted_at"].startswith("2026-10-01")
    assert second["company"] == "weworkremotely.com"


def test_hostile_xml_is_rejected_not_expanded():
    bomb = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY a "aaaa">]><rss><channel></channel></rss>'
    with pytest.raises(Exception):
        connectors.parse_rss(bomb, "https://x.example/feed")


@pytest.mark.asyncio
async def test_himalayas_jobs_are_remote_and_use_the_application_link(monkeypatch):
    payload = {
        "totalCount": 1,
        "jobs": [
            {
                "title": "Data Engineer",
                "companyName": "Initech",
                "applicationLink": "https://himalayas.app/companies/initech/jobs/1",
                "locationRestrictions": ["India"],
                "pubDate": 1790000000,
            }
        ],
    }
    monkeypatch.setattr(connectors, "public_get", _router({"himalayas.app/jobs/api": payload}))
    page = await connectors.fetch_page(Source("himalayas", "himalayas"))
    assert page.jobs[0]["remote"] == "remote" and page.jobs[0]["location"] == "India"


def _job(url, source, company="Acme Inc", title="Backend Engineer", location="Bangalore"):
    return {
        "url": url,
        "source_id": source,
        "company": company,
        "title": title,
        "location": location,
        "remote": "unknown",
        "description": "short",
        "posted_at": None,
        "occurrences": [{"source_id": source, "url": url}],
    }


def test_same_role_on_two_boards_is_one_job_pointing_at_the_ats_page():
    jobs = [
        _job("https://remotive.com/jobs/77", "remotive"),
        _job("https://boards.greenhouse.io/acme/jobs/5", "greenhouse:acme", company="Acme"),
    ]
    (merged,) = connectors.dedupe(jobs)
    assert merged["url"] == "https://boards.greenhouse.io/acme/jobs/5"
    assert {o["source_id"] for o in merged["occurrences"]} == {"remotive", "greenhouse:acme"}


def test_different_locations_or_titles_are_not_merged():
    jobs = [
        _job("https://a.example/1", "a", location="Bangalore"),
        _job("https://a.example/2", "a", location="Pune"),
        _job("https://a.example/3", "a", title="Frontend Engineer"),
    ]
    assert len(connectors.dedupe(jobs)) == 3


def test_new_sources_load_with_their_refresh_tier():
    from app.services.job_catalog import sources

    by_id = {s.id: s for s in sources()}
    assert (
        by_id["hn-whos-hiring"].family == "hn_hiring" and by_id["hn-whos-hiring"].refresh_hours == 6
    )
    assert by_id["rss:weworkremotely"].url.startswith("https://weworkremotely.com/")
    assert by_id["greenhouse:stripe"].refresh_hours == 1
