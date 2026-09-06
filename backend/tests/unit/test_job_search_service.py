"""Unit tests for the queue-first job_search pass.

Search I/O is NEVER called here — every test mocks
services/job_search_service.search_all_platforms() (or the service adapters).
The LLM only scores via prompts/job_search_prompt in batches of 20.
"""
from __future__ import annotations

import uuid
from unittest.mock import MagicMock, patch

import pytest
from langchain_core.messages import HumanMessage

from app.agents.prompts.job_search_prompt import JobMatch, JobSearchOutput
from app.agents.state import AgentState


def make_state(**ctx) -> AgentState:
    context = {"titles": ["Backend Engineer"], "locations": ["Bengaluru"], "max_results": 10}
    context.update(ctx)
    return AgentState(
        user_id="usr_test123",
        run_id=str(uuid.uuid4()),
        task_type="job_search",
        messages=[HumanMessage(content="find backend jobs")],
        context=context,
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )


def _job(i: int) -> dict:
    return {
        "job_id": f"j{i}", "title": f"Backend Engineer {i}", "company": "Acme",
        "location": "Bengaluru", "remote": "onsite", "salary_text": "",
        "url": f"https://example.com/j/{i}", "platform": "open_apis",
        "posted_at": None, "description": "Python APIs",
    }


def _scored_output(jobs: list[dict], score: int = 80) -> JobSearchOutput:
    return JobSearchOutput(
        matches=[JobMatch(job_id=j["job_id"], score=score, reasons=["fit"],
                          red_flags=[], missing_skills=[]) for j in jobs],
        top_pick_id=jobs[0]["job_id"] if jobs else None,
    )


def _node_patches(**overrides):
    from app.agents import job_search as js

    defaults = dict(
        fetch_model_settings=MagicMock(provider="openai"),
        fetch_user_profile_text="profile",
        _build_llm=MagicMock(),
        search_all_platforms=([], []),
        call_llm_json=None,
        _persist_saved_jobs=0,
        emit=None,
    )
    defaults.update(overrides)
    return [
        patch.object(js, "fetch_model_settings", return_value=defaults["fetch_model_settings"]),
        patch.object(js, "fetch_user_profile_text", return_value=defaults["fetch_user_profile_text"]),
        patch.object(js, "_build_llm", return_value=defaults["_build_llm"]),
        patch.object(js, "search_all_platforms", return_value=defaults["search_all_platforms"]),
        patch.object(js, "emit"),
    ]


def test_search_returns_empty_complete_with_warnings_and_no_llm_call():
    from app.agents import job_search as js

    patches = _node_patches(search_all_platforms=([], ["open_apis failed: Timeout"]))
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with patch.object(js, "call_llm_json") as mock_score:
            result = js.job_search_agent_node(make_state())
    mock_score.assert_not_called()
    assert result["status"] == "completed"
    assert result["result"]["matches"] == []
    assert result["result"]["top_pick_id"] is None
    assert result["result"]["warnings"]


def test_45_postings_score_capped_at_max_results():
    from app.agents import job_search as js

    jobs = [_job(i) for i in range(45)]
    calls: list = []

    def fake_score(llm, system, human, schema):
        calls.append(human)
        start = len(calls) * 20 - 20
        return _scored_output(jobs[start:start + 20])

    patches = _node_patches(search_all_platforms=(jobs, []))
    with patches[0], patches[1], patches[2], patches[3], patches[4]:
        with patch.object(js, "call_llm_json", side_effect=fake_score):
            with patch.object(js, "_persist_saved_jobs", return_value=25):
                result = js.job_search_agent_node(make_state(max_results=25))

    # Scoring is capped at max_results so serial LLM calls fit the run budget.
    assert len(calls) == 2
    assert result["status"] == "completed"
    assert len(result["result"]["matches"]) == 25
    assert result["result"]["total_found"] == 45
    assert {m["job_id"] for m in result["result"]["matches"]} == {f"j{i}" for i in range(25)}
    assert result["result"]["top_pick_id"] == "j0"


def test_missing_titles_returns_error_shape():
    from app.agents import job_search as js

    result = js.job_search_agent_node(make_state(titles=[], search_query=None))
    assert result["status"] == "error"
    assert "titles" in result["error"]


def test_one_platform_failure_still_returns_others():
    import asyncio
    from app.services import job_search_service as svc

    good = [_job(0)]

    async def go():
        # NOTE: run_one resolves adapters via the _ADAPTERS registry, so
        # patch the registry entries — patching module attrs would miss.
        with patch.dict(svc._ADAPTERS, {
            "open_apis": MagicMock(side_effect=Exception("boom")),
            "jobspy": MagicMock(return_value=[{**_job(0), "platform": "x"}]),
            "ats": MagicMock(return_value=[]),
            "remoteok": MagicMock(return_value=[]),
        }):
            return await svc.search_all_platforms(
                {"titles": ["Backend"], "locations": [], "max_results": 10},
                ["open_apis", "jobspy", "ats", "remoteok"],
            )

    jobs, warnings = asyncio.run(go())
    assert len(jobs) == 1
    assert any("open_apis failed" in w for w in warnings)


def test_make_job_search_id_is_deterministic():
    from app.services.queue_service import make_job_search_id

    a = make_job_search_id("u1", "python", "Remote", 10)
    assert a == make_job_search_id("u1", "python", "Remote", 10)
    assert a.startswith("u1:job_search:")
    assert make_job_search_id("u1", "java", "Remote", 10) != a


def _override_auth(monkeypatch):
    """Authenticated app client without network.

    Patches the two JWT verify entry points (middleware in app.main and
    deps.get_current_user), the DB dependency, and search-context resolution.
    Returns the FastAPI app. Caller must clear dependency_overrides after.
    """
    from app.api.v1 import jobs as jobs_module
    from app.core.database import get_db
    from app.main import app

    payload = {"sub": "00000000-0000-0000-0000-000000000001", "email": "t@e.com"}
    monkeypatch.setattr("app.main.verify_token", lambda token: payload)
    monkeypatch.setattr("app.api.v1.deps.verify_auth_jwt", lambda token: payload)

    model_row = MagicMock()
    db = MagicMock()
    db.add = MagicMock()

    async def _flush():
        return None

    async def _exec(*a, **k):
        return MagicMock(
            scalars=MagicMock(return_value=MagicMock(first=MagicMock(return_value=model_row))),
            scalar_one_or_none=MagicMock(return_value=model_row),
        )

    db.flush = MagicMock(side_effect=lambda: _flush())
    db.execute = MagicMock(side_effect=lambda *a, **k: _exec(*a, **k))

    async def _fake_db():
        return db

    async def _ctx_unpack(*a, **k):
        return ("Backend Engineer", "Bengaluru", "", {"role_source": "test"})

    async def _no_browser(*a, **k):
        return False

    monkeypatch.setitem(app.dependency_overrides, get_db, _fake_db)
    monkeypatch.setattr(jobs_module, "_resolve_search_context", _ctx_unpack)
    monkeypatch.setattr(jobs_module, "_resolve_live_browser", _no_browser)
    return app


def test_search_dev_redis_down_inlines_with_warning_and_queued_false(monkeypatch, caplog):
    import logging

    from httpx import ASGITransport, AsyncClient

    from app.api.v1 import jobs as jobs_module

    app = _override_auth(monkeypatch)
    monkeypatch.setattr("app.services.queue_service._BULLMQ_AVAILABLE", False)

    async def go():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            with caplog.at_level(logging.WARNING, logger="app.services.queue_service"):
                return await client.post("/api/v1/jobs/search", json={
                    "titles": ["Backend Engineer"], "locations": ["Bengaluru"],
                    "platforms": ["indeed"], "max_results": 5,
                }, headers={"Authorization": "Bearer test-token"})

    import asyncio as _aio

    resp = _aio.run(go())
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["queued"] is False
    assert body["run_id"]
    assert "inline" in caplog.text.lower()

    app.dependency_overrides.clear()


def test_search_prod_redis_down_503_never_inline(monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.api.v1 import jobs as jobs_module
    from app.core.config import settings

    app = _override_auth(monkeypatch)
    monkeypatch.setattr("app.services.queue_service._BULLMQ_AVAILABLE", False)
    monkeypatch.setattr(settings, "APP_ENV", "production", raising=False)

    created_tasks: list = []
    real_create = __import__("asyncio").create_task
    monkeypatch.setattr(
        "app.services.queue_service.asyncio.create_task",
        lambda *a, **k: created_tasks.append(a) or MagicMock(),
    )

    async def go():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post("/api/v1/jobs/search", json={
                "titles": ["Backend Engineer"], "locations": ["Bengaluru"], "max_results": 5,
            }, headers={"Authorization": "Bearer test-token"})

    import asyncio as _aio

    resp = _aio.run(go())
    assert resp.status_code == 503
    assert created_tasks == []

    app.dependency_overrides.clear()


def test_persist_only_above_threshold_and_idempotent():
    from app.agents import job_search as js

    added: list = []

    class FakeSession:
        def __init__(self, store):
            self.store = store

        def execute(self, *a, **k):
            class R:
                def scalar_one_or_none(inner):
                    return "exists" if self.store.get("seen") else None
            return R()

        def add(self, row):
            added.append(row)

        def commit(self):
            self.store["seen"] = True

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    store: dict = {}
    # NOTE: _persist_saved_jobs imports _get_sync_factory locally from
    # app.core.sync_db at call time — patch it there, not in job_search.
    with patch(
        "app.core.sync_db._get_sync_factory", return_value=lambda: FakeSession(store)
    ):
        from app.agents.job_search import _persist_saved_jobs
        jobs = [{**_job(0), "match_score": 90}, {**_job(1), "match_score": 10}]
        assert _persist_saved_jobs("u1", jobs) == 1  # only score>=50, has url
        assert _persist_saved_jobs("u1", jobs) == 0  # second run: idempotent
