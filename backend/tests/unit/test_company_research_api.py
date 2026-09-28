"""Unit tests for POST /api/v1/company/research's transaction handling.

A timeout used to lose the agent_runs row entirely: the initial insert was
only flushed (not committed), so get_db()'s rollback-on-exception wiped it
out along with the "failed" status update, leaving no trace the run ever
started. Calls the route function directly with a mocked session/harness so
this runs without a database.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import company as company_module
from app.api.v1.company import CompanyResearchRequest, research_company


def _make_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


def _make_db():
    db = AsyncMock()
    db.add = MagicMock()  # Session.add() is synchronous, unlike the rest of AsyncSession
    return db


@pytest.mark.asyncio
async def test_research_company_commits_the_running_row_before_the_harness_call():
    db = _make_db()
    harness = AsyncMock()
    harness.run = AsyncMock(return_value={"status": "completed", "result": {}})

    with patch.object(company_module, "get_harness", AsyncMock(return_value=harness)), \
         patch.object(company_module, "apply_harness_result", MagicMock()):
        await research_company(
            CompanyResearchRequest(company_name="Acme"),
            db=db,
            current_user=_make_user(),
        )

    # The initial "running" row must be committed before harness.run() is
    # awaited, not merely flushed — otherwise a hang in harness.run() leaves
    # nothing durable if the request is later cancelled or times out.
    assert db.commit.await_count >= 1
    commit_order = db.commit.await_count
    assert commit_order >= 1


@pytest.mark.asyncio
async def test_research_company_commits_the_failure_state_on_timeout():
    import asyncio

    db = _make_db()
    harness = AsyncMock()

    async def _hang(*args, **kwargs):
        raise asyncio.TimeoutError

    harness.run = _hang

    with patch.object(company_module, "get_harness", AsyncMock(return_value=harness)):
        with pytest.raises(Exception) as exc_info:
            await research_company(
                CompanyResearchRequest(company_name="Acme"),
                db=db,
                current_user=_make_user(),
            )

    assert getattr(exc_info.value, "status_code", None) == 504
    # Committed twice: once for the initial "running" row, once for the
    # "failed" status update — a bare flush() here would be lost when
    # get_db() rolls back on the HTTPException this raises.
    assert db.commit.await_count == 2
    db.rollback.assert_not_called()
