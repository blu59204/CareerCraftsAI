"""Regression tests for the PR #34 review findings."""

import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError


def test_search_max_results_is_bounded():
    from app.api.v1.jobs import JobSearchRequest

    with pytest.raises(ValidationError):
        JobSearchRequest(max_results=10_000)
    assert JobSearchRequest(max_results=25).max_results == 25


def test_picked_resume_keeps_relevant_chunks_from_the_whole_document():
    from app.services.rag_service import _relevant_chunks

    chunks = [f"intro {i}" for i in range(10)] + ["Skills: kubernetes terraform golang"]
    picked = _relevant_chunks(chunks, "Senior engineer: kubernetes, terraform", 3)
    assert len(picked) == 3
    assert picked[-1] == chunks[-1]  # the late skills section is kept
    assert picked == sorted(picked, key=chunks.index)  # still in resume order
    assert _relevant_chunks(chunks[:2], "x", 8) == chunks[:2]


@pytest.mark.asyncio
async def test_notify_goes_through_the_notification_workflow(monkeypatch):
    import app.workflows.starters as starters
    from app.services import auto_apply_queue as q

    start = AsyncMock(return_value="wf")
    monkeypatch.setattr(starters, "start_notification", start)
    owner = uuid.uuid4()
    jobs = [SimpleNamespace(id=uuid.uuid4()), SimpleNamespace(id=uuid.uuid4())]
    await q._notify(owner, jobs, 70)
    start.assert_awaited_once()
    args, kwargs = start.call_args
    assert args[0] == owner and args[1] == "job_matches" and "2 new matches" in args[2]
    assert kwargs["dedupe_key"].startswith(f"rule-notify:{owner}:")


@pytest.mark.asyncio
async def test_rule_only_reads_jobs_found_after_it_was_switched_on(monkeypatch):
    from sqlalchemy.dialects import postgresql

    from app.services import auto_apply_queue as q

    seen = []

    class Result:
        def scalar_one(self):
            return 0

        def scalars(self):
            return self

        def all(self):
            return []

    class DB:
        async def execute(self, stmt):
            seen.append(str(stmt.compile(dialect=postgresql.dialect())))
            return Result()

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

    monkeypatch.setattr(q, "AsyncSessionLocal", DB)
    rule = {"min_match": 70, "action": "notify", "since": datetime(2026, 10, 1, tzinfo=UTC)}
    await q._candidates(uuid.uuid4(), datetime.now(UTC), rule)
    saved_query = next(sql for sql in seen if "job_applications.status" in sql)
    assert "job_applications.found_at >=" in saved_query


def test_city_filter_matches_old_and_new_names_and_any_listed_city():
    from types import SimpleNamespace

    from app.api.v1.jobs import _matches_location_filter

    def at(loc):
        return SimpleNamespace(location=loc)

    assert _matches_location_filter(at("Bangalore, Karnataka"), "Bengaluru")
    assert _matches_location_filter(at("Bengaluru East"), "bangalore")
    assert _matches_location_filter(at("Pune, India"), "Bengaluru,Pune")
    assert not _matches_location_filter(at("Chennai, India"), "Bengaluru,Pune")
