"""Regression tests for backend/app/services/scheduled_jobs.py::check_application_status.

Covers three bugs:
  1. Tenant isolation — grouping must be by (user_id, platform), never by
     platform alone, so one user's applications are never checked under
     another user's model/account.
  2. Missing run_id — the managed-sandbox browser path requires an owned
     durable run id; the status-check browser call must always supply one.
  3. Key-case bug — the prompt asks for COMPANY/STATUS and the parser must
     read those same keys back out (case-insensitively) or well-formed
     responses never produce an update.
"""

import types
import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.services.scheduled_jobs import (
    StatusCheckTrigger,
    _parse_status_updates,
    check_application_status,
)


class _FakeResult:
    def __init__(self, items):
        self._items = items

    def scalars(self):
        return self

    def all(self):
        return self._items


class _FakeSession:
    """Minimal stand-in for AsyncSession: first execute() is the SELECT,
    every execute() after that is one of the UPDATE statements."""

    def __init__(self, applications):
        self.applications = applications
        self.added = []
        self.commits = 0
        self._calls = 0

    async def execute(self, stmt):
        self._calls += 1
        if self._calls == 1:
            return _FakeResult(self.applications)
        return _FakeResult([])

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


class _FakeSessionLocal:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, *exc):
        return False


def _make_app(user_id, company, platform_url):
    return types.SimpleNamespace(
        id=uuid.uuid4(),
        user_id=user_id,
        company=company,
        job_url=platform_url,
        status="applied",
    )


@pytest.mark.asyncio
async def test_status_check_never_runs_one_users_group_under_anothers_account():
    """Two different users' applications on the same platform must be
    processed as separate groups, each under its own model/account."""
    user_a = uuid.uuid4()
    user_b = uuid.uuid4()
    apps = [
        _make_app(user_a, "Acme", "https://www.linkedin.com/jobs/view/1"),
        _make_app(user_b, "Globex", "https://www.linkedin.com/jobs/view/2"),
    ]
    session = _FakeSession(apps)

    get_llm_calls = []

    async def fake_get_llm(user_id, db, *a, **kw):
        get_llm_calls.append(user_id)
        return f"llm-for-{user_id}"

    browser_calls = []

    async def fake_run_browser_task(
        llm,
        task,
        user_id,
        max_steps=15,
        live_browser=False,
        run_id=None,
    ):
        browser_calls.append({"llm": llm, "task": task, "user_id": user_id, "run_id": run_id})
        return "NO_UPDATE"

    with (
        patch("app.core.database.AsyncSessionLocal", _FakeSessionLocal(session)),
        patch("app.core.model_router.get_llm", AsyncMock(side_effect=fake_get_llm)),
        patch(
            "app.services.browser_control_service.run_browser_task_with_captcha_retry",
            AsyncMock(side_effect=fake_run_browser_task),
        ),
    ):
        result = await check_application_status(StatusCheckTrigger(user_id="all"))

    assert result["status"] == "ok"
    # Each user's group must be checked independently, under its own llm.
    assert sorted(get_llm_calls) == sorted([str(user_a), str(user_b)])
    assert len(browser_calls) == 2
    for call in browser_calls:
        assert call["llm"] == f"llm-for-{call['user_id']}"
        # Only one company (this user's own) should ever appear in the task
        # text — never another user's company name.
        if call["user_id"] == str(user_a):
            assert "Acme" in call["task"]
            assert "Globex" not in call["task"]
        else:
            assert "Globex" in call["task"]
            assert "Acme" not in call["task"]


@pytest.mark.asyncio
async def test_status_check_always_passes_a_run_id_to_browser_call():
    user_id = uuid.uuid4()
    apps = [_make_app(user_id, "Acme", "https://www.linkedin.com/jobs/view/1")]
    session = _FakeSession(apps)

    browser_calls = []

    async def fake_run_browser_task(
        llm,
        task,
        user_id,
        max_steps=15,
        live_browser=False,
        run_id=None,
    ):
        browser_calls.append(run_id)
        return "NO_UPDATE"

    with (
        patch("app.core.database.AsyncSessionLocal", _FakeSessionLocal(session)),
        patch("app.core.model_router.get_llm", AsyncMock(return_value="llm")),
        patch(
            "app.services.browser_control_service.run_browser_task_with_captcha_retry",
            AsyncMock(side_effect=fake_run_browser_task),
        ),
    ):
        await check_application_status(StatusCheckTrigger(user_id="all"))

    assert len(browser_calls) == 1
    assert browser_calls[0]  # not None / not empty
    # Must be a valid uuid so acquire_session() can look up an owned AgentRun.
    uuid.UUID(browser_calls[0])
    # The durable run row backing that run_id must exist for this user.
    assert any(str(run.id) == browser_calls[0] and run.user_id == user_id for run in session.added)


@pytest.mark.asyncio
async def test_well_formed_status_response_produces_an_update():
    """Regression: prompt asks for COMPANY/STATUS, parser must read those
    same keys back out — a matching response must not be silently dropped."""
    app = _make_app(uuid.uuid4(), "Acme Corp", "https://www.linkedin.com/jobs/view/1")
    result_text = "COMPANY: Acme Corp | STATUS: interview"

    updates = _parse_status_updates(result_text, [app])

    assert updates == {app.id: "interview"}


def test_parse_status_updates_ignores_no_update():
    app = _make_app(uuid.uuid4(), "Acme Corp", "https://www.linkedin.com/jobs/view/1")
    assert _parse_status_updates("COMPANY: Acme Corp | STATUS: no_update", [app]) == {}
    assert _parse_status_updates("", [app]) == {}
