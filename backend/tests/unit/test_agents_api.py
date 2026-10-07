"""Authenticated HTTP contracts for agent dispatch, ownership and validation."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.v1 import agents, jobs
from app.api.v1.deps import get_current_user, get_db
from app.core.rate_limit import limiter


@pytest.fixture
def api():
    limiter.reset()
    app = FastAPI()
    app.state.limiter = limiter
    app.include_router(agents.router, prefix="/api/v1")
    app.include_router(jobs.router, prefix="/api/v1")
    owner = SimpleNamespace(id=uuid.uuid4())
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: None))
    )
    app.dependency_overrides[get_current_user] = lambda: owner
    app.dependency_overrides[get_db] = lambda: db
    return app, owner, db


async def test_jobs_search_rejects_too_many_results_when_authenticated(api):
    app, _, db = api
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/jobs/search", json={"search_query": "python", "max_results": 9999}
        )
    assert response.status_code == 422
    db.execute.assert_not_awaited()


async def test_agents_run_dispatches_authenticated_task(api, monkeypatch):
    app, owner, db = api
    queue = AsyncMock(return_value=str(uuid.uuid4()))
    monkeypatch.setattr("app.api.v1.run_utils.queue_agent_run", queue)
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post(
            "/api/v1/agents/run",
            json={"task_type": "resume_optimize", "context": {"jd_text": "Python"}},
        )
    assert response.status_code == 200
    assert response.json()["status"] == "queued"
    queue.assert_awaited_once_with(db, owner, "resume_optimize", {"jd_text": "Python"})


@pytest.mark.parametrize(
    "suffix,method,body", [("stream", "GET", None), ("approve", "POST", {"approved": True})]
)
async def test_foreign_or_unknown_run_is_rejected_before_stream_or_approval(
    api, suffix, method, body
):
    app, owner, db = api
    run_id = uuid.uuid4()
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.request(method, f"/api/v1/agents/{run_id}/{suffix}", json=body)
    assert response.status_code == 404
    values = db.execute.await_args.args[0].compile().params.values()
    assert run_id in values and owner.id in values


async def test_invalid_task_rejected_after_authentication(api):
    app, _, db = api
    async with AsyncClient(transport=ASGITransport(app), base_url="http://test") as client:
        response = await client.post("/api/v1/agents/run", json={"task_type": "not-a-task"})
    assert response.status_code == 400
    db.execute.assert_not_awaited()
