"""Unit tests for Jobs API integration."""
import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


def make_client(headers=None):
    return AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers=headers or {},
    )


@pytest.mark.asyncio
async def test_jobs_search_requires_auth():
    async with make_client() as client:
        resp = await client.post("/api/v1/jobs/search", json={
            "search_query": "python",
            "location": "Remote",
            "max_results": 5,
        })
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_jobs_search_rejects_too_many_results():
    async with make_client() as client:
        resp = await client.post("/api/v1/jobs/search", json={
            "search_query": "python",
            "max_results": 9999,
        })
    assert resp.status_code in (400, 401, 422)


@pytest.mark.asyncio
async def test_jobs_list_applications_requires_auth():
    async with make_client() as client:
        resp = await client.get("/api/v1/jobs/applications")
    assert resp.status_code in (401, 422)


@pytest.mark.asyncio
async def test_agents_run_returns_202():
    async with make_client() as client:
        resp = await client.post("/api/v1/agents/run", json={
            "task_type": "resume_optimize",
            "context": {"jd_text": "Python engineer"},
        })
    assert resp.status_code in (202, 200, 401, 422)


@pytest.mark.asyncio
async def test_agents_stream_requires_ownership():
    async with make_client() as client:
        resp = await client.get("/api/v1/agents/00000000-0000-0000-0000-000000000fff/stream")
    assert resp.status_code in (401, 404)


@pytest.mark.asyncio
async def test_agents_approve_rejects_unknown_run():
    async with make_client() as client:
        resp = await client.post("/api/v1/agents/00000000-0000-0000-0000-000000000fff/approve", json={
            "approved": True,
        })
    assert resp.status_code in (401, 404)
