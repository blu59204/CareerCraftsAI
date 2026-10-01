"""Retired executor routes cannot reach an application submit."""

import uuid
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from fastapi import FastAPI

from app.api.v1 import agents
from app.api.v1.deps import get_current_user, get_db
from app.models.db import AgentRun, User


@pytest.mark.asyncio
async def test_generic_approval_cannot_submit_an_extension_application(monkeypatch):
    user = User(id=uuid.uuid4(), email="test@example.test")
    run = AgentRun(
        id=uuid.uuid4(),
        user_id=user.id,
        agent_type="apply_prepare",
        status="awaiting_approval",
        input={"workflow_id": "auto-apply/test/test"},
        output={"type": "resume_ready"},
    )
    db = MagicMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = run
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    signal = AsyncMock()
    monkeypatch.setattr("app.workflows.starters.signal_agent_decision", signal)

    app = FastAPI()
    app.include_router(agents.router)
    app.dependency_overrides[get_current_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.post(f"/agents/{run.id}/approve", json={"approved": True})

    assert response.status_code == 409
    assert run.status == "awaiting_approval"
    db.commit.assert_not_awaited()
    signal.assert_not_awaited()


def test_retired_browser_routes_and_tables_are_not_in_the_application():
    from app.core.database import Base
    from app.main import app

    # OpenAPI paths are flattened on every FastAPI version; newer releases nest
    # included routers in app.routes as objects without a .path.
    assert not any(path.startswith("/api/v1/browser") for path in app.openapi()["paths"])
    assert "browser_sessions" not in Base.metadata.tables
    assert "browser_account_states" not in Base.metadata.tables
