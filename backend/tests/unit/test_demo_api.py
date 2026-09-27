"""Unit tests for the public, unauthenticated demo job search endpoint.

Search I/O is NEVER called here — every test mocks
app.api.v1.demo.search_all_platforms(). Redis is a tiny in-memory fake so the
lifetime-per-IP cap can be asserted deterministically without a live server.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import demo as demo_module
from app.main import app


def make_client():
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    )


class FakeRedis:
    """Minimal async INCR/EXPIRE/GET fake, enough for the demo quota counter."""

    def __init__(self):
        self._store: dict[str, int] = {}

    async def incr(self, key: str) -> int:
        self._store[key] = self._store.get(key, 0) + 1
        return self._store[key]

    async def expire(self, key: str, ttl: int) -> None:
        return None

    async def get(self, key: str):
        value = self._store.get(key)
        return str(value) if value is not None else None


SAMPLE_JOBS = [
    {
        "title": "Backend Engineer",
        "company": "Acme Corp",
        "location": "Remote",
        "url": "https://example.com/jobs/1",
        "platform": "open_apis",
    },
    {
        "title": "Python Developer",
        "company": "Widgets Inc",
        "location": "Remote",
        "url": "https://example.com/jobs/2",
        "platform": "open_apis",
    },
]


@pytest.mark.asyncio
async def test_demo_job_search_returns_real_shaped_jobs():
    fake_redis = FakeRedis()
    with (
        patch.object(demo_module, "get_redis", lambda: fake_redis),
        patch.object(demo_module, "search_all_platforms", return_value=(SAMPLE_JOBS, [])),
    ):
        async with make_client() as client:
            resp = await client.post(
                "/api/v1/demo/job-search",
                json={"query": "python developer", "location": "Remote"},
            )
    assert resp.status_code == 200
    body = resp.json()
    assert body["searches_used"] == 1
    assert body["searches_remaining"] == 1
    assert len(body["jobs"]) == 2
    assert body["jobs"][0]["title"] == "Backend Engineer"
    assert body["jobs"][0]["url"] == "https://example.com/jobs/1"


@pytest.mark.asyncio
async def test_demo_job_search_blocks_after_two_lifetime_searches():
    fake_redis = FakeRedis()
    with (
        patch.object(demo_module, "get_redis", lambda: fake_redis),
        patch.object(demo_module, "search_all_platforms", return_value=(SAMPLE_JOBS, [])),
    ):
        async with make_client() as client:
            first = await client.post(
                "/api/v1/demo/job-search", json={"query": "python", "location": "Remote"}
            )
            second = await client.post(
                "/api/v1/demo/job-search", json={"query": "python", "location": "Remote"}
            )
            third = await client.post(
                "/api/v1/demo/job-search", json={"query": "python", "location": "Remote"}
            )

    assert first.status_code == 200
    assert first.json()["searches_remaining"] == 1
    assert second.status_code == 200
    assert second.json()["searches_remaining"] == 0
    assert third.status_code == 429
    assert "free demo searches" in third.json()["detail"]


@pytest.mark.asyncio
async def test_demo_job_search_rejects_empty_query():
    fake_redis = FakeRedis()
    with patch.object(demo_module, "get_redis", lambda: fake_redis):
        async with make_client() as client:
            resp = await client.post(
                "/api/v1/demo/job-search", json={"query": "", "location": "Remote"}
            )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_demo_quota_reports_zero_used_before_any_search():
    fake_redis = FakeRedis()
    with patch.object(demo_module, "get_redis", lambda: fake_redis):
        async with make_client() as client:
            resp = await client.get("/api/v1/demo/job-search/quota")
    assert resp.status_code == 200
    body = resp.json()
    assert body["searches_used"] == 0
    assert body["searches_remaining"] == 2


@pytest.mark.asyncio
async def test_demo_quota_reflects_prior_searches():
    fake_redis = FakeRedis()
    with (
        patch.object(demo_module, "get_redis", lambda: fake_redis),
        patch.object(demo_module, "search_all_platforms", return_value=(SAMPLE_JOBS, [])),
    ):
        async with make_client() as client:
            await client.post(
                "/api/v1/demo/job-search", json={"query": "python", "location": "Remote"}
            )
            quota_resp = await client.get("/api/v1/demo/job-search/quota")

    assert quota_resp.status_code == 200
    body = quota_resp.json()
    assert body["searches_used"] == 1
    assert body["searches_remaining"] == 1
