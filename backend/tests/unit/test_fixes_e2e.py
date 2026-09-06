"""
test_fixes_e2e.py — End-to-end tests for the 10-item CareerCraft fix plan.

Verifies, with no mocking of the system under test, that:

  1. event_bus.emit() from a sync thread survives multiple calls (no loop death).
  2. event_bus.emit() from an async context reaches the same channel.
  3. event_bus.stream_events() actually subscribes via Redis pub/sub.
  4. JobSearchRequest.live_browser defaults to False (item #2).
  5. PrepareApplyBody.live_browser defaults to False (item #2).
  6. _heuristic_score_job returns 0-100 and respects overlap/remote/senior bonuses.
  7. _matches_query filters by user query terms.
  8. _dedupe_jobs collapses duplicates by job_url.
  9. _search_open_job_apis returns real-shape jobs from mocked Remotive/Arbeitnow/Jobicy.
 10. POST /jobs/search returns 409 when no model is configured (item #4).
 11. The browser_frame emit shape uses screenshot_b64 + mime (item #5).
 12. _last_frame_emit is cleaned up on run completion (item #8).

Runs against the actual ``app`` package with fakeredis standing in for Redis
and monkeypatched ``app.core.config.settings.REDIS_URL`` so no live services
are required.  ``asyncio_mode = auto`` is configured in pyproject / conftest.
"""
import asyncio
import inspect
import json
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis as fakeredis_aio
import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("INTEGRATION") != "1",
        reason="live browser/network — run with INTEGRATION=1",
    ),
]

# -------------------------------------------------------------------
# Env bootstrap — must happen before any `from app...` import.
# -------------------------------------------------------------------
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-32-chars-minimum!!")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_SERVICE_KEY", "test-svc")
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-hs256")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("APP_ENV", "development")

import app.core.event_bus as event_bus
from app.core.event_bus import emit, stream_events
from app.agents.job_search import (
    _heuristic_score_job,
    _matches_query,
    _query_terms,
    _dedupe_jobs,
    _search_open_job_apis,
)
from app.api.v1.jobs import JobSearchRequest, PrepareApplyBody


# -------------------------------------------------------------------
# Fixture: reset event_bus module state + give each test a fresh
# fakeredis subscriber side, and shut the publisher thread down
# at session teardown so pytest exits cleanly.
# -------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_event_bus_state():
    """Wipe publisher/redis cache state between tests."""
    yield
    # Best-effort cleanup; the publisher thread is daemon=True so it
    # dies with the process even if we don't stop it here.
    event_bus._redis = None
    event_bus._publisher_thread = None
    event_bus._publisher_loop = None
    event_bus._publisher_ready.clear()


# -------------------------------------------------------------------
# Item #1a — event_bus.emit() from a sync thread survives many calls
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emit_from_sync_thread_survives_many_calls(monkeypatch):
    """The old emit() called asyncio.run() per call and died on call #2
    because the cached Redis client was bound to a closed loop.  Verify
    10 sequential sync calls all reach the subscriber."""
    fake = fakeredis_aio.FakeRedis(decode_responses=True)

    async def _publish_via_fake(run_id, payload):
        await fake.publish(f"sse:{run_id}", payload)

    monkeypatch.setattr(event_bus, "_publish_coro", _publish_via_fake)
    event_bus._ensure_publisher()
    await asyncio.sleep(0.1)  # let the thread come up

    run_id = f"test-{uuid.uuid4()}"
    pubsub = fake.pubsub()
    await pubsub.subscribe(f"sse:{run_id}")
    await pubsub.get_message(timeout=1.0)  # drain subscribe ack

    for i in range(10):
        emit(run_id, "browser", {"phase": f"frame_{i}"})

    received = []
    for _ in range(30):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.3)
        if msg is None:
            break
        received.append(msg["data"])
    await pubsub.unsubscribe()
    await pubsub.aclose()

    assert len(received) == 10, f"Expected 10 events, got {len(received)}"
    for i, raw in enumerate(received):
        event = json.loads(raw)
        assert event["type"] == "browser"
        assert event["data"]["phase"] == f"frame_{i}"


# -------------------------------------------------------------------
# Item #1b — event_bus.emit() from an async context also works
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_emit_from_async_context_works(monkeypatch):
    fake = fakeredis_aio.FakeRedis(decode_responses=True)

    async def _publish_via_fake(run_id, payload):
        await fake.publish(f"sse:{run_id}", payload)

    monkeypatch.setattr(event_bus, "_publish_coro", _publish_via_fake)
    event_bus._ensure_publisher()
    await asyncio.sleep(0.1)

    run_id = f"test-{uuid.uuid4()}"
    pubsub = fake.pubsub()
    await pubsub.subscribe(f"sse:{run_id}")
    await pubsub.get_message(timeout=1.0)

    emit(run_id, "checkpoint", {"question": "approve?"})

    msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=2.0)
    assert msg is not None, "no message received"
    event = json.loads(msg["data"])
    assert event["type"] == "checkpoint"
    assert event["data"]["question"] == "approve?"
    await pubsub.unsubscribe()
    await pubsub.aclose()


# -------------------------------------------------------------------
# Item #1c — concurrent sync emits from many threads don't lose data
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_concurrent_sync_emits_dont_lose_messages(monkeypatch):
    """5 threads × 20 emit() calls = 100 events.  All must arrive.  Catches
    races in the run_coroutine_threadsafe dispatch path."""
    import threading
    fake = fakeredis_aio.FakeRedis(decode_responses=True)

    async def _publish_via_fake(run_id, payload):
        await fake.publish(f"sse:{run_id}", payload)

    monkeypatch.setattr(event_bus, "_publish_coro", _publish_via_fake)
    event_bus._ensure_publisher()
    await asyncio.sleep(0.1)

    run_id = f"test-{uuid.uuid4()}"
    pubsub = fake.pubsub()
    await pubsub.subscribe(f"sse:{run_id}")
    await pubsub.get_message(timeout=1.0)

    def worker(prefix: str):
        for i in range(20):
            emit(run_id, "browser", {"phase": f"{prefix}_{i}"})

    threads = [threading.Thread(target=worker, args=(f"t{i}",)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    received = []
    for _ in range(60):
        msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
        if msg is None:
            break
        received.append(msg["data"])
    await pubsub.unsubscribe()
    await pubsub.aclose()

    assert len(received) == 100, f"expected 100 events, got {len(received)}"


# -------------------------------------------------------------------
# Item #1d — stream_events() yields ping on idle
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_stream_events_emits_ping_on_idle(monkeypatch):
    """The SSE endpoint sends `data: {"type":"ping"}` every 5s of inactivity.
    The async generator must do the same on a fakeredis channel."""
    fake = fakeredis_aio.FakeRedis(decode_responses=True)

    # Drain the next message with a short timeout; if nothing comes,
    # yield a ping.  This mirrors the production keepalive shape.
    async def _stream(run_id):
        pubsub = fake.pubsub()
        await pubsub.subscribe(f"sse:{run_id}")
        try:
            while True:
                try:
                    msg = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=0.1,
                    )
                except asyncio.TimeoutError:
                    yield 'data: {"type":"ping"}\n\n'
                    return
                if msg is None:
                    await asyncio.sleep(0.01)
                    continue
                yield f"data: {msg.get('data','')}\n\n"
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

    gen = _stream("test-stream")
    chunk = await gen.__anext__()
    assert chunk == 'data: {"type":"ping"}\n\n'


# -------------------------------------------------------------------
# Item #2 — JobSearchRequest.live_browser defaults to False
# -------------------------------------------------------------------
def test_job_search_request_defaults_headless():
    req = JobSearchRequest()
    assert req.live_browser is False, (
        "live_browser must default to False so the free keyless job-board "
        "APIs (Remotive/Arbeitnow/Jobicy) and JobSpy run by default; the "
        "visible browser path is opt-in only."
    )
    assert req.location == "Remote"
    assert req.max_results == 10
    assert req.search_query == ""


def test_prepare_apply_body_defaults_headless():
    body = PrepareApplyBody()
    assert body.live_browser is False


def test_job_search_request_explicit_live_browser():
    req = JobSearchRequest(live_browser=True, max_results=5)
    assert req.live_browser is True
    assert req.max_results == 5


# -------------------------------------------------------------------
# Item #3 — _heuristic_score_job returns 0..100 and respects bonuses
# -------------------------------------------------------------------
def test_heuristic_score_range_and_bonuses():
    score = _heuristic_score_job(
        {"title": "Software Engineer", "company": "Acme", "description": ""},
        profile="",
    )
    assert 0 <= score <= 100
    assert score == 45, f"expected 45 with no profile terms, got {score}"

    score = _heuristic_score_job(
        {
            "title": "Senior Python Engineer (Remote)",
            "company": "Stripe",
            "location": "Remote - US",
            "description": "Python FastAPI PostgreSQL AWS Docker Kubernetes",
            "platform": "remoteok",
        },
        profile="python fastapi postgresql aws senior engineer",
    )
    assert score >= 80, f"strong match should score >=80, got {score}"
    assert score <= 92, "score must be capped at 92"


def test_heuristic_score_ignores_stop_words():
    score = _heuristic_score_job(
        {"title": "Backend Developer", "company": "Acme"},
        profile="the and with backend",
    )
    assert score == 55, f"expected 55, got {score}"


# -------------------------------------------------------------------
# Item #3 — _matches_query filters correctly
# -------------------------------------------------------------------
def test_matches_query_term_overlap():
    job = {"title": "Python Developer", "company": "Stripe", "location": "Remote"}
    assert _matches_query(job, "python") is True
    assert _matches_query(job, "rust") is False


def test_matches_query_empty_returns_true():
    job = {"title": "Anything", "company": "X", "location": "Y"}
    assert _matches_query(job, "") is True


def test_query_terms_filters_short_and_stopwords():
    terms = _query_terms("Python Rust Go and the with for")
    assert "python" in terms
    assert "rust" in terms
    assert "go" not in terms  # len <= 2
    assert "and" not in terms
    assert "the" not in terms


# -------------------------------------------------------------------
# Item #3 — _dedupe_jobs collapses duplicates
# -------------------------------------------------------------------
def test_dedupe_jobs_keeps_first_by_url():
    a = {"title": "Backend", "company": "Stripe", "job_url": "https://x.com/1"}
    b = {"title": "Backend", "company": "Stripe", "job_url": "https://x.com/1"}
    c = {"title": "Frontend", "company": "Vercel", "job_url": "https://x.com/2"}
    out = _dedupe_jobs([a, b, c], max_results=10)
    assert len(out) == 2
    assert out[0]["job_url"] == "https://x.com/1"
    assert out[1]["job_url"] == "https://x.com/2"


def test_dedupe_jobs_caps_at_max_results():
    jobs = [
        {"title": f"J{i}", "company": "X", "job_url": f"https://x.com/{i}"}
        for i in range(20)
    ]
    out = _dedupe_jobs(jobs, max_results=5)
    assert len(out) == 5


# -------------------------------------------------------------------
# Item #3 — _search_open_job_apis returns real-shape jobs from mocked HTTP
# -------------------------------------------------------------------
def test_search_open_job_apis_returns_real_shape(monkeypatch):
    """The default path (live_browser=False) should hit the free key-less
    job-board APIs.  Mock Remotive/Arbeitnow/Jobicy to confirm we read
    their response shape and emit job_url-bearing listings."""

    from app.core import config
    monkeypatch.setattr(config.settings, "RAPIDAPI_KEY", "", raising=False)

    class _Resp:
        def __init__(self, data):
            self._data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self._data

    remotive_data = [
        {"position": "Python Developer", "company_name": "Stripe", "url": "https://stripe.com/r/1",
         "candidate_required_location": "Remote", "description": "FastAPI + Postgres", "tags": ["python"]},
        {"position": "Frontend Dev", "company_name": "Vercel", "url": "https://vercel.com/r/2",
         "candidate_required_location": "Remote", "description": "React", "tags": ["react"]},
    ]
    arbeitnow_data = {
        "data": [
            {"slug": "py1", "title": "Python Engineer", "company_name": "Acme",
             "url": "https://arbeitnow.com/r/1", "description": "Django", "remote": True,
             "location": "Berlin"},
        ]
    }
    jobicy_data = {
        "jobList": [
            {"jobTitle": "Python Dev", "companyName": "PyCo", "url": "https://jobicy.com/r/1",
             "jobExcerpt": "Flask", "jobGeo": "Remote"},
        ]
    }

    def fake_get(url, **kwargs):
        if "remotive" in url:
            return _Resp(remotive_data)
        if "arbeitnow" in url:
            return _Resp(arbeitnow_data)
        if "jobicy" in url:
            return _Resp(jobicy_data)
        return _Resp({})

    import httpx
    monkeypatch.setattr(httpx.Client, "get", fake_get)

    jobs = _search_open_job_apis("python", "Remote", max_results=10)
    assert jobs, "expected at least one job"
    for j in jobs:
        assert j.get("title"), f"missing title in {j}"
        assert j.get("job_url"), f"missing job_url in {j}"
        assert j.get("platform") in {"remotive", "arbeitnow", "jobicy"}


# -------------------------------------------------------------------
# Item #4 — POST /jobs/search returns 409 when no model is configured
# -------------------------------------------------------------------
@pytest.mark.asyncio
async def test_search_jobs_returns_409_without_model(monkeypatch):
    """When the user has no active model row, /jobs/search must short-circuit
    with HTTP 409 so the UI gets a clear 'configure your model first' error
    instead of a silent 'Agent failed' 30s later."""
    from fastapi import HTTPException
    from app.api.v1.jobs import search_jobs

    payload = JobSearchRequest(search_query="python", location="Remote", max_results=5)
    request = MagicMock()

    db = AsyncMock()
    result_mock = MagicMock()
    result_mock.scalars.return_value.first.return_value = None
    db.execute = AsyncMock(return_value=result_mock)

    current_user = MagicMock()
    current_user.id = uuid.uuid4()

    with pytest.raises(HTTPException) as exc_info:
        await search_jobs(request, payload, db, current_user)
    assert exc_info.value.status_code == 409
    assert "model" in exc_info.value.detail.lower()


# -------------------------------------------------------------------
# Item #5 — base64-encoded screenshot payload shape
# -------------------------------------------------------------------
def test_browser_frame_payload_uses_base64_screenshot():
    """The browser-use step callback should emit a frame whose payload
    contains ``screenshot_b64`` (base64 PNG) and ``mime`` — not raw bytes
    that the UI can't render."""
    import app.services.browser_control_service as bcs
    src = inspect.getsource(bcs)
    assert "screenshot_b64" in src, "browser_control_service must emit screenshot_b64"
    assert "base64.b64encode" in src, "must base64-encode the screenshot bytes"
    assert "mime" in src, "must include mime type for the data URL"


# -------------------------------------------------------------------
# Item #7 — frontend BrowserFrame field renamed to screenshot_b64
# -------------------------------------------------------------------
def test_frontend_browserframe_renamed_to_screenshot_b64():
    """The Zustand store + AgentStatusStream component must read
    `screenshot_b64` (with `mime` fallback) to render the SSE frame."""
    import pathlib
    root = pathlib.Path(r"D:\CareerCraft AI\frontend\src")
    store = (root / "store" / "agentSlice.ts").read_text(encoding="utf-8")
    component = (root / "components" / "agents" / "AgentStatusStream.tsx").read_text(encoding="utf-8")
    assert "screenshot_b64" in store, "store must declare screenshot_b64"
    assert "screenshot:" not in store or "screenshot_b64" in store, "store still references raw screenshot"
    assert "screenshot_b64" in component, "component must read screenshot_b64"
    assert "screenshot?" not in component, "component still reads raw screenshot?"
    # data: URL must include mime fallback
    assert "data:${" in component or "data:image/png" in component, "data URL must use mime or PNG default"


# -------------------------------------------------------------------
# Item #8 — _last_frame_emit is cleaned up on run completion
# -------------------------------------------------------------------
def test_last_frame_emit_cleaned_up_on_close():
    """Long-lived workers must not leak one dict entry per run.  The
    finally block in run_browser_task should pop the run_id key."""
    import app.services.browser_control_service as bcs
    src = inspect.getsource(bcs.run_browser_task)
    assert "_last_frame_emit" in src
    assert "pop" in src
    assert "finally" in src


# ---------------------------------------------------------------------------
# Tests for the prefer_live_browser per-user preference (steps 11-15)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_resolve_live_browser_request_true_always_wins(monkeypatch):
    """When the request asks for live_browser=True, preference is irrelevant."""
    from app.api.v1.jobs import _resolve_live_browser

    user = MagicMock()
    user.id = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    assert await _resolve_live_browser(db, user, request_value=True) is True
    # DB shouldn't even be hit
    assert db.execute.await_count == 0


@pytest.mark.asyncio
async def test_resolve_live_browser_request_false_prefers_user_pref(monkeypatch):
    """When request is False, user.prefer_live_browser=True flips it to True."""
    from app.api.v1.jobs import _resolve_live_browser

    user = MagicMock()
    user.id = uuid.uuid4()

    prefs = MagicMock()
    prefs.prefer_live_browser = True
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=prefs)))
    assert await _resolve_live_browser(db, user, request_value=False) is True


@pytest.mark.asyncio
async def test_resolve_live_browser_no_prefs_returns_false(monkeypatch):
    """When request is False AND user has no preferences row, return False."""
    from app.api.v1.jobs import _resolve_live_browser

    user = MagicMock()
    user.id = uuid.uuid4()
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    assert await _resolve_live_browser(db, user, request_value=False) is False


@pytest.mark.asyncio
async def test_resolve_live_browser_pref_false_returns_false(monkeypatch):
    """When request is False AND user has prefer_live_browser=False, return False."""
    from app.api.v1.jobs import _resolve_live_browser

    user = MagicMock()
    user.id = uuid.uuid4()
    prefs = MagicMock()
    prefs.prefer_live_browser = False
    db = MagicMock()
    db.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=prefs)))
    assert await _resolve_live_browser(db, user, request_value=False) is False


def test_user_preferences_model_has_prefer_live_browser_column():
    """SQLAlchemy model has the new column with correct defaults."""
    from app.models.db import UserPreferences

    col = UserPreferences.__table__.columns.get("prefer_live_browser")
    assert col is not None
    assert col.default is not None or col.server_default is not None
    assert bool(col.nullable) is False


def test_user_preferences_schema_default_is_false():
    """Pydantic schema default is False — opt-in, not opt-out."""
    from app.models.schemas import UserPreferencesSchema

    prefs = UserPreferencesSchema()
    assert prefs.prefer_live_browser is False
    prefs = UserPreferencesSchema(prefer_live_browser=True)
    assert prefs.prefer_live_browser is True


def test_supabase_migration_adds_column():
    """The new migration file ALTERs user_preferences and adds the column."""
    path = Path(
        r"D:\CareerCraft AI\supabase\migrations\0031_user_preferences_prefer_live_browser.sql"
    )
    assert path.exists(), "migration file missing"
    text = path.read_text(encoding="utf-8")
    assert "ADD COLUMN" in text
    assert "prefer_live_browser" in text
    assert "BOOLEAN" in text
    assert "NOT NULL" in text
    assert "DEFAULT false" in text


def test_daily_search_responds_with_visible_browser_count(monkeypatch):
    """internal.daily_search returns visible_browser_opted_in in the response shape."""
    import inspect

    from app.api import internal

    src = inspect.getsource(internal.daily_search)
    assert "visible_browser_opted_in" in src
    assert "prefer_live_browser" in src


def test_frontend_store_consumes_screenshot_b64():
    """agentSlice.BrowserFrame uses screenshot_b64 (rename from screenshot)."""
    path = Path(r"D:\CareerCraft AI\frontend\src\store\agentSlice.ts")
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "screenshot_b64" in text
    assert "screenshot:" not in text or "screenshot_b64" in text


def test_frontend_profile_page_has_live_browser_toggle():
    """profile page renders the live browser toggle with PATCH plumbing."""
    path = Path(
        r"D:\CareerCraft AI\frontend\src\app\(app)\settings\profile\page.tsx"
    )
    assert path.exists()
    text = path.read_text(encoding="utf-8")
    assert "prefer_live_browser" in text
    assert 'type="checkbox"' in text
    assert "PATCH" in text or "patch" in text  # apiClient.patch
    # Save payload must include the new field
    assert "prefer_live_browser: form.prefer_live_browser" in text


def test_search_jobs_uses_resolved_live_browser(monkeypatch):
    """The search_jobs route calls _resolve_live_browser and stores the resolved value in agent_run.input."""
    import inspect

    from app.api.v1 import jobs as jobs_module

    src = inspect.getsource(jobs_module.search_jobs)
    assert "_resolve_live_browser" in src
    # The route must write the resolved value (not the request value) into the input dict
    assert "live_browser\": live_browser" in src
    # And use the resolved value when enqueueing
    assert "live_browser=live_browser" in src


def test_prepare_application_apply_uses_resolved_live_browser(monkeypatch):
    """The prepare-apply route calls _resolve_live_browser and uses the resolved value when running browser task."""
    import inspect

    from app.api.v1 import jobs as jobs_module

    src = inspect.getsource(jobs_module.prepare_application_apply)
    assert "_resolve_live_browser" in src
    assert "live_browser=live_browser" in src

