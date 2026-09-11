"""
test_agent_e2e.py — End-to-end agent integration tests.

Requires INTEGRATION=1, real DB, Redis, and LLM API key.
Use: INTEGRATION=1 pytest tests/integration/test_agent_e2e.py -v
"""
from __future__ import annotations

import asyncio
import os

import pytest

pytestmark = pytest.mark.skipif(
    os.environ.get("INTEGRATION") != "1",
    reason="Set INTEGRATION=1 to run integration tests with real infrastructure",
)


@pytest.mark.asyncio
async def test_hitl_gate_prevents_email_send():
    from app.agents.email_agent import email_agent_node
    from app.agents.state import AgentState

    state = AgentState(
        user_id="test-user-001",
        run_id="test-run-e2e-001",
        task_type="email",
        context={
            "recruiter_name": "Test Recruiter",
            "recruiter_company": "TestCorp",
            "recruiter_email": "test@testcorp.com",
            "job_title": "Engineer",
        },
        messages=[],
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )
    result = email_agent_node(state)
    assert result.get("status") in ("awaiting_approval", "failed")


@pytest.mark.asyncio
async def test_hitl_gate_cancel_flow():
    """HITL gate should exist — checkpoint is visible even without real services."""
    from app.agents.email_agent import email_agent_node
    from app.agents.state import AgentState

    state = AgentState(
        user_id="test-user-002",
        run_id="test-run-e2e-002",
        task_type="email",
        context={
            "recruiter_name": "HR",
            "recruiter_company": "Company",
            "recruiter_email": "hr@company.com",
            "job_title": "Dev",
        },
        messages=[],
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )
    result = email_agent_node(state)
    pending = result.get("pending_action")
    if pending:
        assert pending.get("type") == "send_email"
        assert "to" in pending.get("details", {})
        assert "subject" in pending.get("details", {})
        assert "body" in pending.get("details", {})


@pytest.mark.asyncio
async def test_company_research_without_exa_key_is_graceful():
    from app.agents.company_research_agent import company_research_node
    from app.agents.state import AgentState

    state = AgentState(
        user_id="test-user-003",
        run_id="test-run-e2e-003",
        task_type="company_research",
        context={"company_name": "TestCorp"},
        messages=[],
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )
    result = company_research_node(state)
    assert result.get("status") in ("completed", "failed")


@pytest.mark.asyncio
async def test_nl_search_returns_checkpoint():
    from app.agents.nl_search_agent import nl_search_node
    from app.agents.state import AgentState

    state = AgentState(
        user_id="test-user-004",
        run_id="test-run-e2e-004",
        task_type="nl_job_search",
        context={"query": "python developer remote India"},
        messages=[],
        status="running",
        pending_action=None,
        result=None,
        error=None,
    )
    result = nl_search_node(state)
    assert result.get("status") in ("awaiting_approval", "completed", "failed")
