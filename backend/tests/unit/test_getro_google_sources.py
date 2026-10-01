"""VC portfolio boards (Getro) and Google site: searches for ATS postings."""

import httpx
import pytest

from app.services import job_connectors as connectors
from app.services.job_connectors import Source

BOARD = '<script id="__NEXT_DATA__">{"props":{"network":{"name":"Acme VC","id":4711}}}</script>'
SEARCH = {
    "results": {
        "total": 150,
        "jobs": [
            {
                "id": 1,
                "title": "Backend Engineer",
                "url": "https://jobs.example-vc.com/companies/acme/jobs/1",
                "created_at": 1790000000,
                "locations": ["Bengaluru, India", "Remote"],
                "organization": {"name": "Acme"},
            },
            {"id": 2, "title": "No company", "url": "https://x.example.com/2"},
        ],
    }
}


def test_network_id_is_read_from_the_board_page():
    assert connectors.getro_network_id(BOARD) == "4711"
    assert connectors.getro_network_id('{"network_id": 99}') == "99"
    assert connectors.getro_network_id("<html>nothing</html>") is None


@pytest.mark.asyncio
async def test_getro_board_resolves_its_id_then_pages_through_jobs(monkeypatch):
    calls = []

    async def get(url, **kwargs):
        calls.append((url, kwargs.get("json_body")))
        if "api.getro.com" in url:
            return httpx.Response(200, json=SEARCH, request=httpx.Request("POST", url))
        return httpx.Response(200, text=BOARD, request=httpx.Request("GET", url))

    monkeypatch.setattr(connectors, "public_get", get)
    connectors._getro_networks.clear()
    source = Source(id="getro:test", family="getro", url="https://jobs.example-vc.com")
    page = await connectors.fetch_page(source, cursor="1")
    assert [j["title"] for j in page.jobs] == ["Backend Engineer"]
    assert page.jobs[0]["company"] == "Acme" and page.next_cursor == "2"
    assert calls[1][0].endswith("/collections/4711/search/jobs")
    assert calls[1][1]["page"] == 0
    # the id is remembered, so the board page is fetched once
    await connectors.fetch_page(source, cursor="2")
    assert len(calls) == 3 and calls[2][1]["page"] == 1


@pytest.mark.asyncio
async def test_getro_needs_an_address_or_id():
    with pytest.raises(ValueError):
        await connectors.fetch_page(Source(id="getro:none", family="getro"))


GOOGLE = {
    "items": [
        {
            "title": "Senior Engineer - Acme Corp - Greenhouse",
            "link": "https://boards.greenhouse.io/acme-corp/jobs/123",
            "snippet": "Join us in Pune",
        },
        {
            "title": "Data Analyst - Globex Careers",
            "link": "https://globex.wd1.myworkdayjobs.com/en-US/Careers/job/Pune/Analyst_R1",
            "snippet": "Analyse",
        },
        {"title": "Careers", "link": "https://example.com/careers"},
    ]
}


def test_google_results_become_postings_on_the_ats():
    jobs = connectors.parse_google_cse(GOOGLE)
    assert [(j["title"], j["company"]) for j in jobs] == [
        ("Senior Engineer", "Acme Corp"),
        ("Data Analyst", "Globex"),
    ]
    assert jobs[0]["url"].startswith("https://boards.greenhouse.io/")


@pytest.mark.asyncio
async def test_google_search_is_inert_without_keys_and_one_page_with_them(monkeypatch):
    source = Source(id="google:greenhouse", family="google_cse", url="site:boards.greenhouse.io")
    monkeypatch.setattr(connectors.settings, "GOOGLE_CSE_API_KEY", None)
    with pytest.raises(ValueError, match="not configured"):
        await connectors.fetch_page(source)

    monkeypatch.setattr(connectors.settings, "GOOGLE_CSE_API_KEY", "k")
    monkeypatch.setattr(connectors.settings, "GOOGLE_CSE_ID", "cx")
    seen = []

    async def get(url, **kwargs):
        seen.append(url)
        return httpx.Response(200, json=GOOGLE, request=httpx.Request("GET", url))

    monkeypatch.setattr(connectors, "public_get", get)
    page = await connectors.fetch_page(source, query="python")
    assert len(page.jobs) == 2 and page.next_cursor is None
    assert "site%3Aboards.greenhouse.io+python" in seen[0] and "key=k" in seen[0]


@pytest.mark.asyncio
async def test_working_nomads_listing_becomes_remote_jobs(monkeypatch):
    feed = [
        {
            "url": "https://www.workingnomads.com/jobs/dev-1",
            "title": "Python Developer",
            "company_name": "Acme",
            "pub_date": "2026-10-01T08:00:00Z",
        },
        {"title": "No url"},
    ]

    async def get(url, **kwargs):
        return httpx.Response(200, json=feed, request=httpx.Request("GET", url))

    monkeypatch.setattr(connectors, "public_get", get)
    page = await connectors.fetch_page(Source(id="workingnomads", family="workingnomads"))
    assert [(j["title"], j["remote"]) for j in page.jobs] == [("Python Developer", "remote")]


@pytest.mark.asyncio
async def test_careerjet_is_inert_without_a_key_and_pages_with_one(monkeypatch):
    source = Source(id="careerjet:in", family="careerjet", tenant="en_IN")
    monkeypatch.setattr(connectors.settings, "CAREERJET_API_KEY", None)
    with pytest.raises(ValueError, match="not configured"):
        await connectors.fetch_page(source)

    monkeypatch.setattr(connectors.settings, "CAREERJET_API_KEY", "secret")
    seen = {}

    async def get(url, **kwargs):
        seen["url"], seen["headers"] = url, kwargs["headers"]
        body = {
            "pages": 3,
            "jobs": [
                {
                    "title": "Analyst",
                    "company": "Globex",
                    "url": "https://www.careerjet.co.in/jobad/abc",
                    "locations": "Pune",
                    "date": "Wed, 01 Oct 2026 08:00:00 GMT",
                }
            ],
        }
        return httpx.Response(200, json=body, request=httpx.Request("GET", url))

    monkeypatch.setattr(connectors, "public_get", get)
    page = await connectors.fetch_page(source, query="analyst")
    assert page.jobs[0]["company"] == "Globex" and page.next_cursor == "2"
    assert "locale_code=en_IN" in seen["url"] and seen["headers"]["Authorization"].startswith(
        "Basic "
    )
