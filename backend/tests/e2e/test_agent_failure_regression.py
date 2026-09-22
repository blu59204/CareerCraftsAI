"""Authenticated staging checks for the shared agent failure modes.

Run with RUN_AGENT_FAILURE_E2E=1 and a staging TEST_JWT. This suite never
approves an email or application submission.
"""
from __future__ import annotations

import os
import time

import pytest

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.skipif(
        os.getenv("RUN_AGENT_FAILURE_E2E") != "1",
        reason="Set RUN_AGENT_FAILURE_E2E=1 for authenticated staging checks",
    ),
]

CASES = [
    ("job_search", {"search_query": "python engineer", "location": "Remote", "max_results": 3}),
    ("nl_job_search", {"query": "remote senior Python role"}),
    ("resume_optimize", {"jd_text": "Senior Python Engineer using FastAPI and PostgreSQL"}),
    ("cover_letter", {"jd_text": "Senior Python Engineer using FastAPI", "tone": "formal"}),
    ("linkedin_optimize", {"target_role": "Senior Python Engineer"}),
    ("linkedin_outreach", {"company_name": "Stripe", "role_context": "Senior Python Engineer"}),
    ("email", {"company": "Example", "role": "Senior Python Engineer", "recipient_email": "test@example.com"}),
    ("email_monitor", {}),
    ("interview_coach", {"role": "Senior Python Engineer", "company": "Example"}),
    ("interview_prep", {"role": "Senior Python Engineer", "company": "Example"}),
    ("company_research", {"company_name": "Example"}),
    ("salary_intelligence", {"role": "Senior Python Engineer", "location": "Bangalore", "experience_years": 5}),
]


def _wait_for_terminal(client, run_id: str, timeout_s: int) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        response = client.get(f"/agents/runs/{run_id}")
        response.raise_for_status()
        data = response.json()
        if data["status"] in {"completed", "awaiting_approval", "failed", "expired"}:
            return data
        time.sleep(1)
    raise AssertionError(f"run {run_id} did not reach terminal status within {timeout_s}s")


@pytest.mark.parametrize("task_type,context", CASES)
def test_agent_route_reaches_terminal_result_without_429(api_client, task_type, context):
    response = api_client.post("/agents/run", json={"task_type": task_type, "context": context})
    assert response.status_code != 429, response.text
    response.raise_for_status()

    run_id = response.json()["run_id"]
    timeout = 300 if task_type == "auto_apply" else 120
    run = _wait_for_terminal(api_client, run_id, timeout)
    assert run["status"] in {"completed", "awaiting_approval"}, run
    assert run.get("tokens_used", 0) > 0, run
    assert run.get("duration_ms") is not None, run


def test_invalid_task_type_is_rejected(api_client):
    response = api_client.post("/agents/run", json={"task_type": "not_a_real_task", "context": {}})
    assert response.status_code == 400
