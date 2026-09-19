"""reserve_application_attempt must be safe under Temporal's at-least-once
activity execution: retrying the same call (same run_id) must never create
a second AgentRun row. See app/workflows/activities.py's docstring."""
import uuid
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest


def _fake_session_cm(yielded):
    @asynccontextmanager
    async def _cm():
        yield yielded
    return _cm()


class _ReserveFakeDB:
    def __init__(self, app_row, existing_attempt=None):
        self.app_row = app_row
        self.existing_attempt = existing_attempt
        self.agent_runs: dict = {}
        self.added = []
        self.commits = 0

    async def execute(self, statement, *a, **k):
        compiled = str(statement).lower()

        class _R:
            def __init__(self, v):
                self._v = v

            def scalar_one_or_none(self):
                return self._v

        if "application_attempts" in compiled:
            return _R(self.existing_attempt)
        return _R(self.app_row)

    async def get(self, model, key, with_for_update=False):
        return self.agent_runs.get(key)

    def add(self, obj):
        from app.models.db import AgentRun
        if isinstance(obj, AgentRun):
            self.agent_runs[obj.id] = obj
        self.added.append(obj)

    async def flush(self):
        pass

    async def commit(self):
        self.commits += 1


@pytest.mark.asyncio
async def test_reserve_activity_retry_with_same_run_id_creates_one_agent_run(monkeypatch):
    from app.models.db import JobApplication
    from app.workflows import activities

    user_id = uuid.uuid4()
    job_application_id = uuid.uuid4()
    run_id = str(uuid.uuid4())
    app_row = JobApplication(
        id=job_application_id, user_id=user_id, company="Acme", role="Backend Engineer",
        job_url="https://jobs.example.test/apply", status="saved", resume_id=uuid.uuid4(),
    )
    fake = _ReserveFakeDB(app_row)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _fake_session_cm(fake))
    monkeypatch.setattr(
        "app.services.application_workflow.load_resume",
        AsyncMock(return_value=(b"%PDF-test", "deadbeef")),
    )

    params = {
        "user_id": str(user_id), "job_application_id": str(job_application_id),
        "workflow_id": f"auto-apply/{user_id}/{job_application_id}", "run_id": run_id,
    }

    first = await activities.reserve_application_attempt(params)
    # Simulate Temporal retrying the same activity invocation after the
    # first one's reply to the server was lost (commit already happened).
    second = await activities.reserve_application_attempt(params)

    assert first["run_id"] == second["run_id"] == run_id
    assert len(fake.agent_runs) == 1


@pytest.mark.asyncio
async def test_reserve_activity_rejects_different_workflow_when_already_submitting(monkeypatch):
    from app.models.db import ApplicationAttempt, JobApplication
    from app.workflows import activities

    user_id = uuid.uuid4()
    job_application_id = uuid.uuid4()
    app_row = JobApplication(
        id=job_application_id, user_id=user_id, company="Acme", role="Backend Engineer",
        job_url="https://jobs.example.test/apply", status="saved", resume_id=uuid.uuid4(),
    )
    other_workflow_attempt = ApplicationAttempt(
        id=uuid.uuid4(), user_id=user_id, job_application_id=job_application_id,
        workflow_id="auto-apply/other/other", state="submitting",
    )
    fake = _ReserveFakeDB(app_row, existing_attempt=other_workflow_attempt)
    monkeypatch.setattr("app.core.database.AsyncSessionLocal", lambda: _fake_session_cm(fake))

    params = {
        "user_id": str(user_id), "job_application_id": str(job_application_id),
        "workflow_id": f"auto-apply/{user_id}/{job_application_id}", "run_id": str(uuid.uuid4()),
    }
    with pytest.raises(ValueError, match="already submitting"):
        await activities.reserve_application_attempt(params)
